import asyncio
import contextlib
import json
import os
import secrets
import signal
import subprocess
import tempfile
import textwrap
import time
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import httpx
from mpp import Receipt
from mpp.client import get as mpp_get
from mpp.methods.tempo import ChargeIntent, TempoAccount, tempo

WORKSPACE = Path(os.environ.get("TEMPO_BENCH_WORKSPACE", "/app"))
LOG_DIR = Path(os.environ.get("TEMPO_BENCH_LOG_DIR", "/logs/verifier"))
OUT_PATH = WORKSPACE / "out.json"
SCORES_PATH = WORKSPACE / "scores.json"
LOG_SCORES_PATH = LOG_DIR / "scores.json"
RPC_URL = "https://rpc.moderato.tempo.xyz"
CHAIN_ID = 42431
CHAIN_ID_HEX = hex(CHAIN_ID)
TOKEN = "0x20c0000000000000000000000000000000000000"
USDC = "0x20C000000000000000000000b9537d11c60E8b50"
BASE_USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
RECIPIENT = "0x1111111111111111111111111111111111111111"
PAYER_PRIVATE_KEY = os.environ.get(
    "TEMPO_MPP_PAYER_PRIVATE_KEY", f"0x{secrets.token_hex(32)}"
)
MPP_SECRET_KEY = "tempo-bench-mpp-secret-key-000000001"
CHARGE_AMOUNT = Decimal("0.01")
TOKEN_BASE_UNITS = Decimal("1000000")
KEEP_SERVER = os.environ.get("TEMPO_MPP_KEEP_SERVER") == "1"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_scores(value: dict) -> None:
    write_json(SCORES_PATH, value)
    write_json(LOG_SCORES_PATH, value)


def log_event(event: str, **fields: object) -> None:
    payload = {"event": event, "ts": time.time(), **fields}
    line = json.dumps(payload, sort_keys=True)
    print(line, flush=True)
    with (LOG_DIR / "verifier-events.ndjson").open("a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")


def read_json_log(name: str) -> object | None:
    path = LOG_DIR / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def response_snapshot(response: httpx.Response) -> dict:
    return {
        "body": response.text[:4000],
        "headers": dict(response.headers),
        "status": response.status_code,
    }


def fail(reason: str) -> None:
    log_event("fail", reason=reason)
    diagnostics = {
        name.removesuffix(".json"): value
        for name in [
            "challenge-failure.json",
            "discovery-failure.json",
            "free-failure.json",
            "paid-failure.json",
            "payment-failure.json",
            "session-client.json",
        ]
        if (value := read_json_log(name)) is not None
    }
    score = {"reward": 0, "reason": reason}
    if diagnostics:
        score["diagnostics"] = diagnostics
    write_scores(score)
    write_json(LOG_DIR / "details.json", {"ok": False, "reason": reason, **score})


def rpc(method: str, params: list) -> object:
    response = httpx.post(
        RPC_URL,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload["result"]


def validate_url(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"out.json {name} must be a string")
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise RuntimeError(f"out.json {name} must be a local http URL")
    if parsed.port is None or not parsed.path.startswith("/"):
        raise RuntimeError(f"out.json {name} must include port and path")
    return value


def read_out_json(process: subprocess.Popen[str], keys: list[str]) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if OUT_PATH.exists():
            out = json.loads(OUT_PATH.read_text(encoding="utf-8"))
            urls = {key: validate_url(key, out.get(key)) for key in keys}
            log_event("out_json", **urls)
            return urls
        if process.poll() is not None:
            raise RuntimeError("server exited before writing out.json")
        time.sleep(0.1)
    raise RuntimeError("server did not write out.json within 30s")


def start_server() -> subprocess.Popen[str]:
    log_event(
        "start_server",
        recipient=RECIPIENT,
        chargeAmount=str(CHARGE_AMOUNT),
        chargeAmountEnvKeys=["CHARGE_AMOUNT", "MPP_CHARGE_AMOUNT", "PAYMENT_AMOUNT"],
        recipientEnvKeys=[
            "MPP_RECIPIENT_ADDRESS",
            "PAYMENT_RECIPIENT_ADDRESS",
            "RECIPIENT_ADDRESS",
        ],
    )
    stdout = (LOG_DIR / "server.stdout.txt").open("w", encoding="utf-8")
    stderr = (LOG_DIR / "server.stderr.txt").open("w", encoding="utf-8")
    return subprocess.Popen(
        ["npm", "run", "--silent", "serve"],
        cwd=WORKSPACE,
        env={
            **os.environ,
            "MPP_SECRET_KEY": MPP_SECRET_KEY,
            "CHARGE_AMOUNT": str(CHARGE_AMOUNT),
            "MPP_CHARGE_AMOUNT": str(CHARGE_AMOUNT),
            "MPP_RECIPIENT_ADDRESS": RECIPIENT,
            "MPPX_RPC_URL": os.environ.get("MPPX_RPC_URL", RPC_URL),
            "PAYMENT_AMOUNT": str(CHARGE_AMOUNT),
            "PAYMENT_RECIPIENT_ADDRESS": RECIPIENT,
            "RECIPIENT_ADDRESS": RECIPIENT,
        },
        stderr=stderr,
        stdout=stdout,
        start_new_session=True,
        text=True,
    )


def request_until_ready(url: str) -> httpx.Response:
    deadline = time.monotonic() + 30
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return httpx.get(url, headers={"accept": "application/json"}, timeout=5)
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"endpoint did not respond: {last_error}")


def free_request(url: str) -> dict:
    response = request_until_ready(url)
    log_event("free_response", status=response.status_code, url=url)
    if response.status_code != 200:
        write_json(
            LOG_DIR / "free-failure.json",
            {"reason": "unexpected status", "url": url, **response_snapshot(response)},
        )
        raise RuntimeError(f"free request returned {response.status_code}")
    response.json()
    return {"json": True, "status": response.status_code}


def challenge_request(url: str, expected: dict[str, str]) -> dict:
    response = request_until_ready(url)
    log_event("challenge_response", status=response.status_code, url=url)
    if response.status_code != 402:
        write_json(
            LOG_DIR / "challenge-failure.json",
            {"reason": "unexpected status", "url": url, **response_snapshot(response)},
        )
        raise RuntimeError(f"challenge request returned {response.status_code}")
    raw = "\n".join(
        [
            str(response.status_code),
            response.text,
            json.dumps(dict(response.headers), sort_keys=True),
        ]
    )
    lowered = raw.lower()
    return {
        "status": response.status_code,
        "hasPaymentChallenge": "payment" in lowered or "www-authenticate" in lowered,
        **{name: needle.lower() in lowered for name, needle in expected.items()},
    }


def discovery_request(url: str, paid_path: str) -> dict:
    response = request_until_ready(url)
    log_event("discovery_response", status=response.status_code, url=url)
    if response.status_code != 200:
        write_json(
            LOG_DIR / "discovery-failure.json",
            {"reason": "unexpected status", "url": url, **response_snapshot(response)},
        )
        raise RuntimeError(f"discovery request returned {response.status_code}")
    document = response.json()
    raw = json.dumps(document, sort_keys=True).lower()
    paths = document.get("paths", {})
    path_doc = paths.get(paid_path, {}) if isinstance(paths, dict) else {}
    path_raw = json.dumps(path_doc, sort_keys=True).lower()
    return {
        "status": response.status_code,
        "openapi": isinstance(document.get("openapi"), str),
        "hasPaidPath": paid_path in paths,
        "hasPaymentInfo": "x-payment-info" in path_raw,
        "mentionsTempo": "tempo" in path_raw,
        "mentionsCharge": "charge" in path_raw,
        "mentionsPathUsd": TOKEN.lower() in raw,
    }


def fund_account(address: str) -> None:
    log_event("fund_account_start", address=address)
    tx_hashes = rpc("tempo_fundAddress", [address])
    log_event("fund_account_txs", address=address, hashes=tx_hashes)
    write_json(LOG_DIR / "faucet.json", {"address": address, "hashes": tx_hashes})
    for tx_hash in tx_hashes:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if rpc("eth_getTransactionReceipt", [tx_hash]):
                log_event("fund_account_confirmed", txHash=tx_hash)
                break
            time.sleep(1)
        else:
            raise RuntimeError(f"faucet transaction did not confirm: {tx_hash}")


def normalize_address(address: str | None) -> str | None:
    return address.lower() if isinstance(address, str) else None


def topic_address(address: str) -> str:
    return f"0x{'0' * 24}{address.removeprefix('0x').lower()}"


def transfer_data(amount: Decimal) -> str:
    return f"0x{int(amount * TOKEN_BASE_UNITS):064x}"


def payment_transaction(reference: str, payer: str) -> dict:
    log_event("payment_transaction_fetch", reference=reference, payer=payer)
    transaction = rpc("eth_getTransactionByHash", [reference])
    receipt = rpc("eth_getTransactionReceipt", [reference])
    if not isinstance(transaction, dict):
        write_json(
            LOG_DIR / "payment-failure.json",
            {
                "reason": "payment receipt reference was not a transaction hash",
                "reference": reference,
                "transaction": transaction,
            },
        )
        raise RuntimeError("payment receipt reference was not a transaction hash")
    if not isinstance(receipt, dict):
        write_json(
            LOG_DIR / "payment-failure.json",
            {
                "reason": "payment transaction receipt was not found",
                "reference": reference,
                "transaction": transaction,
            },
        )
        raise RuntimeError("payment transaction receipt was not found")

    transfer_log = None
    payer_topic = topic_address(payer)
    recipient_topic = topic_address(RECIPIENT)
    for log in receipt.get("logs", []):
        topics = log.get("topics", [])
        if (
            normalize_address(log.get("address")) == TOKEN
            and len(topics) >= 3
            and topics[1].lower() == payer_topic
            and topics[2].lower() == recipient_topic
        ):
            transfer_log = log
            break

    call = (transaction.get("calls") or [{}])[0]
    expected_transfer_data = transfer_data(CHARGE_AMOUNT)
    transfer_candidates = [
        {
            "amount": log.get("data"),
            "from": topics[1].lower() if len(topics) >= 2 else None,
            "to": topics[2].lower() if len(topics) >= 3 else None,
            "token": normalize_address(log.get("address")),
        }
        for log in receipt.get("logs", [])
        if normalize_address(log.get("address")) == TOKEN
        for topics in [log.get("topics", [])]
    ]
    proof = {
        "blockHash": receipt.get("blockHash"),
        "blockNumber": receipt.get("blockNumber"),
        "callTo": normalize_address(call.get("to")),
        "callToMatchesToken": normalize_address(call.get("to")) == TOKEN,
        "chainId": transaction.get("chainId"),
        "chainMatches": transaction.get("chainId") == CHAIN_ID_HEX,
        "confirmed": bool(receipt.get("blockHash") and receipt.get("blockNumber")),
        "feeToken": normalize_address(transaction.get("feeToken")),
        "feeTokenMatches": normalize_address(transaction.get("feeToken")) == TOKEN,
        "from": normalize_address(transaction.get("from")),
        "fromMatchesPayer": normalize_address(transaction.get("from"))
        == normalize_address(payer),
        "hash": transaction.get("hash"),
        "hasLogs": bool(receipt.get("logs")),
        "receiptFeeToken": normalize_address(receipt.get("feeToken")),
        "receiptFeeTokenMatches": normalize_address(receipt.get("feeToken")) == TOKEN,
        "receiptStatus": receipt.get("status"),
        "receiptStatusIsSuccess": receipt.get("status") == "0x1",
        "receiptTo": normalize_address(receipt.get("to")),
        "receiptToMatchesToken": normalize_address(receipt.get("to")) == TOKEN,
        "receiptTransactionHash": receipt.get("transactionHash"),
        "receiptTransactionHashMatchesReference": reference
        == receipt.get("transactionHash"),
        "referenceMatchesHash": reference == transaction.get("hash"),
        "successful": receipt.get("status") == "0x1",
        "expected": {
            "amount": expected_transfer_data,
            "payer": normalize_address(payer),
            "recipient": normalize_address(RECIPIENT),
            "recipientTopic": recipient_topic,
            "token": TOKEN,
        },
        "transferCandidates": transfer_candidates,
        "transfer": {
            "amount": transfer_log.get("data") if transfer_log else None,
            "amountMatchesCharge": transfer_log is not None
            and transfer_log.get("data") == expected_transfer_data,
            "found": transfer_log is not None,
            "from": payer_topic,
            "fromMatchesPayer": transfer_log is not None
            and len(transfer_log.get("topics", [])) >= 2
            and transfer_log["topics"][1].lower() == payer_topic,
            "to": recipient_topic,
            "toMatchesRecipient": transfer_log is not None
            and len(transfer_log.get("topics", [])) >= 3
            and transfer_log["topics"][2].lower() == recipient_topic,
            "token": normalize_address(transfer_log.get("address"))
            if transfer_log
            else None,
            "tokenMatches": transfer_log is not None
            and normalize_address(transfer_log.get("address")) == TOKEN,
        },
    }

    def raise_payment_error(reason: str) -> None:
        failure = {"reason": reason, "proof": proof}
        write_json(LOG_DIR / "payment-proof.json", proof)
        write_json(LOG_DIR / "payment-failure.json", failure)
        raise RuntimeError(reason)

    write_json(LOG_DIR / "payment-proof.json", proof)
    log_event(
        "payment_transaction_proof",
        reference=reference,
        transferFound=proof["transfer"]["found"],
        transferCandidates=len(transfer_candidates),
    )
    if not proof["chainMatches"]:
        raise_payment_error(f"payment transaction used chain {proof['chainId']}")
    if not proof["fromMatchesPayer"]:
        raise_payment_error("payment transaction payer mismatch")
    if not proof["successful"]:
        raise_payment_error("payment transaction was not successful")
    if not proof["transfer"]["found"]:
        raise_payment_error("payment transaction did not transfer to recipient")
    if not proof["transfer"]["amountMatchesCharge"]:
        raise_payment_error("payment transaction amount mismatch")
    return proof


async def paid_request(url: str) -> dict:
    log_event("paid_request_start", url=url)
    account = TempoAccount.from_key(PAYER_PRIVATE_KEY)
    fund_account(account.address)
    response = await mpp_get(
        url,
        methods=[
            tempo(
                intents={"charge": ChargeIntent()},
                account=account,
                chain_id=CHAIN_ID,
                rpc_url=RPC_URL,
            )
        ],
        headers={"accept": "application/json"},
    )
    receipt_header = response.headers.get("payment-receipt")
    log_event(
        "paid_response",
        hasReceiptHeader=bool(receipt_header),
        status=response.status_code,
        url=url,
    )
    if response.status_code < 200 or response.status_code >= 300:
        write_json(
            LOG_DIR / "paid-failure.json",
            {"reason": "unexpected status", "url": url, **response_snapshot(response)},
        )
        raise RuntimeError(f"paid request returned {response.status_code}")
    if not receipt_header:
        write_json(
            LOG_DIR / "paid-failure.json",
            {
                "reason": "missing payment receipt",
                "url": url,
                **response_snapshot(response),
            },
        )
        raise RuntimeError("paid response did not include Payment-Receipt")
    response.json()
    receipt = Receipt.from_payment_receipt(receipt_header)
    log_event(
        "paid_receipt",
        method=receipt.method,
        reference=receipt.reference,
        status=receipt.status,
    )
    transaction = payment_transaction(receipt.reference, account.address)
    return {
        "hasReceipt": True,
        "json": True,
        "receipt": {
            "externalId": receipt.external_id,
            "extra": receipt.extra,
            "hasReference": bool(receipt.reference),
            "hasTimestamp": receipt.timestamp is not None,
            "method": receipt.method,
            "methodIsTempo": receipt.method == "tempo",
            "reference": receipt.reference,
            "referenceMatchesTransaction": receipt.reference == transaction["hash"],
            "status": receipt.status,
            "statusIsSuccess": receipt.status == "success",
            "timestamp": receipt.timestamp.isoformat(),
        },
        "receiptHeader": receipt_header,
        "receiptReference": receipt.reference,
        "status": response.status_code,
        "transaction": transaction,
    }


def session_request(url: str) -> dict:
    log_event("session_request_start", url=url)
    script = Path(tempfile.mkdtemp(prefix="tempo-mpp-session-")) / "session-client.mjs"
    script.write_text(
        textwrap.dedent(
            """
            import { createRequire } from 'node:module'

            const workspace = process.env.TEMPO_BENCH_WORKSPACE ?? '/app'
            const require = createRequire(`${workspace}/package.json`)
            const { tempo } = await import(require.resolve('mppx/client'))
            const { createClient, http } = await import(require.resolve('viem'))
            const { privateKeyToAccount } = await import(
              require.resolve('viem/accounts')
            )
            const { Actions, Chain } = await import(require.resolve('viem/tempo'))

            const account = privateKeyToAccount(process.env.TEMPO_MPP_PAYER_PRIVATE_KEY)
            const client = createClient({
              account,
              chain: Chain.testnet,
              pollingInterval: 1_000,
              transport: http(process.env.MPPX_RPC_URL),
            })

            await Actions.faucet.fundSync(client, { account, timeout: 60_000 })
            const session = tempo.session.manager({ client, maxDeposit: '0.02' })
            const response = await session.fetch(process.env.TEMPO_MPP_SESSION_URL, {
              headers: { accept: 'application/json' },
            })
            const receiptHeader = response.headers.get('payment-receipt')
            if (!response.ok)
              throw new Error(`session request returned ${response.status}`)
            if (!receiptHeader)
              throw new Error('session response did not include Payment-Receipt')
            await response.json()
            let closeReceipt = null
            try {
              closeReceipt = await session.close()
            } catch (error) {
              closeReceipt = {
                error: error instanceof Error ? error.message : String(error),
              }
            }
            console.log(JSON.stringify({
              status: response.status,
              json: true,
              hasReceipt: true,
              receiptHeader,
              closeReceipt,
            }))
            """
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["node", str(script)],
        cwd=WORKSPACE,
        env={
            **os.environ,
            "MPPX_RPC_URL": os.environ.get("MPPX_RPC_URL", RPC_URL),
            "TEMPO_MPP_PAYER_PRIVATE_KEY": PAYER_PRIVATE_KEY,
            "TEMPO_MPP_SESSION_URL": url,
        },
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    write_json(
        LOG_DIR / "session-client.json",
        {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
    )
    log_event(
        "session_client_exit",
        returncode=result.returncode,
        stderrTail=result.stderr[-1000:],
        stdoutTail=result.stdout[-1000:],
    )
    if result.returncode != 0:
        raise RuntimeError(f"session client failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = read_out_json(process, ["freeUrl", "paidUrl"])
    return {
        "out": out,
        "free": free_request(out["freeUrl"]),
        "offer": challenge_request(
            out["paidUrl"],
            {"pathUsdAdvertised": TOKEN, "chargeAdvertised": "charge"},
        ),
        "paid": await paid_request(out["paidUrl"]),
    }


async def main() -> None:
    process = None
    keep_process = False
    try:
        process = start_server()
        result = await run_task(process)
        write_scores(
            {
                "reward": 1,
                "server": {"pid": process.pid, "processGroupId": process.pid},
                **result,
            }
        )
        write_json(LOG_DIR / "details.json", {"ok": True, **result.get("out", {})})
        keep_process = KEEP_SERVER
    except Exception as exc:
        fail(str(exc))
    finally:
        if process and process.poll() is None and not keep_process:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            time.sleep(1)
            if process.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)


if __name__ == "__main__":
    asyncio.run(main())
