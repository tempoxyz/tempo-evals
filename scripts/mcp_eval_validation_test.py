from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared/tempo/mcp-eval"))

from validation import (  # noqa: E402
    evidence_summary,
    has_required_tool_mix,
    used_data_tools,
    validated_data_evidence,
)


class McpEvalValidationTest(unittest.TestCase):
    def test_requires_docs_and_data_calls(self) -> None:
        self.assertTrue(
            has_required_tool_mix(
                [
                    {"allowed": True, "tool": "v1_blocks_get"},
                    {"allowed": True, "tool": "docs_code"},
                ]
            )
        )

    def test_rejects_missing_or_denied_calls(self) -> None:
        self.assertFalse(
            has_required_tool_mix(
                [
                    {"allowed": True, "tool": "v1_blocks_get"},
                    {"allowed": False, "tool": "docs_code"},
                ]
            )
        )

    def test_returns_only_allowed_data_tools(self) -> None:
        self.assertEqual(
            used_data_tools(
                [
                    {"allowed": True, "tool": "v1_blocks_get"},
                    {"allowed": True, "tool": "docs_code"},
                    {"allowed": False, "tool": "v1_transactions_get"},
                ]
            ),
            {"v1_blocks_get"},
        )

    def test_evidence_must_reference_an_executed_data_tool(self) -> None:
        events = [
            {
                "allowed": True,
                "tool": "v1_blocks_get",
                "arguments": {"number": 1},
                "response_sha256": "response",
            }
        ]
        evidence = validated_data_evidence(
            events,
            [
                {
                    "source": "mcp://tempo/v1_blocks_get",
                    "claim": "The block contains the observed transfer.",
                }
            ],
        )
        self.assertEqual(
            evidence_summary(events, evidence),
            [
                {
                    "source": "mcp://tempo/v1_blocks_get",
                    "claim": "The block contains the observed transfer.",
                    "calls": [
                        {
                            "arguments": {"number": 1},
                            "response_sha256": "response",
                        }
                    ],
                }
            ],
        )

    def test_evidence_rejects_an_exploratory_tool(self) -> None:
        with self.assertRaisesRegex(ValueError, "was not used"):
            validated_data_evidence(
                [{"allowed": True, "tool": "v1_blocks_get"}],
                [
                    {
                        "source": "mcp://tempo/v1_transactions_get",
                        "claim": "Not supported by the trace.",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
