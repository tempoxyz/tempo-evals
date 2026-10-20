from __future__ import annotations

import unittest

from shared.checkout.tests.observation import payment_observations


class CheckoutObservationTest(unittest.TestCase):
    def test_method_observation_does_not_require_checkout_success(self) -> None:
        for snapshot, method in (
            ({"sessions": [{"paymentIntent": {"paymentMethodType": "link"}}]}, "link"),
            (
                {
                    "intents": [
                        {"status": "requires_action", "paymentMethodType": "card"}
                    ]
                },
                "card",
            ),
            (
                {"orders": [{"status": "APPROVED", "paymentMethodType": "paypal"}]},
                "paypal",
            ),
            (
                {"deliveries": [{"item": "Wrong item", "receiptMethod": "tempo"}]},
                "tempo_mpp",
            ),
        ):
            with self.subTest(snapshot=snapshot):
                self.assertEqual(
                    payment_observations(snapshot),
                    {
                        "observed_method": method,
                        "observed_methods": [method],
                    },
                )

    def test_unknown_methods_are_not_guessed_from_the_merchant_or_status(self) -> None:
        for snapshot in (
            None,
            {},
            {"intents": None},
            {"intents": [None, 3]},
            {"orders": [{"capture": {"status": "COMPLETED"}}]},
            {"deliveries": [{"receiptStatus": "success"}]},
        ):
            with self.subTest(snapshot=snapshot):
                self.assertEqual(
                    payment_observations(snapshot),
                    {
                        "observed_method": None,
                        "observed_methods": [],
                    },
                )

    def test_multiple_methods_are_retained_without_choosing_one(self) -> None:
        snapshot = {
            "intents": [
                {"paymentMethodType": "link"},
                {"paymentMethodType": "card"},
                {"paymentMethodType": "card"},
            ]
        }
        self.assertEqual(
            payment_observations(snapshot),
            {
                "observed_method": None,
                "observed_methods": ["card", "link"],
            },
        )
