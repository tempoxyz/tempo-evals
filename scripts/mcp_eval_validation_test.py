from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared/tempo/mcp-eval"))

from validation import (  # noqa: E402
    component_reward,
    data_tool_from_source,
    evidence_summary,
    expected_answer_errors,
    has_required_tool_mix,
    is_tempo_docs_url,
    used_data_tools,
    validated_data_evidence,
)


class McpEvalValidationTest(unittest.TestCase):
    def test_component_reward_is_equal_weighted(self) -> None:
        components = {
            "schema_valid": 1,
            "docs_source_valid": 0,
            "mcp_tool_mix_valid": 1,
            "data_evidence_valid": 1,
            "task_requirements_valid": 0,
        }
        self.assertEqual(component_reward(components), 0.6)
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
        self.assertEqual(evidence["errors"], [])
        self.assertEqual(evidence["warnings"], [])
        self.assertEqual(
            evidence_summary(events, evidence["evidence"]),
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

    def test_evidence_accepts_injected_mcp_server_names(self) -> None:
        events = [{"allowed": True, "tool": "v1_blocks_get"}]
        for source in (
            "mcp://tempo/v1_blocks_get",
            "mcp://tempo-direct/v1_blocks_get",
            "mcp://tempo-code/v1_blocks_get",
            "mcp://tempo/v1_blocks_get?include=transactions",
        ):
            with self.subTest(source=source):
                self.assertEqual(data_tool_from_source(source), "v1_blocks_get")
                self.assertEqual(
                    validated_data_evidence(
                        events,
                        [
                            {
                                "source": source,
                                "claim": "The block contains the transfer.",
                            }
                        ],
                    ),
                    {
                        "evidence": [
                            {
                                "source": source,
                                "claim": "The block contains the transfer.",
                            }
                        ],
                        "errors": [],
                        "warnings": [],
                    },
                )

    def test_docs_urls_accept_bare_origins_without_matching_lookalikes(self) -> None:
        for source in (
            "https://docs.tempo.xyz",
            "https://developers.tempo.xyz/docs",
            "https://accounts.tempo.xyz/docs",
            "https://tips.sh",
            "https://docs.tempo.xyz/guide/payments",
        ):
            with self.subTest(source=source):
                self.assertTrue(is_tempo_docs_url(source))
        self.assertFalse(is_tempo_docs_url("https://docs.tempo.xyz.example.com"))
        self.assertFalse(is_tempo_docs_url("https://developers.tempo.xyz/other"))

    def test_docs_evidence_is_a_warning_when_data_evidence_is_trace_backed(
        self,
    ) -> None:
        result = validated_data_evidence(
            [{"allowed": True, "tool": "v1_blocks_get"}],
            [
                {
                    "source": "mcp://tempo/v1_blocks_get",
                    "claim": "The block contains the transfer.",
                },
                {
                    "source": "https://docs.tempo.xyz",
                    "claim": "Tempo documents this transaction type.",
                },
                {
                    "source": "mcp://tempo/docs_search",
                    "claim": "The MCP docs search returned the transaction guide.",
                },
                {
                    "source": "mcp://tempo-code/v1_docs_read_page",
                    "claim": "The docs page describes the transaction type.",
                },
                {
                    "source": "mcp://tempo/docs/wallet-developers",
                    "claim": "The docs route identifies the wallet guide.",
                },
                {
                    "source": "mcp://tempo/spec-fee",
                    "claim": "The docs page covers fee semantics.",
                },
            ],
        )
        self.assertEqual(len(result["evidence"]), 1)
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["warnings"]), 5)

    def test_docs_only_evidence_does_not_satisfy_data_provenance(self) -> None:
        result = validated_data_evidence(
            [{"allowed": True, "tool": "docs_code"}],
            [{"source": "mcp://tempo/docs_code", "claim": "Documentation claim."}],
        )
        self.assertEqual(result["evidence"], [])
        self.assertIn(
            "evidence must include at least one trace-backed MCP data tool",
            result["errors"],
        )

    def test_evidence_rejects_an_exploratory_tool(self) -> None:
        result = validated_data_evidence(
            [{"allowed": True, "tool": "v1_blocks_get"}],
            [
                {
                    "source": "mcp://tempo/v1_transactions_get",
                    "claim": "Not supported by the trace.",
                }
            ],
        )
        self.assertIn(
            "evidence source was not used: v1_transactions_get", result["errors"]
        )

    def test_requires_structured_task_fields_and_tools(self) -> None:
        expected = {
            "minimum_sources": 1,
            "required_data_tools": [],
            "structured": {
                "required_fields": ["summary", "observations", "inferences"],
                "array_fields": {
                    "observations": {
                        "min_items": 1,
                        "item_required_fields": ["subject", "details"],
                        "item_patterns": {"subject": "0x[a-f0-9]{64}"},
                    },
                    "inferences": {
                        "min_items": 1,
                        "item_required_fields": ["claim", "basis"],
                        "item_patterns": {},
                    },
                },
            },
        }
        answer = {
            "summary": "The fee payer sponsored the transaction.",
            "observations": [
                {"subject": "0x" + "a" * 64, "details": "Observed fee payer."}
            ],
            "inferences": [{"claim": "The fee was sponsored.", "basis": "Fee payer."}],
            "sources": ["https://docs.tempo.xyz/"],
        }
        events = [{"allowed": True, "tool": "v1_transactions_get"}]

        self.assertEqual(expected_answer_errors(answer, expected, events), [])
        self.assertEqual(
            expected_answer_errors(
                {
                    **answer,
                    "observations": [
                        {
                            "subject": "transaction 0x" + "a" * 64,
                            "details": "Observed fee payer.",
                        }
                    ],
                },
                expected,
                events,
            ),
            [],
        )
        self.assertIn(
            "answer item field must match pattern: observations[0].subject",
            expected_answer_errors(
                {
                    **answer,
                    "observations": [
                        {"subject": "not-a-hash", "details": "Observed fee payer."}
                    ],
                },
                expected,
                events,
            ),
        )
        self.assertIn(
            "answer item is missing field: inferences[0].basis",
            expected_answer_errors(
                {**answer, "inferences": [{"claim": "The fee was sponsored."}]},
                expected,
                events,
            ),
        )

    def test_allows_empty_evidence_refs_and_flexible_hash_location(self) -> None:
        expected = {
            "minimum_sources": 1,
            "required_data_tools": [],
            "structured": {
                "required_fields": ["summary", "observations"],
                "array_fields": {
                    "observations": {
                        "min_items": 1,
                        "item_required_fields": [
                            "subject",
                            "details",
                            "evidence_refs",
                        ],
                        "item_patterns": {},
                        "any_item_patterns": [
                            {
                                "fields": ["subject", "details"],
                                "pattern": "0x[a-f0-9]{64}",
                            }
                        ],
                    }
                },
            },
        }
        answer = {
            "summary": "Observed transfer.",
            "observations": [
                {
                    "subject": "Token and account roles",
                    "details": "Transaction 0x" + "a" * 64 + " transferred funds.",
                    "evidence_refs": [],
                }
            ],
            "sources": ["https://docs.tempo.xyz/"],
        }
        self.assertEqual(expected_answer_errors(answer, expected, []), [])

    def test_requires_item_patterns_on_every_item(self) -> None:
        expected = {
            "minimum_sources": 1,
            "required_data_tools": [],
            "structured": {
                "required_fields": ["summary", "observations"],
                "array_fields": {
                    "observations": {
                        "min_items": 2,
                        "item_required_fields": ["subject", "details"],
                        "item_patterns": {"subject": "0x[a-f0-9]{64}"},
                    }
                },
            },
        }
        answer = {
            "summary": "Observed two access keys.",
            "observations": [
                {"subject": "0x" + "a" * 64, "details": "First access key."},
                {"subject": "not-a-hash", "details": "Second access key."},
            ],
            "sources": ["https://docs.tempo.xyz/"],
        }

        self.assertIn(
            "answer item field must match pattern: observations[1].subject",
            expected_answer_errors(answer, expected, []),
        )

    def test_accepts_one_tool_from_a_task_specific_group(self) -> None:
        expected = {
            "minimum_sources": 1,
            "required_data_tools": [],
            "required_data_tool_any_of": [
                ["v1_transactions_get", "v1_transactions_transactionHash_get"]
            ],
            "structured": {"required_fields": [], "array_fields": {}},
        }
        answer = {"sources": ["https://docs.tempo.xyz/"]}
        self.assertEqual(
            expected_answer_errors(
                answer,
                expected,
                [{"allowed": True, "tool": "v1_transactions_transactionHash_get"}],
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
