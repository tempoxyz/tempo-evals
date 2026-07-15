from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "shared/tempo/mcp-eval/check.py"
sys.path.insert(0, str(CHECK.parent))
SPEC = importlib.util.spec_from_file_location("tempo_mcp_eval_check", CHECK)
assert SPEC and SPEC.loader
CHECK_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK_MODULE)
sys.path.pop(0)


def run_check(
    answer: dict[str, Any],
    expected: dict[str, Any],
    events: list[dict[str, Any]] | None = None,
    *,
    traces: dict[str, list[dict[str, Any]] | str | None] | None = None,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="tempo-mcp-check-") as root:
        root_path = Path(root)
        workspace = root_path / "workspace"
        tests_dir = root_path / "tests"
        log_dir = root_path / "logs"
        workspace.mkdir()
        tests_dir.mkdir()
        (workspace / "answer.json").write_text(json.dumps(answer))
        (tests_dir / "expected.json").write_text(json.dumps(expected))

        trace_paths = {
            arm: root_path / f"{arm}-trace.jsonl" for arm in ("direct", "code")
        }
        if traces is None:
            traces = {"direct": events or [], "code": []}
        for arm, payload in traces.items():
            if payload is None:
                continue
            text = (
                payload
                if isinstance(payload, str)
                else "".join(f"{json.dumps(event)}\n" for event in payload)
            )
            trace_paths[arm].write_text(text)

        env = {
            "TEMPO_BENCH_WORKSPACE": str(workspace),
            "TEMPO_BENCH_TESTS_DIR": str(tests_dir),
            "TEMPO_BENCH_LOG_DIR": str(log_dir),
        }
        with (
            mock.patch.dict(os.environ, env),
            mock.patch.object(CHECK_MODULE, "TRACE_PATHS", trace_paths),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            CHECK_MODULE.main()
        return {
            "reward": json.loads((log_dir / "reward.json").read_text()),
            "validation": json.loads((log_dir / "validation.json").read_text()),
        }


class McpEvalCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.events = [
            {"allowed": True, "succeeded": True, "tool": "v1_transactions_get"},
            {"allowed": True, "succeeded": True, "tool": "docs_search"},
        ]
        self.answer = {
            "summary": "The observed fee was paid by the account.",
            "observations": [
                {
                    "subject": "transaction",
                    "details": "Observed fee payer.",
                    "evidence_refs": [0],
                }
            ],
            "inferences": [
                {
                    "claim": "The fee was sponsored.",
                    "basis": "Fee payer field.",
                    "evidence_refs": [0],
                }
            ],
            "sources": ["https://docs.tempo.xyz"],
            "evidence": [
                {
                    "source": "mcp://tempo-direct/v1_transactions_get",
                    "claim": "The transaction identifies the fee payer.",
                },
                {
                    "source": "mcp://tempo/docs_search",
                    "claim": "The documentation search returned the fee guide.",
                },
            ],
        }
        self.expected = {
            "minimum_sources": 1,
            "required_data_tools": ["v1_transactions_get"],
            "structured": {
                "required_fields": ["summary", "observations", "inferences"],
                "array_fields": {
                    "observations": {
                        "min_items": 1,
                        "item_required_fields": ["subject", "details", "evidence_refs"],
                        "item_patterns": {},
                    },
                    "inferences": {
                        "min_items": 1,
                        "item_required_fields": ["claim", "basis", "evidence_refs"],
                        "item_patterns": {},
                    },
                },
            },
        }

    def test_accepts_docs_provenance_as_a_warning_alongside_data_evidence(self) -> None:
        result = run_check(self.answer, self.expected, self.events)
        self.assertEqual(result["reward"]["reward"], 1)
        self.assertEqual(result["reward"]["quality"], 0)
        self.assertEqual(result["validation"]["errors"], [])
        self.assertEqual(len(result["validation"]["warnings"]), 1)
        self.assertEqual(result["reward"]["data_evidence_valid"], 1)

    def test_reports_all_deterministic_failures(self) -> None:
        result = run_check(
            {
                "summary": "No details available.",
                "observations": [],
                "inferences": [],
                "sources": [],
                "evidence": [
                    {
                        "source": "https://docs.tempo.xyz",
                        "claim": "Documentation claim only.",
                    }
                ],
            },
            self.expected,
            self.events,
        )
        self.assertEqual(result["reward"]["reward"], 0.4)
        self.assertEqual(result["reward"]["quality"], 0)
        self.assertEqual(result["reward"]["valid_answer"], 0)
        self.assertEqual(result["reward"]["mcp_tool_mix_valid"], 1)
        self.assertEqual(result["reward"]["data_evidence_valid"], 0)
        self.assertIn(
            "answer must cite at least one Tempo documentation URL",
            result["validation"]["errors"],
        )
        self.assertIn(
            "evidence must include at least one trace-backed MCP data tool",
            result["validation"]["errors"],
        )
        self.assertIn(
            "answer field needs at least 1 item(s): observations",
            result["validation"]["errors"],
        )

    def test_failed_tool_calls_do_not_count_as_trace_evidence(self) -> None:
        events = [
            {"allowed": True, "succeeded": False, "tool": "v1_transactions_get"},
            {"allowed": True, "succeeded": False, "tool": "docs_search"},
        ]
        result = run_check(self.answer, self.expected, events)

        self.assertEqual(result["reward"]["mcp_tool_mix_valid"], 0)
        self.assertEqual(result["reward"]["data_evidence_valid"], 0)
        self.assertEqual(result["reward"]["task_requirements_valid"], 0)
        self.assertIn(
            "evidence source was not used: v1_transactions_get",
            result["validation"]["errors"],
        )

    def test_rejects_a_missing_trace_artifact(self) -> None:
        result = run_check(
            self.answer,
            self.expected,
            traces={"direct": self.events, "code": None},
        )
        self.assertIn(
            "missing code MCP trace artifact",
            result["validation"]["errors"][0],
        )
        self.assertLess(result["reward"]["reward"], 1)

    def test_rejects_malformed_trace_jsonl(self) -> None:
        result = run_check(
            self.answer,
            self.expected,
            traces={"direct": "not-json\n", "code": []},
        )
        self.assertEqual(
            result["validation"]["errors"],
            ["malformed direct MCP trace JSONL at line 1"],
        )
        self.assertLess(result["reward"]["reward"], 1)

    def test_rejects_both_active_arms(self) -> None:
        result = run_check(
            self.answer,
            self.expected,
            traces={"direct": self.events, "code": self.events},
        )
        self.assertIn(
            "both MCP arms provided traces; exactly one must be active",
            result["validation"]["errors"],
        )

    def test_rejects_neither_active_arm(self) -> None:
        result = run_check(
            self.answer,
            self.expected,
            traces={"direct": [], "code": []},
        )
        self.assertIn(
            "neither MCP arm provided a trace; exactly one must be active",
            result["validation"]["errors"],
        )


if __name__ == "__main__":
    unittest.main()
