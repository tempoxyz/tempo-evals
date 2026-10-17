"""Create one trial-local Tempo payer and sandbox payment inventory."""

import json
import os
import secrets
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from eth_account import Account

RPC = os.environ.get("TEMPO_RPC_URL", "https://rpc.moderato.tempo.xyz")
LINK_EMAIL = f"tempo-checkout-{uuid.uuid4().hex}@example.com"
AREA_CODES = [
    "202",
    "206",
    "212",
    "213",
    "214",
    "215",
    "216",
    "305",
    "310",
    "312",
    "313",
    "415",
    "617",
    "646",
    "650",
    "703",
    "718",
    "781",
    "818",
    "925",
]
LINK_PHONE = f"{secrets.choice(AREA_CODES)}55501{secrets.randbelow(100):02d}"


def rpc(method: str, params: list) -> object:
    request = Request(
        RPC,
        data=json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        ).encode(),
        headers={
            "content-type": "application/json",
            "user-agent": "tempo-evals-checkout/1.0",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload["result"]


account = Account.create()
hashes = rpc("tempo_fundAddress", [account.address])
if not isinstance(hashes, list) or not hashes:
    raise RuntimeError("Tempo testnet funding did not return transactions")
for tx_hash in hashes:
    for _attempt in range(30):
        receipt = rpc("eth_getTransactionReceipt", [tx_hash])
        if receipt:
            if receipt.get("status") != "0x1":
                raise RuntimeError("Tempo testnet funding failed")
            break
        time.sleep(2)
    else:
        raise TimeoutError("Tempo testnet funding was not confirmed")

year = datetime.now(UTC).year + 3
wallet = {
    "tempo": {
        "chainId": 42431,
        "rpcUrl": RPC,
        "address": account.address,
        "privateKey": "0x" + account.key.hex().removeprefix("0x"),
    },
    "card": {
        "number": "4242424242424242",
        "expMonth": "12",
        "expYear": str(year),
        "cvc": "123",
    },
    "link": {
        "email": LINK_EMAIL,
        "phone": LINK_PHONE,
        "sandboxPasscode": "000000",
    },
}
path = Path("/wallet/wallet.json")
path.write_text(json.dumps(wallet, indent=2) + "\n")
path.chmod(0o444)
print("Trial wallet funded and ready", flush=True)
