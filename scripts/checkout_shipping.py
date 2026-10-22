"""Generate additive shipping tasks using the existing merchant payment adapters."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

import tomlkit


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"Shipping overlay expected one occurrence of {old!r}")
    return text.replace(old, new, 1)


def generate(source: Path, target: Path, shared: Path) -> None:
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(
            "node_modules", "package-lock.json", "__pycache__", "*.pyc"
        ),
    )
    name = source.name.removesuffix("-discover")
    mpp = name.startswith("mpp-")
    config = tomlkit.parse((target / "task.toml").read_text())
    config["task"]["name"] = f"checkout-v1/{target.name}"
    config["task"]["description"] = (
        "Buy a notebook and supply the requested shipping address."
    )
    config["metadata"].update(
        scenario_id=f"checkout-v1/{target.name}",
        credential_scenario_id=f"checkout-v1/{source.name}",
        purchase_scenario="shipping",
    )
    config["metadata"]["verification_explanation"] += (
        " The paid order must contain every requested shipping field."
    )
    (target / "task.toml").write_text(tomlkit.dumps(config))
    address = json.loads((shared / "address.json").read_text())
    instruction = (source / "instruction.md").read_text()
    marker = uuid.uuid5(uuid.NAMESPACE_URL, str(config["task"]["name"]))
    instruction = re.sub(
        r"<!-- stable-bench-canary: [0-9a-f-]+ -->",
        f"<!-- stable-bench-canary: {marker} -->",
        instruction,
        count=1,
    )
    shipping = (
        "\nShip it to:\n\n"
        + "\n".join(f"- {key}: {value}" for key, value in address.items())
        + (
            "\n\nThe completed order must use this full shipping address,"
            " including the apartment.\n"
        )
    )
    instruction = replace_once(
        instruction,
        "Complete the purchase once.\n",
        "Complete the purchase once.\n" + shipping,
    )
    (target / "instruction.md").write_text(instruction)
    (target / "README.md").write_text(
        f"<!-- Generated from {source.name} and "
        "shared/checkout/shipping by npm run sync. -->\n"
        + (source / "README.md").read_text()
        + (
            "\n## Shipping requirement\n\nSubmit the task's recipient "
            "and full shipping address before payment. The separate "
            "verifier joins the provider-confirmed payment to the "
            "immutable merchant shipping order; incorrect or missing "
            "fields fail even after payment.\n"
        )
    )
    for src, dest in (
        ("merchant.js", "environment/merchant/shipping.js"),
        ("oracle.ts", "solution/shipping.ts"),
        ("address.json", "solution/shipping.json"),
        ("address.json", "tests/shipping.json"),
    ):
        shutil.copyfile(shared / src, target / dest)
    shutil.copyfile(source / "tests/check.py", target / "tests/payment_check.py")
    shutil.copyfile(shared / "check.py", target / "tests/check.py")
    # Original payment tests remain unchanged in their source tasks. New task
    # checks are covered by the shared shipping/payment regression cases.
    (target / "tests/check_test.py").unlink(missing_ok=True)
    merchant = target / "environment/merchant"
    server = merchant / ("server.ts" if mpp else "server.js")
    shutil.copyfile(shared / f"{name}{server.suffix}", server)
    docker = merchant / "Dockerfile"
    docker.write_text(
        docker.read_text()
        .replace(
            "COPY server.ts snapshot.ts ./", "COPY server.ts snapshot.ts shipping.js ./"
        )
        .replace(
            "COPY package.json server.js snapshot.ts ./",
            "COPY package.json server.js snapshot.ts shipping.js ./",
        )
    )
    snapshot = merchant / "snapshot.ts"
    text = "import { shippingOrders } from './shipping.js';\n" + snapshot.read_text()
    text = replace_once(
        text, "JSON.stringify({ ", "JSON.stringify({ shippingOrders: shippingOrders(), "
    )
    if name == "mpp-card":
        text = replace_once(
            text,
            "...merchant, payments,",
            "...merchant, orderId: deliveries[0]?.orderId, payments,",
        )
    snapshot.write_text(text)
    oracle = target / "solution/solve.ts"
    text = oracle.read_text()
    if not mpp:
        text = "import { shippingFormScript } from '/solution/shipping.ts';\n" + text
        text = replace_once(
            text,
            "await page.goto('http://merchant:3000');",
            "await page.goto('http://merchant:3000');\n  ${shippingFormScript}",
        )
        text = replace_once(
            text,
            "name: 'Pay with PayPal'" if name == "paypal" else "name: 'Buy notebook'",
            "name: 'Continue to payment'",
        )
    else:
        text = "import { createShippingOrder } from '/solution/shipping.ts';\n" + text
        text = replace_once(
            text,
            "async function main() {",
            (
                "async function main() {\n  const shippingOrder = await crea"
                "teShippingOrder();"
            ),
        )
        text = replace_once(
            text,
            "mppx.fetch(process.argv[2] || 'http://merchant:3000/buy'"
            if name == "mpp-card"
            else "mppx.fetch(url",
            "mppx.fetch(shippingOrder.paymentUrl",
        )
    oracle.write_text(text)
