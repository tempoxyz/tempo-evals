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
        for always_fail in (False, True):
            with (
                self.subTest(always_fail=always_fail),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                fake = root / "tsx"
                fake.write_text(
                    '#!/bin/sh\nprintf x >> "$COLLECTION_COUNT"\n'
                    'if [ "$FAIL_ALWAYS" = 1 ] || '
                    '[ "$(cat "$COLLECTION_COUNT")" = x ]; then exit 1; fi\n'
                    'printf \'{"trusted":true}\' > "$COLLECTION_OUTPUT"\n'
                )
                fake.chmod(0o700)
                result = subprocess.run(
                    ["sh", "-c", command],
                    env={
                        "PATH": str(root) + ":" + os.defpath,
                        "COLLECTION_COUNT": str(root / "count"),
                        "COLLECTION_OUTPUT": str(root / "snapshot.json"),
                        "FAIL_ALWAYS": str(int(always_fail)),
                    },
                    capture_output=True,
                    timeout=5,
                )
                self.assertEqual((root / "count").read_text(), "xx")
                self.assertEqual(result.returncode, int(always_fail))
                self.assertEqual((root / "snapshot.json").exists(), not always_fail)

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
                        {"id": order_id, "shipping": copy.deepcopy(verifier.EXPECTED)}
                    ]
                    self.assertTrue(verifier.check(paid)[0])
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
                        [{"id": "another-order", "shipping": verifier.EXPECTED}],
                        paid["shippingOrders"] * 2,
                    ):
                        wrong = copy.deepcopy(paid)
                        wrong["shippingOrders"] = value
                        self.assertFalse(verifier.check(wrong)[0])
                    missing = copy.deepcopy(paid)
                    del missing["shippingOrders"][0]["shipping"]["line2"]
                    self.assertFalse(verifier.check(missing)[0])
                    unpaid = copy.deepcopy(paid)
                    for key in ("sessions", "intents", "orders", "deliveries"):
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

    def test_shipping_is_shared_by_the_ten_default_tasks(self):
        pairs = sync_shared.TASKS_CONFIG["checkout"]["directed"]
        expected = set(pairs) | {peer["task"] for peer in pairs.values()}
        tasks = sync_shared.checkout_task_dirs()
        self.assertEqual({p.name for p in tasks}, expected)
        self.assertEqual(len(tasks), 10)
        for task in tasks:
            with self.subTest(task=task.name):
                self.assertNotIn("shipping", task.name)
                for source, target in (
                    ("merchant.js", "environment/merchant/shipping.js"),
                    ("oracle.ts", "solution/shipping.ts"),
                    ("address.json", "solution/shipping.json"),
                    ("address.json", "tests/shipping.json"),
                    ("check.py", "tests/check.py"),
                ):
                    self.assertEqual(
                        (task / target).read_bytes(), (SHARED / source).read_bytes()
                    )
                instruction = (task / "instruction.md").read_text()
                self.assertIn("including the apartment", instruction)
                for field, value in json.loads(
                    (SHARED / "address.json").read_text()
                ).items():
                    self.assertIn(f"- {field}: {value}", instruction)
                self.assertFalse((task / "environment/merchant/shipping.json").exists())
