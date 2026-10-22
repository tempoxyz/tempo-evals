from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sync_shared
from scripts.checkout_shipping import generate

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared/checkout/shipping"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CheckoutShippingTest(unittest.TestCase):
    def test_each_payment_adapter_requires_the_paid_orders_exact_address(self):
        for slug in sync_shared.TASKS_CONFIG["checkout"]["shipping"]:
            with self.subTest(merchant=slug):
                source = ROOT / "tasks/checkout-v1" / slug
                original_path = sys.path[:]
                try:
                    sys.path.insert(0, str(source / "tests"))
                    fixture = load(source / "tests/check_test.py", "shipping_fixture")
                    payment_check = load(
                        source / "tests/check.py", "shipping_payment_check"
                    )
                    with patch.dict(sys.modules, {"payment_check": payment_check}):
                        # A task-local trusted fixture supplies the expected address.
                        target = (
                            ROOT
                            / "tasks/checkout-v1"
                            / sync_shared.TASKS_CONFIG["checkout"]["shipping"][slug]
                        )
                        verifier = load(target / "tests/check.py", "shipping_check")
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

    def test_generation_is_repeatable_and_does_not_modify_sources(self):
        for slug, target_name in sync_shared.TASKS_CONFIG["checkout"][
            "shipping"
        ].items():
            with (
                self.subTest(merchant=slug),
                tempfile.TemporaryDirectory() as directory,
            ):
                source = ROOT / "tasks/checkout-v1" / slug
                before = {
                    p.relative_to(source): p.read_bytes()
                    for p in source.rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts
                }
                target = Path(directory) / target_name
                generate(source, target, SHARED)
                first = {
                    p.relative_to(target): p.read_bytes()
                    for p in target.rglob("*")
                    if p.is_file()
                }
                generate(source, target, SHARED)
                self.assertEqual(
                    first,
                    {
                        p.relative_to(target): p.read_bytes()
                        for p in target.rglob("*")
                        if p.is_file()
                    },
                )
                self.assertEqual(
                    before,
                    {
                        p.relative_to(source): p.read_bytes()
                        for p in source.rglob("*")
                        if p.is_file() and "__pycache__" not in p.parts
                    },
                )
                self.assertEqual(
                    (target / "tests/payment_check.py").read_bytes(),
                    (source / "tests/check.py").read_bytes(),
                )
                self.assertIn(
                    "including the apartment", (target / "instruction.md").read_text()
                )
                self.assertFalse(
                    (target / "environment/merchant/shipping.json").exists()
                )
                for name in ("wallet", "link"):
                    for p in (source / "environment" / name).iterdir():
                        if p.is_file():
                            self.assertEqual(
                                p.read_bytes(),
                                (target / "environment" / name / p.name).read_bytes(),
                            )
