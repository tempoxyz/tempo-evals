from __future__ import annotations

import copy
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sync_shared

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks/checkout-v1"
DECLINE = ROOT / "shared/checkout/decline"
WALLET = ROOT / "shared/checkout/wallet"
ADDRESS = json.loads((ROOT / "shared/checkout/shipping/address.json").read_text())
ORDER = json.loads((ROOT / "shared/checkout/shipping/order.json").read_text())
# The provider object each source's fixture keeps its payment in.
COLLECTIONS = {"stripe-card-discover": "sessions"}


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def modules(directory: Path, name: str):
    """A decline task's payment check, shipping check and decline check."""
    original = sys.path[:]
    try:
        sys.path.insert(0, str(directory))
        payment_check = load(directory / "payment_check.py", f"{name}_payment")
        with patch.dict(sys.modules, {"payment_check": payment_check}):
            shipping_check = load(directory / "shipping_check.py", f"{name}_shipping")
            with patch.dict(sys.modules, {"shipping_check": shipping_check}):
                check = load(directory / "check.py", f"{name}_check")
    finally:
        sys.path[:] = original
    return payment_check, shipping_check, check


def paid(task: str, slug: str) -> dict:
    """The source's verified purchase, shipped to the fixture address and paid
    with the backup card after the primary card was declined."""
    source = TASKS / slug / "tests"
    original = sys.path[:]
    try:
        sys.path.insert(0, str(source))
        payment_check = load(source / "payment_check.py", f"source_{slug}_payment")
        with patch.dict(sys.modules, {"payment_check": payment_check}):
            fixture = load(source / "check_test.py", f"source_{slug}_fixture")
    finally:
        sys.path[:] = original
    snapshot = copy.deepcopy(fixture.PAID)
    if slug in COLLECTIONS:
        snapshot = {COLLECTIONS[slug]: [snapshot]}
    order_id = payment_check.paid_order_id(snapshot)
    cards = json.loads((TASKS / task / "tests/cards.json").read_text())
    return {
        **snapshot,
        "shippingOrders": [
            {"id": order_id, "shipping": ADDRESS, "source": "json", **ORDER}
        ],
        "cardAttempts": [
            {
                "kind": "charge",
                "id": "declined",
                "orderId": order_id,
                "status": "failed",
                "outcome": "declined",
                "last4": cards["primaryLast4"],
            },
            {
                "kind": "charge",
                "id": "paid",
                "orderId": order_id,
                "status": "succeeded",
                "outcome": "succeeded",
                "last4": cards["backupLast4"],
            },
        ],
    }


class CheckoutDeclineTest(unittest.TestCase):
    def test_decline_tasks_cover_every_card_rail_that_can_show_attempts(self):
        decline = sync_shared.TASKS_CONFIG["checkout"]["decline"]
        directed = sync_shared.TASKS_CONFIG["checkout"]["directed"]
        self.assertEqual(set(decline), set(sync_shared.CHECKOUT_DECLINE_CARDS))
        self.assertEqual(set(decline), set(sync_shared.CHECKOUT_DECLINE_EVIDENCE))
        self.assertEqual(
            set(directed), set(decline) | set(sync_shared.CHECKOUT_DECLINE_UNSUPPORTED)
        )
        self.assertFalse(set(decline) & set(sync_shared.CHECKOUT_DECLINE_UNSUPPORTED))
        self.assertEqual(
            sorted(sync_shared.decline_tasks()),
            [
                "apicard-decline-directed",
                "braintree-decline-directed",
                "mppcard-decline-directed",
                "stripecard-decline-directed",
            ],
        )

    def test_every_wallet_has_a_backup_card_and_decline_mode_swaps_them(self):
        init = (WALLET / "init.py").read_text()
        backup = sync_shared.CHECKOUT_DECLINE_BACKUP_CARD
        self.assertIn('os.environ.get("DECLINED_CARD_NUMBER", "")', init)
        self.assertIn(f'"number": DECLINED_CARD or "{backup}"', init)
        self.assertIn(f'"{backup}" if DECLINED_CARD else "6011111111111117"', init)
        link = (WALLET / "link_setup.js").read_text()
        self.assertIn("process.env.CARD_DECLINE === '1'", link)
        self.assertIn("decline ? wallet.backupCard : wallet.card", link)
        self.assertIn("decline ? 'pm_card_chargeDeclined' : 'pm_card_visa'", link)
        self.assertIn("decline ? 'pm_card_mastercard' : 'pm_card_discover'", link)
        # The token rails' backup token is minted on the backup card's number.
        self.assertTrue(backup.startswith("5555"))
        agent = (ROOT / "shared/checkout/agent/README.md").read_text()
        self.assertIn("backup card", agent)
        for task in sync_shared.checkout_task_dirs():
            with self.subTest(task=task.name):
                self.assertEqual(
                    (task / "environment/wallet/init.py").read_bytes(),
                    (WALLET / "init.py").read_bytes(),
                )
                self.assertEqual(
                    (task / "environment/link/link_setup.js").read_bytes(),
                    (WALLET / "link_setup.js").read_bytes(),
                )
                compose = (task / "environment/docker-compose.yaml").read_text()
                declined = task.name in sync_shared.decline_tasks()
                self.assertEqual("DECLINED_CARD_NUMBER" in compose, declined)
                self.assertEqual('CARD_DECLINE: "1"' in compose, declined)

    def test_verifier_requires_the_backup_card_after_a_primary_decline(self):
        for task, slug in sync_shared.decline_tasks().items():
            with self.subTest(task=task):
                payment_check, shipping_check, check = modules(
                    TASKS / task / "tests", task
                )
                snapshot = paid(task, slug)
                method = payment_check.check(snapshot)[2]
                self.assertIsNotNone(method)
                self.assertEqual(check.check(snapshot), (True, "verified", method))
                declined, backup = snapshot["cardAttempts"]
                for attempts, reason in (
                    (None, "missing_card_attempts"),
                    ("bad", "missing_card_attempts"),
                    ([declined], "not_paid_with_backup_card"),
                    (
                        [declined, {**backup, "last4": declined["last4"]}],
                        "not_paid_with_backup_card",
                    ),
                    (
                        [declined, {**backup, "orderId": "another"}],
                        "not_paid_with_backup_card",
                    ),
                    ([declined, backup, backup], "not_paid_with_backup_card"),
                    ([backup], "primary_card_not_declined"),
                    (
                        [{**declined, "last4": "1117"}, backup],
                        "primary_card_not_declined",
                    ),
                    (
                        [{**declined, "outcome": "other"}, backup],
                        "primary_card_not_declined",
                    ),
                ):
                    changed = copy.deepcopy(snapshot)
                    if attempts is None:
                        del changed["cardAttempts"]
                    else:
                        changed["cardAttempts"] = attempts
                    self.assertEqual(check.check(changed), (False, reason, None))
                # Declines on another order and other attempts still pass.
                changed = copy.deepcopy(snapshot)
                changed["cardAttempts"] = [
                    {**declined, "orderId": "earlier"},
                    {**declined, "outcome": "other"},
                    backup,
                ]
                self.assertTrue(check.check(changed)[0])
                # The paying task's own failures keep their reasons.
                wrong_address = copy.deepcopy(snapshot)
                wrong_address["shippingOrders"][0]["shipping"]["line2"] = "Apt 9"
                self.assertEqual(
                    check.check(wrong_address),
                    (False, "shipping_address_mismatch", None),
                )
                unpaid = {
                    "shippingOrders": snapshot["shippingOrders"],
                    "cardAttempts": [declined],
                }
                passed, reason, _ = check.check(unpaid)
                self.assertFalse(passed)
                self.assertEqual(reason, shipping_check.check(unpaid)[1])

    def test_verifier_writes_rewards_and_details_the_grader_reads(self):
        for task, slug in sync_shared.decline_tasks().items():
            _, _, check = modules(TASKS / task / "tests", f"main_{task}")
            snapshot = paid(task, slug)
            no_decline = {**snapshot, "cardAttempts": snapshot["cardAttempts"][1:]}
            for case, reward, reason, declines in (
                (snapshot, 1, "verified", 1),
                (no_decline, 0, "primary_card_not_declined", 0),
            ):
                with (
                    self.subTest(task=task, reason=reason),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    root = Path(directory)
                    path = root / "snapshot.json"
                    path.write_text(json.dumps(case))
                    with (
                        patch.object(check, "SNAPSHOT", path),
                        patch.object(check, "LOG_DIR", root),
                    ):
                        check.main()
                    self.assertEqual(
                        json.loads((root / "reward.json").read_text()),
                        {"reward": reward},
                    )
                    details = json.loads((root / "details.json").read_text())
                    self.assertEqual(details["reason"], reason)
                    self.assertEqual(details["primary_card_declines"], declines)
                    self.assertEqual(details["backup_card_payments"], 1)
                    self.assertTrue(details["shipping_address_match"])
                    self.assertIn("extra_checkout_attempts", details)
                    self.assertEqual(
                        details["checkout_stage"],
                        "verified" if reward else "primary_card_not_declined",
                    )

    def test_generated_tasks_differ_from_their_directed_peer_only_as_intended(self):
        decline = sync_shared.TASKS_CONFIG["checkout"]["decline"]
        directed = sync_shared.TASKS_CONFIG["checkout"]["directed"]
        for task, slug in sync_shared.decline_tasks().items():
            with self.subTest(task=task):
                target = TASKS / task
                peer = TASKS / directed[slug]["task"]
                card = sync_shared.CHECKOUT_DECLINE_CARDS[slug]
                self.assertEqual(task, f"{decline[slug]}-decline-directed")
                for source, destination in (
                    (DECLINE / "check.py", "tests/check.py"),
                    (DECLINE / "solve.sh", "solution/solve.sh"),
                    (DECLINE / "attempts.ts", "environment/merchant/attempts.ts"),
                    (
                        ROOT / "shared/checkout/shipping/check.py",
                        "tests/shipping_check.py",
                    ),
                ):
                    self.assertEqual(
                        (target / destination).read_bytes(), source.read_bytes()
                    )
                self.assertTrue((target / "solution/solve.sh").stat().st_mode & 0o100)
                self.assertFalse((target / "solution/solve.ts").exists())
                self.assertEqual(
                    json.loads((target / "tests/cards.json").read_text()),
                    {"primaryLast4": card["number"][-4:], "backupLast4": "4444"},
                )
                self.assertEqual(
                    (target / "solution/pay.ts").read_text(),
                    re.sub(
                        r"\bwallet\.card\b",
                        "wallet[process.env.ORACLE_CARD || 'card']",
                        (peer / "solution/solve.ts").read_text(),
                    ),
                )
                self.assertEqual(
                    (target / "solution/pay.sh").read_text(),
                    (peer / "solution/solve.sh")
                    .read_text()
                    .replace("/solution/solve.ts", "/solution/pay.ts"),
                )
                self.assertTrue((target / "solution/pay.sh").stat().st_mode & 0o100)
                compose = (target / "environment/docker-compose.yaml").read_text()
                self.assertEqual(
                    compose.replace(
                        f'      DECLINED_CARD_NUMBER: "{card["number"]}"\n', "", 1
                    ).replace('      CARD_DECLINE: "1"\n', "", 1),
                    (peer / "environment/docker-compose.yaml").read_text(),
                )
                self.assertEqual(
                    (target / "environment/merchant/Dockerfile")
                    .read_text()
                    .replace(" attempts.ts ", " ", 1),
                    (peer / "environment/merchant/Dockerfile").read_text(),
                )
                (server,) = (target / "environment/merchant").glob("server.[jt]s")
                peer_server = (peer / server.relative_to(target)).read_text()
                if slug == "braintree-card-discover":
                    self.assertIn("verifyCard: true", server.read_text())
                    self.assertIn("declines.jsonl", server.read_text())
                    self.assertIn("paymentMethodToken: card.token", server.read_text())
                else:
                    self.assertEqual(server.read_text(), peer_server)
                instruction = (target / "instruction.md").read_text()
                peer_instruction = (peer / "instruction.md").read_text()
                self.assertEqual(
                    instruction.split("\n", 1)[1], peer_instruction.split("\n", 1)[1]
                )
                self.assertNotEqual(instruction, peer_instruction)
                metadata = tomllib.loads((target / "task.toml").read_text())
                peer_metadata = tomllib.loads((peer / "task.toml").read_text())
                self.assertEqual(metadata["task"]["name"], f"checkout-v1/{task}")
                self.assertIn("decline", metadata["task"]["keywords"])
                self.assertEqual(
                    {
                        key: metadata["metadata"].get(key)
                        for key in (
                            "prompt_condition",
                            "required_method",
                            "expected_outcome",
                            "source_task",
                            "scenario_id",
                        )
                    },
                    {
                        "prompt_condition": "directed",
                        "required_method": directed[slug]["method"],
                        "expected_outcome": None,
                        "source_task": slug,
                        "scenario_id": f"checkout-v1/{task}",
                    },
                )
                (collect,) = metadata["verifier"]["collect"]
                (peer_collect,) = peer_metadata["verifier"]["collect"]
                self.assertTrue(
                    collect["command"].startswith(f"({peer_collect['command']}) && ")
                )
                tsx = peer_collect["command"].split(" /srv/snapshot.ts")[0].split()[-1]
                self.assertIn(f" {tsx} /srv/attempts.ts", collect["command"])
                self.assertGreater(collect["timeout_sec"], peer_collect["timeout_sec"])
                readme = (target / "README.md").read_text()
                method = sync_shared.CHECKOUT_CART_METHODS[slug]["method"]
                self.assertIn(f"\n# {method} declined-card checkout\n", readme)
                self.assertIn(sync_shared.CHECKOUT_DECLINE_EVIDENCE[slug], readme)
                self.assertTrue(readme.endswith(f"{directed[slug]['instruction']}\n"))

    def test_generation_is_reproducible_and_rejects_unsupported_sources(self):
        directed = sync_shared.TASKS_CONFIG["checkout"]["directed"]
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            for slug in sync_shared.TASKS_CONFIG["checkout"]["decline"]:
                peer = directed[slug]["task"]
                shutil.copytree(TASKS / peer, checkout / peer)
            with patch.object(sync_shared, "CHECKOUT_TASKS_DIR", checkout):
                sync_shared.sync_checkout_decline_variants()
            for task in sync_shared.decline_tasks():
                generated = {
                    path.relative_to(checkout / task): path.read_bytes()
                    for path in (checkout / task).rglob("*")
                    if path.is_file()
                }
                committed = {
                    path.relative_to(TASKS / task): path.read_bytes()
                    for path in (TASKS / task).rglob("*")
                    if path.is_file()
                    and not {"node_modules", "__pycache__"} & set(path.parts)
                }
                self.assertEqual(generated, committed, task)
            config = copy.deepcopy(sync_shared.TASKS_CONFIG)
            config["checkout"]["decline"] = {"stripe-link-discover": "link"}
            with (
                patch.object(sync_shared, "CHECKOUT_TASKS_DIR", checkout),
                patch.object(sync_shared, "TASKS_CONFIG", config),
                self.assertRaisesRegex(ValueError, "Link"),
            ):
                sync_shared.sync_checkout_decline_variants()

    def test_service_env_is_added_to_one_service(self):
        with tempfile.TemporaryDirectory() as directory:
            task = Path(directory)
            compose = task / "environment/docker-compose.yaml"
            compose.parent.mkdir()
            compose.write_text(
                "services:\n  wallet:\n    build:\n      context: ./wallet\n"
                "    environment:\n      A: b\n  link:\n    environment:\n"
            )
            sync_shared.set_service_env(task, "wallet", "X", "1")
            self.assertIn(
                '    environment:\n      X: "1"\n      A: b\n', compose.read_text()
            )
            with self.assertRaisesRegex(ValueError, "merchant"):
                sync_shared.set_service_env(task, "merchant", "X", "1")


if __name__ == "__main__":
    unittest.main()
