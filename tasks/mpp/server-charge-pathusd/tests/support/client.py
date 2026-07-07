import asyncio
import contextlib
import json
import os
import signal
import subprocess
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
# Fixed Moderato fixture values used by the verifier-paid MPP request.
TOKEN = "0x20c0000000000000000000000000000000000000"
RECIPIENT = "0x1111111111111111111111111111111111111111"
PAYER_PRIVATE_KEY = "0x59c6995e998f97a5a004497e5da46f94a879b621718eb9bde6e3db6c2b2b3b4d"
MPP_SECRET_KEY = "tempo-bench-mpp-secret-key-000000001"
CHARGE_AMOUNT = Decimal("0.000001")
TOKEN_BASE_UNITS = Decimal("1000000")
KEEP_SERVER = os.environ.get("TEMPO_MPP_KEEP_SERVER") == "1"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_scores(value: dict) -> None:
    write_json(SCORES_PATH, value)
    write_json(LOG_SCORES_PATH, value)


def fail(reason: str) -> None:
    write_scores({"reward": 0, "reason": reason})
    write_json(LOG_DIR / "details.json", {"ok": False, "reason": reason})


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


def read_out_json(process: subprocess.Popen[str]) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if OUT_PATH.exists():
            out = json.loads(OUT_PATH.read_text(encoding="utf-8"))
            return {
                "freeUrl": validate_url("freeUrl", out.get("freeUrl")),
                "paidUrl": validate_url("paidUrl", out.get("paidUrl")),
            }
        if process.poll() is not None:
            raise RuntimeError("server exited before writing out.json")
        time.sleep(0.1)
    raise RuntimeError("server did not write out.json within 30s")


def start_server() -> subprocess.Popen[str]:
    return subprocess.Popen(
        ["npm", "run", "--silent", "serve"],
        cwd=WORKSPACE,
        env={**os.environ, "MPP_SECRET_KEY": MPP_SECRET_KEY},
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        start_new_session=True,
        text=True,
    )


def fund_account(address: str) -> None:
    tx_hashes = rpc("tempo_fundAddress", [address])
    write_json(LOG_DIR / "faucet.json", {"address": address, "hashes": tx_hashes})
    for tx_hash in tx_hashes:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if rpc("eth_getTransactionReceipt", [tx_hash]):
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
    transaction = rpc("eth_getTransactionByHash", [reference])
    receipt = rpc("eth_getTransactionReceipt", [reference])
    if not isinstance(transaction, dict):
        raise RuntimeError("payment receipt reference was not a transaction hash")
    if not isinstance(receipt, dict):
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
    if not proof["chainMatches"]:
        raise RuntimeError(f"payment transaction used chain {proof['chainId']}")
    if not proof["fromMatchesPayer"]:
        raise RuntimeError("payment transaction payer mismatch")
    if not proof["successful"]:
        raise RuntimeError("payment transaction was not successful")
    if not proof["transfer"]["found"]:
        raise RuntimeError("payment transaction did not transfer to recipient")
    if not proof["transfer"]["amountMatchesCharge"]:
        raise RuntimeError("payment transaction amount mismatch")
    return proof


async def paid_request(url: str) -> dict:
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
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(f"paid request returned {response.status_code}")
    if not receipt_header:
        raise RuntimeError("paid response did not include Payment-Receipt")
    response.json()
    receipt = Receipt.from_payment_receipt(receipt_header)
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


async def main() -> None:
    process = None
    keep_process = False
    try:
        process = start_server()
        out = read_out_json(process)
        paid = await paid_request(out["paidUrl"])
        write_scores(
            {
                "reward": 1,
                "out": out,
                "server": {"pid": process.pid, "processGroupId": process.pid},
                "paid": paid,
            }
        )
        write_json(LOG_DIR / "details.json", {"ok": True, **out})
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
