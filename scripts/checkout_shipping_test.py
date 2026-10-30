from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sync_shared

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared/checkout/shipping"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CheckoutShippingTest(unittest.TestCase):
    def test_collection_retries_read_only_evidence_without_replaying_the_agent(self):
        task = ROOT / "tasks/checkout-v1/paypal-discover/task.toml"
        command = tomllib.loads(task.read_text())["verifier"]["collect"][0]["command"]
        for mode in ("recover", "hang", "fail"):
            with (
                self.subTest(mode=mode),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                fake = root / "tsx"
                fake.write_text(
                    '#!/bin/sh\nprintf x >> "$COLLECTION_COUNT"\n'
                    'if [ "$FAIL_ALWAYS" = 1 ]; then exit 1; fi\n'
                    'if [ "$(cat "$COLLECTION_COUNT")" = x ]; then\n'
                    '  if [ "$COLLECTION_HANG" = 1 ]; then exec sleep 10; fi\n'
                    "  exit 1\nfi\n"
                    'printf \'{"trusted":true}\' > "$COLLECTION_OUTPUT"\n'
                )
                fake.chmod(0o700)
                # Shorten the container's GNU timeout for this host-only test.
                bound = root / "timeout"
                bound.write_text(
                    "#!/usr/bin/env python3\nimport subprocess, sys\n"
                    "try:\n"
                    "    result = subprocess.run(sys.argv[4:], timeout=1)\n"
                    "    sys.exit(result.returncode)\n"
                    "except subprocess.TimeoutExpired:\n    sys.exit(124)\n"
                )
                bound.chmod(0o700)
                result = subprocess.run(
                    ["sh", "-c", command],
                    env={
                        "PATH": str(root)
                        + ":"
                        + str(Path(sys.executable).parent)
                        + ":"
                        + os.defpath,
                        "COLLECTION_COUNT": str(root / "count"),
                        "COLLECTION_OUTPUT": str(root / "snapshot.json"),
                        "FAIL_ALWAYS": str(int(mode == "fail")),
                        "COLLECTION_HANG": str(int(mode == "hang")),
                    },
                    capture_output=True,
                    timeout=8,
                )
                self.assertEqual((root / "count").read_text(), "xx", result.stderr)
                self.assertEqual(result.returncode, int(mode == "fail"))
                self.assertEqual((root / "snapshot.json").exists(), mode != "fail")

    def test_each_payment_adapter_requires_the_paid_orders_exact_address(self):
        for slug in sync_shared.TASKS_CONFIG["checkout"]["directed"]:
            with self.subTest(merchant=slug):
                source = ROOT / "tasks/checkout-v1" / slug
                original_path = sys.path[:]
                try:
                    sys.path.insert(0, str(source / "tests"))
                    payment_check = load(
                        source / "tests/payment_check.py", "shipping_payment_check"
                    )
                    with patch.dict(sys.modules, {"payment_check": payment_check}):
                        fixture = load(
                            source / "tests/check_test.py", "shipping_fixture"
                        )
                        verifier = load(source / "tests/check.py", "shipping_check")
                    paid = copy.deepcopy(fixture.PAID)
                    collection = {
                        "stripe-card-discover": "sessions",
                        "stripe-link-discover": "intents",
                        "paypal-discover": "orders",
                    }.get(slug)
                    if collection:
                        paid = {collection: [paid]}
                    order_id = verifier.paid_order_id(paid)
                    self.assertTrue(order_id)
                    paid["shippingOrders"] = [
                        {
                            "id": order_id,
                            "shipping": copy.deepcopy(verifier.EXPECTED),
                            "description": "Tempo Notebook",
                            "total": verifier.EXPECTED_ORDER["total"],
                        }
                    ]
                    self.assertTrue(verifier.check(paid)[0])
                    # The paid order must record the merchant's own price.
                    mispriced = copy.deepcopy(paid)
                    mispriced["shippingOrders"][0]["total"] += 100
                    self.assertEqual(
                        verifier.check(mispriced), (False, "order_mismatch", None)
                    )
                    for field in verifier.EXPECTED:
                        wrong = copy.deepcopy(paid)
                        wrong["shippingOrders"][0]["shipping"][field] = "wrong"
                        self.assertEqual(
                            verifier.check(wrong),
                            (False, "shipping_address_mismatch", None),
                        )
                        self.assertEqual(
                            verifier.shipping_details(wrong)[
                                "shipping_mismatched_fields"
                            ],
                            [field],
                        )
                    for value in (
                        [],
                        [
                            {
                                "id": "another-order",
                                "shipping": verifier.EXPECTED,
                                "total": verifier.EXPECTED_ORDER["total"],
                            }
                        ],
                        paid["shippingOrders"] * 2,
                    ):
                        wrong = copy.deepcopy(paid)
                        wrong["shippingOrders"] = value
                        self.assertFalse(verifier.check(wrong)[0])
                    missing = copy.deepcopy(paid)
                    del missing["shippingOrders"][0]["shipping"]["line2"]
                    self.assertFalse(verifier.check(missing)[0])
                    unpaid = copy.deepcopy(paid)
                    for key in (
                        "sessions",
                        "intents",
                        "orders",
                        "deliveries",
                        "transactions",
                    ):
                        if key in unpaid:
                            unpaid[key] = []
                    self.assertFalse(verifier.check(unpaid)[0])
                    normalized = copy.deepcopy(paid)
                    normalized["shippingOrders"][0]["shipping"]["name"] = (
                        "  AVERY   CHEN "
                    )
                    self.assertTrue(verifier.check(normalized)[0])
                    with tempfile.TemporaryDirectory() as directory:
                        directory = Path(directory)
                        snapshot = directory / "snapshot.json"
                        snapshot.write_text(json.dumps(missing))
                        with (
                            patch.object(verifier, "SNAPSHOT", snapshot),
                            patch.object(verifier, "LOG_DIR", directory),
                        ):
                            verifier.main()
                        self.assertEqual(
                            json.loads((directory / "reward.json").read_text()),
                            {"reward": 0},
                        )
                        details = json.loads((directory / "details.json").read_text())
                        self.assertEqual(details["reason"], "shipping_address_mismatch")
                finally:
                    sys.path[:] = original_path

    def test_cart_tasks_require_the_requested_cart_and_its_payment(self):
        order = json.loads((SHARED.parent / "cart/order.json").read_text())
        address = json.loads((SHARED / "address.json").read_text())

        def payment(slug, total, description):
            if slug == "stripe-card-discover":
                return {
                    "sessions": [
                        {
                            "orderId": "order-1",
                            "id": "cs_test_one",
                            "livemode": False,
                            "clientReferenceId": "order-1",
                            "metadataOrderId": "order-1",
                            "status": "complete",
                            "paymentStatus": "paid",
                            "amountTotal": total,
                            "currency": "usd",
                            "paymentIntent": {
                                "id": "pi_one",
                                "status": "succeeded",
                                "amount": total,
                                "amountReceived": total,
                                "currency": "usd",
                                "paymentMethodType": "card",
                            },
                            "items": [
                                {
                                    "description": description,
                                    "quantity": 1,
                                    "amountTotal": total,
                                    "currency": "usd",
                                }
                            ],
                        }
                    ]
                }
            if slug == "mpp-ousd-discover":
                return {
                    "recipient": "0x" + "1" * 40,
                    "ousd": "0x20c0000000000000000000006a37DA5C996874BE",
                    "decimals": 6,
                    "balance": str(total * 10**4),
                    "deliveries": [
                        {
                            "orderId": "order-1",
                            "item": description,
                            "quantity": 1,
                            "amount": f"{total / 100:.2f}",
                            "currency": "USD",
                            "receiptStatus": "success",
                            "receiptMethod": "tempo",
                        }
                    ],
                }
            # Other rails: their single-notebook fixture with the cart's
            # description and total in place of the notebook's.
            source = ROOT / "tasks/checkout-v1" / slug / "tests"
            original_path = sys.path[:]
            try:
                sys.path.insert(0, str(source))
                checker = load(source / "payment_check.py", "cart_fixture_check")
                with patch.dict(sys.modules, {"payment_check": checker}):
                    fixture = load(source / "check_test.py", "cart_fixture")
            finally:
                sys.path[:] = original_path

            # The source's own price, such as x402's $1.00 in USDC base units.
            price = json.loads((source / "order.json").read_text())["total"]

            def swap(value):
                if isinstance(value, dict):
                    return {key: swap(item) for key, item in value.items()}
                if isinstance(value, list):
                    return [swap(item) for item in value]
                if value == price and type(value) is int:
                    return total
                if value == f"{price / 100:.2f}":
                    return f"{total / 100:.2f}"
                if value == str(price * 10_000):
                    return str(total * 10_000)
                if value == f"{price / 100:g}":
                    return f"{total / 100:g}"
                if value == "Tempo Notebook":
                    return description
                return value

            paid = swap(copy.deepcopy(fixture.PAID))
            collection = {
                "stripe-link-discover": "intents",
                "paypal-discover": "orders",
            }.get(slug)
            return {collection: [paid]} if collection else paid

        def snapshot(slug, lines, option, total, description, paid=None):
            charged = payment(slug, total if paid is None else paid, description)
            return {
                **charged,
                "shippingOrders": [
                    {
                        # verifier is the cart task's check module, set below.
                        "id": verifier.paid_order_id(charged),
                        "shipping": address,
                        "lines": lines,
                        "shippingOption": option,
                        "total": total,
                        "description": description,
                    }
                ],
            }

        for slug, target in sync_shared.TASKS_CONFIG["checkout"]["cart"].items():
            with self.subTest(task=target):
                tests = ROOT / "tasks/checkout-v1" / target / "tests"
                original_path = sys.path[:]
                try:
                    sys.path.insert(0, str(tests))
                    payment_check = load(tests / "payment_check.py", "cart_payment")
                    with patch.dict(sys.modules, {"payment_check": payment_check}):
                        verifier = load(tests / "check.py", "cart_check")
                    good = snapshot(
                        slug,
                        order["lines"],
                        "standard",
                        order["total"],
                        order["description"],
                    )
                    self.assertTrue(verifier.check(good)[0])
                    express = snapshot(
                        slug,
                        order["lines"],
                        "express",
                        4300,
                        order["description"].replace("Standard", "Express"),
                    )
                    a4 = [
                        {"sku": "notebook-a4-dotted", "quantity": 2},
                        order["lines"][1],
                    ]
                    one = [{**order["lines"][0], "quantity": 1}, order["lines"][1]]
                    for wrong, fields in (
                        (express, ["total", "shippingOption"]),
                        (snapshot(slug, a4, "standard", 3700, "x"), ["total", "lines"]),
                        (
                            snapshot(slug, one, "standard", 2100, "x"),
                            ["total", "lines"],
                        ),
                    ):
                        self.assertEqual(
                            verifier.check(wrong), (False, "order_mismatch", None)
                        )
                        self.assertEqual(
                            verifier.order_details(wrong)["order_mismatched_fields"],
                            fields,
                        )
                    underpaid = snapshot(
                        slug,
                        order["lines"],
                        "standard",
                        order["total"],
                        order["description"],
                        paid=1200,
                    )
                    self.assertFalse(verifier.check(underpaid)[0])
                    if slug in {"braintree-card-discover", "shopify-card-discover"}:
                        # These payments carry an amount but no description.
                        continue
                    renamed = {
                        **payment(slug, order["total"], "Tempo Notebook"),
                        "shippingOrders": good["shippingOrders"],
                    }
                    self.assertFalse(verifier.check(renamed)[0])
                finally:
                    sys.path[:] = original_path

    def test_x402_pair_expects_its_one_dollar_order(self):
        for slug in (
            "x402-usdc-discover",
            "x402-usdc-directed",
            "x402usdc-prepared-discover",
            "x402usdc-prepared-directed",
        ):
            with self.subTest(task=slug):
                task = ROOT / "tasks/checkout-v1" / slug
                for target in ("solution/order.json", "tests/order.json"):
                    self.assertEqual(
                        json.loads((task / target).read_text())["total"], 100
                    )
                server = (task / "environment/merchant/server.ts").read_text()
                self.assertIn("const total = 100;", server)
                self.assertIn("createShipping('/buy', { total })", server)

    def test_shipping_is_shared_by_all_checkout_tasks(self):
        pairs = sync_shared.TASKS_CONFIG["checkout"]["directed"]
        expected = set(pairs) | {peer["task"] for peer in pairs.values()}
        tasks = sync_shared.checkout_task_dirs()
        expected |= set(sync_shared.TASKS_CONFIG["checkout"]["prepared"].values())
        carts = set(sync_shared.TASKS_CONFIG["checkout"]["cart"].values())
        expected |= carts
        self.assertEqual({p.name for p in tasks}, expected)
        for task in tasks:
            with self.subTest(task=task.name):
                self.assertNotIn("shipping", task.name)
                store = SHARED.parent / ("cart" if task.name in carts else "shipping")
                for directory, source, target in (
                    (store, "merchant.js", "environment/merchant/shipping.js"),
                    (store, "oracle.ts", "solution/shipping.ts"),
                    (SHARED, "address.json", "solution/shipping.json"),
                    (SHARED, "address.json", "tests/shipping.json"),
                    (SHARED, "check.py", "tests/check.py"),
                ):
                    self.assertEqual(
                        (task / target).read_bytes(),
                        (directory / source).read_bytes(),
                    )
                order = json.loads((store / "order.json").read_text())
                total = sync_shared.CHECKOUT_ORDER_TOTALS.get(task.name)
                if total is not None:
                    order["total"] = total
                for target in ("solution/order.json", "tests/order.json"):
                    self.assertEqual(json.loads((task / target).read_text()), order)
                instruction = (task / "instruction.md").read_text()
                self.assertIn("including the apartment", instruction)
                for field, value in json.loads(
                    (SHARED / "address.json").read_text()
                ).items():
                    self.assertIn(f"- {field}: {value}", instruction)
                self.assertFalse((task / "environment/merchant/shipping.json").exists())
