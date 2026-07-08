"""Shared Tempo testnet verifier helpers.

SYNCED FROM shared/tempo-testnet/tests/support/client_lib.py BY npm run sync.
Task-specific checks live in sibling client.py files.
"""

import json
import os
import re
import secrets
import subprocess
import time
from decimal import Decimal
from pathlib import Path

import httpx
from eth_utils import keccak, to_hex
from mpp.methods.tempo import TempoAccount

WORKSPACE = Path(os.environ.get("TEMPO_BENCH_WORKSPACE", "/app"))
LOG_DIR = Path(os.environ.get("TEMPO_BENCH_LOG_DIR", "/logs/verifier"))
OUT_PATH = WORKSPACE / "out.json"
SCORES_PATH = WORKSPACE / "scores.json"
LOG_SCORES_PATH = LOG_DIR / "scores.json"

RPC_URL = os.environ.get("TEMPO_TESTNET_RPC_URL", "https://rpc.moderato.tempo.xyz")
CHAIN_ID = 42431
CHAIN_ID_HEX = hex(CHAIN_ID)
TOKEN = os.environ.get(
    "TEMPO_TESTNET_TOKEN", "0x20c0000000000000000000000000000000000000"
)
RECIPIENT = os.environ.get(
    "TEMPO_TESTNET_RECIPIENT", "0x1111111111111111111111111111111111111111"
)
AMOUNT = Decimal(os.environ.get("TEMPO_TESTNET_AMOUNT", "0.01"))
DECIMALS = int(os.environ.get("TEMPO_TESTNET_DECIMALS", "6"))
TRANSFER_WITH_MEMO_TOPIC = to_hex(
    keccak(text="TransferWithMemo(address,address,uint256,bytes32)")
)


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
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / "verifier-events.ndjson").open("a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")


def fail(reason: str) -> None:
    log_event("fail", reason=reason)
    score = {"reward": 0, "reason": reason}
    write_scores(score)
    write_json(LOG_DIR / "details.json", {"ok": False, **score})


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


def new_private_key() -> str:
    return f"0x{secrets.token_hex(32)}"


def account_from_key(private_key: str) -> TempoAccount:
    return TempoAccount.from_key(private_key)


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


def run_submission(env: dict[str, str]) -> dict:
    OUT_PATH.unlink(missing_ok=True)
    timeout = int(os.environ.get("TEMPO_BENCH_SUBMISSION_TIMEOUT_MS", "180000")) / 1000
    result = subprocess.run(
        ["npm", "run", "--silent", "run"],
        cwd=WORKSPACE,
        env={**os.environ, **env},
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    payload = {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    write_json(LOG_DIR / "submission-run.json", payload)
    log_event(
        "submission_run_exit",
        returncode=result.returncode,
        stderrTail=result.stderr[-1000:],
        stdoutTail=result.stdout[-1000:],
    )
    if result.returncode != 0:
        raise RuntimeError(f"submission run failed: {result.stderr.strip()}")
    return payload


def read_transfer_out_json() -> dict:
    if not OUT_PATH.exists():
        raise RuntimeError("submission did not write /app/out.json")

    try:
        out = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise RuntimeError("submission wrote invalid /app/out.json") from exc

    if not isinstance(out, dict) or set(out) != {"transactionHash"}:
        raise RuntimeError("out.json must contain only transactionHash")

    tx_hash = out.get("transactionHash")
    if not isinstance(tx_hash, str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}", tx_hash):
        raise RuntimeError("out.json transactionHash must be a 32-byte hex hash")

    write_json(LOG_DIR / "submission-output.json", out)
    log_event("out_json", transactionHash=tx_hash)
    return out


def wait_for_rpc_result(method: str, params: list, name: str) -> dict:
    deadline = (
        time.monotonic()
        + int(os.environ.get("TEMPO_BENCH_LOG_WAIT_MS", "120000")) / 1000
    )
    while time.monotonic() < deadline:
        result = rpc(method, params)
        if isinstance(result, dict):
            return result
        time.sleep(1)
    raise RuntimeError(f"{name} was not found")


def normalize_address(address: str | None) -> str | None:
    return address.lower() if isinstance(address, str) else None


def same_address(left: str | None, right: str | None) -> bool:
    return normalize_address(left) == normalize_address(right)


def topic_address(address: str) -> str:
    return f"0x{'0' * 24}{address.removeprefix('0x').lower()}"


def memo_topics(memo: str) -> set[str]:
    raw = memo.encode("utf-8")
    if len(raw) > 32:
        raise RuntimeError("TEMPO_MEMO must fit in bytes32")
    zero = b"\x00"
    return {
        f"0x{raw.ljust(32, zero).hex()}",
        f"0x{raw.rjust(32, zero).hex()}",
    }


def amount_data(amount: Decimal, decimals: int) -> str:
    base_units = int(amount * (Decimal(10) ** decimals))
    return f"0x{base_units:064x}"


def chain_matches(value: object) -> bool:
    if isinstance(value, str):
        return int(value, 16) == CHAIN_ID
    if isinstance(value, int):
        return value == CHAIN_ID
    return False


def verify_transfer_with_memo(
    *,
    transaction_hash: str,
    payer: str,
    recipient: str,
    token: str,
    amount: Decimal,
    decimals: int,
    memo: str,
) -> dict:
    transaction = wait_for_rpc_result(
        "eth_getTransactionByHash", [transaction_hash], "transaction"
    )
    receipt = wait_for_rpc_result(
        "eth_getTransactionReceipt", [transaction_hash], "transaction receipt"
    )
    write_json(LOG_DIR / "transaction.json", transaction)
    write_json(LOG_DIR / "receipt.json", receipt)

    payer_topic = topic_address(payer)
    recipient_topic = topic_address(recipient)
    expected_amount = amount_data(amount, decimals)
    expected_memos = memo_topics(memo)
    transfer_candidates = []
    matching_log = None

    for log in receipt.get("logs", []):
        topics = [topic.lower() for topic in log.get("topics", [])]
        if normalize_address(log.get("address")) != normalize_address(token):
            continue
        if not topics or topics[0] != TRANSFER_WITH_MEMO_TOPIC.lower():
            continue

        candidate = {
            "address": normalize_address(log.get("address")),
            "amount": str(log.get("data", "")).lower(),
            "from": topics[1] if len(topics) > 1 else None,
            "memo": topics[3] if len(topics) > 3 else None,
            "to": topics[2] if len(topics) > 2 else None,
        }
        transfer_candidates.append(candidate)
        if (
            candidate["from"] == payer_topic
            and candidate["to"] == recipient_topic
            and candidate["amount"] == expected_amount
            and candidate["memo"] in {item.lower() for item in expected_memos}
        ):
            matching_log = candidate

    proof = {
        "chainId": transaction.get("chainId"),
        "chainMatches": chain_matches(transaction.get("chainId")),
        "expected": {
            "amount": expected_amount,
            "memoTopics": sorted(expected_memos),
            "payer": normalize_address(payer),
            "recipient": normalize_address(recipient),
            "token": normalize_address(token),
        },
        "from": normalize_address(transaction.get("from")),
        "fromMatchesPayer": same_address(transaction.get("from"), payer),
        "hash": transaction.get("hash"),
        "receiptStatus": receipt.get("status"),
        "receiptStatusIsSuccess": receipt.get("status") == "0x1",
        "receiptTransactionHash": receipt.get("transactionHash"),
        "receiptTransactionHashMatchesReference": receipt.get("transactionHash")
        == transaction_hash,
        "referenceMatchesHash": transaction.get("hash") == transaction_hash,
        "transfer": {
            "candidates": transfer_candidates,
            "found": matching_log is not None,
            "match": matching_log,
        },
    }

    def raise_failure(reason: str) -> None:
        failure = {"reason": reason, "proof": proof}
        write_json(LOG_DIR / "transfer-with-memo-proof.json", proof)
        write_json(LOG_DIR / "transfer-with-memo-failure.json", failure)
        raise RuntimeError(reason)

    write_json(LOG_DIR / "transfer-with-memo-proof.json", proof)
    log_event(
        "transfer_with_memo_proof",
        hash=transaction_hash,
        transferFound=proof["transfer"]["found"],
        transferCandidates=len(transfer_candidates),
    )
    if not proof["referenceMatchesHash"]:
        raise_failure("transaction hash mismatch")
    if not proof["receiptTransactionHashMatchesReference"]:
        raise_failure("receipt transaction hash mismatch")
    if not proof["chainMatches"]:
        raise_failure(f"transaction used chain {proof['chainId']}")
    if not proof["fromMatchesPayer"]:
        raise_failure("transaction sender mismatch")
    if not proof["receiptStatusIsSuccess"]:
        raise_failure("transaction receipt was not successful")
    if not proof["transfer"]["found"]:
        raise_failure("matching TransferWithMemo event was not found")
    return proof
