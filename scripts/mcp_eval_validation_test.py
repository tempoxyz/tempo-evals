from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared/tempo/mcp-eval"))

from validation import (  # noqa: E402
    evidence_summary,
    expected_answer_errors,
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

    def test_requires_task_specific_terms_evidence_and_tools(self) -> None:
        expected = {
            "required_terms": ["fee", "payer"],
            "required_patterns": [
                {
                    "name": "transaction hash",
                    "pattern": "0x[a-f0-9]{64}",
                    "min_matches": 1,
                }
            ],
            "minimum_sources": 1,
            "required_data_tools": [],
        }
        answer = {
            "answer": "Fee payer 0x" + "a" * 64,
            "sources": ["https://docs.tempo.xyz/"],
        }
        events = [{"allowed": True, "tool": "v1_transactions_get"}]

        self.assertEqual(expected_answer_errors(answer, expected, events), [])
        self.assertIn(
            "answer must address task concept: payer",
            expected_answer_errors(
                {**answer, "answer": "Fee 0x" + "a" * 64}, expected, events
            ),
        )


if __name__ == "__main__":
    unittest.main()
