# SYNCED FROM shared/checkout/wallet/init.py BY npm run sync. DO NOT EDIT COPIES.
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
# Decline tasks set a provider test card that declines as the primary card; the
# backup card is then the card every other task lists as primary.
DECLINED_CARD = os.environ.get("DECLINED_CARD_NUMBER", "")
# Underfunded tasks hold exactly this much OUSD (6 decimals) and nothing else on
# Tempo; every other task gets the faucet's full funding.
PAYER_OUSD = os.environ.get("TEMPO_PAYER_OUSD_UNITS", "")
OUSD = "0x20c0000000000000000000006a37DA5C996874BE"
BASE_SEPOLIA_RPC = os.environ.get("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org")
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


def confirm(tx_hash: str) -> None:
    for _attempt in range(30):
        receipt = rpc("eth_getTransactionReceipt", [tx_hash])
        if receipt:
            if receipt.get("status") != "0x1":
                raise RuntimeError("Tempo testnet funding failed")
            return
        time.sleep(2)
    raise TimeoutError("Tempo testnet funding was not confirmed")


def fund(address: str) -> None:
    hashes = rpc("tempo_fundAddress", [address])
    if not isinstance(hashes, list) or not hashes:
        raise RuntimeError("Tempo testnet funding did not return transactions")
    for tx_hash in hashes:
        confirm(tx_hash)


def word(value: int) -> str:
    """One 32-byte ABI argument."""
    return f"{value:064x}"


def ousd_balance(address: str) -> int:
    data = "0x70a08231" + word(int(address, 16))
    return int(str(rpc("eth_call", [{"to": OUSD, "data": data}, "latest"])), 16)


def fund_exactly(address: str, units: int) -> None:
    """Send exactly units of OUSD from a separate faucet-funded account.

    The payer receives nothing else, so all it can spend is that OUSD; Tempo
    takes the fee for an OUSD transfer in OUSD, so it can still send one.
    """
    funder = Account.create()
    fund(funder.address)
    data = "0xa9059cbb" + word(int(address, 16)) + word(units)
    call = {"from": funder.address, "to": OUSD, "data": data}
    gas_price = int(str(rpc("eth_gasPrice", [])), 16)
    transaction = {
        "type": 2,
        "chainId": 42431,
        "nonce": int(
            str(rpc("eth_getTransactionCount", [funder.address, "pending"])), 16
        ),
        "to": OUSD,
        "data": data,
        "value": 0,
        "gas": 2 * int(str(rpc("eth_estimateGas", [call])), 16),
        "maxFeePerGas": 2 * gas_price,
        "maxPriorityFeePerGas": 0,
    }
    signed = Account.sign_transaction(transaction, funder.key)
    raw = "0x" + signed.raw_transaction.hex().removeprefix("0x")
    confirm(str(rpc("eth_sendRawTransaction", [raw])))
    if ousd_balance(address) != units:
        raise RuntimeError("Tempo testnet payer balance is not the funded amount")


account = Account.create()
if PAYER_OUSD:
    fund_exactly(account.address, int(PAYER_OUSD))
else:
    fund(account.address)

year = datetime.now(UTC).year + 3
wallet = {
    "tempo": {
        "chainId": 42431,
        "rpcUrl": RPC,
        "address": account.address,
        "privateKey": "0x" + account.key.hex().removeprefix("0x"),
    },
    # The same key controls a Base Sepolia account. It is listed in every
    # task so the wallet does not reveal which merchant accepts x402.
    "baseSepolia": {
        "chainId": 84532,
        "rpcUrl": BASE_SEPOLIA_RPC,
        "address": account.address,
        "privateKey": "0x" + account.key.hex().removeprefix("0x"),
    },
    # A test Mastercard both Stripe (test mode) and the Braintree sandbox
    # accept, so every task lists the same card and none reveals its merchant.
    # Decline tasks replace it with a test card their provider declines.
    "card": {
        "number": DECLINED_CARD or "5555555555554444",
        "expMonth": "12",
        "expYear": str(year),
        "cvc": "123",
    },
    # Every wallet has a second card both providers accept: a test Discover
    # card, or the Mastercard when the primary card declines.
    "backupCard": {
        "number": "5555555555554444" if DECLINED_CARD else "6011111111111117",
        "expMonth": "12",
        "expYear": str(year),
        "cvc": "123",
    },
    "paypal": {
        "email": os.environ.get("PAYPAL_SANDBOX_BUYER_EMAIL", ""),
        "password": os.environ.get("PAYPAL_SANDBOX_BUYER_PASSWORD", ""),
    },
    # Listed in every task so the wallet does not reveal the Shopify merchant.
    "storefront": {
        "password": os.environ["SHOPIFY_STOREFRONT_PASSWORD"],
        "testCard": {
            "number": "1",
            "name": "Bogus Gateway",
            "expMonth": "12",
            "expYear": str(year),
            "cvc": "123",
        },
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
