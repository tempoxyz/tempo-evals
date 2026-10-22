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
    text = server.read_text()
    text = (
        (
            "import { createShipping } from './shipping.js';\n"
            "const shipping = createShipping('"
        )
        + ("/buy" if mpp else "/checkout")
        + "');\n"
        + text
    )
    text = replace_once(
        text,
        "http.createServer(async (request, response) => {",
        (
            "http.createServer(async (request, response) => {\n  if "
            "(await shipping.handle(request, response)) return;"
        ),
    )
    if not mpp:
        if name != "paypal":
            text = replace_once(
                text,
                "request.url === '/checkout' && request.method === 'POST'",
                (
                    "new URL(request.url, 'http://merchant:3000').pathname "
                    "=== '/checkout' && ['GET', "
                    "'POST'].includes(request.method)"
                ),
            )
        else:
            text = replace_once(
                text,
                "path === '/checkout' && request.method === 'POST'",
                "path === '/checkout' && ['GET', 'POST'].includes(request.method)",
            )
        text = replace_once(
            text,
            "const orderId = randomUUID();",
            (
                "const shippingOrder = shipping.get(request);\n    if "
                "(!shippingOrder) return "
                "response.writeHead(400).end('Submit a shipping address "
                "first');\n    const orderId = shippingOrder.id;"
            ),
        )
        text = text.replace("import { randomUUID } from 'node:crypto';\n", "")
        if name == "stripe-card":
            text = re.sub(
                r"  if \(request.url\?\.startsWith\('/complete'\).*?\n  }",
                (
                    "  if (request.url?.startsWith('/complete') && "
                    "request.method === 'GET') {\n    return "
                    "shipping.stripeReceipt(request, response, 'sessions');"
                    "\n  }"
                ),
                text,
                count=1,
                flags=re.S,
            )
        elif name == "stripe-link":
            text = text.replace(
                "function paymentPage(clientSecret)",
                "function paymentPage(clientSecret, orderId)",
            ).replace(
                "paymentPage(intent.client_secret)",
                "paymentPage(intent.client_secret, orderId)",
            )
            text = text.replace(
                "http://merchant:3000/complete'",
                "http://merchant:3000/complete?order_id=${orderId}'",
            ).replace(
                "location.href = '/complete';",
                "location.href = '/complete?order_id=${orderId}';",
            )
            text = re.sub(
                r"  if \(request.url\?\.startsWith\('/complete'\).*?\n  }",
                (
                    "  if (request.url?.startsWith('/complete') && "
                    "request.method === 'GET') {\n    return "
                    "shipping.stripeReceipt(request, response, 'intents');\n  "
                    "}"
                ),
                text,
                count=1,
                flags=re.S,
            )
        else:
            text = replace_once(
                text,
                ".some(line => JSON.parse(line).paypalOrderId === paypalOrderId)",
                (
                    ".map(line => JSON.parse(line)).find(row => row.paypalOrder"
                    "Id === paypalOrderId)"
                ),
            )
            text = replace_once(
                text,
                "{ location: '/complete' }",
                "{ location: `/complete?order_id=${known.orderId}` }",
            )
            text = re.sub(
                r"  if \(path === '/complete'\) \{.*?\n  }",
                (
                    "  if (path === '/complete') {\n    return "
                    "shipping.paypalReceipt(request, response, paypal);\n  }"
                ),
                text,
                count=1,
                flags=re.S,
            )
    elif name == "mpp-card":
        text = replace_once(
            text,
            "const charge = mppx.stripe.charge({",
            "const charge = (orderId: string) => mppx.stripe.charge({",
        )
        text = replace_once(
            text,
            "const paid = await charge(ServerRequest",
            (
                "const shippingOrder = shipping.get(request);\n      if "
                "(!shippingOrder) return "
                "response.writeHead(400).end('Submit a shipping address "
                "first');\n      const orderId = shippingOrder.id;\n      "
                "const paid = await charge(orderId)(ServerRequest"
            ),
        )
        text = replace_once(
            text,
            "const order = { orderId,",
            "const order = { orderId, shipping: shippingOrder.shipping,",
        )
    else:
        text = replace_once(
            text,
            "const proxy = Proxy.create({",
            "const proxy = (orderId: string) => Proxy.create({",
        )
        text = replace_once(
            text,
            "description: 'Tempo Notebook' })",
            "description: 'Tempo Notebook', scope: orderId })",
        )
        text = replace_once(
            text,
            "request.url !== '/deliver'",
            (
                "new URL(request.url || '/', 'http://merchant:3000').pathna"
                "me !== '/deliver'"
            ),
        )
        text = replace_once(
            text,
            "orderId: randomUUID(),",
            (
                "orderId: new URL(request.url || '/', "
                "'http://merchant:3000').searchParams.get('order_id'),"
            ),
        )
        text = replace_once(
            text,
            "const incoming = ServerRequest",
            (
                "const shippingOrder = shipping.get(request);\n      if "
                "(!shippingOrder) return "
                "response.writeHead(400).end('Submit a shipping address "
                "first');\n      const incoming = ServerRequest"
            ),
        )
        text = replace_once(
            text,
            (
                "await proxy.fetch(new Request('http://merchant:3000/notebo"
                "ok/deliver', incoming))"
            ),
            (
                "await proxy(shippingOrder.id).fetch(new Request(`http://"
                "merchant:3000/notebook/deliver?order_id=${shippingOrder."
                "id}`, incoming))"
            ),
        )
        text = text.replace("randomBytes, randomUUID", "randomBytes")
    server.write_text(text)
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
