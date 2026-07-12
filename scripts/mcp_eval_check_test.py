from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "shared/tempo/mcp-eval/check.py"


def run_check(
    answer: dict[str, Any], expected: dict[str, Any], events: list[dict[str, Any]]
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="tempo-mcp-check-") as root:
        root_path = Path(root)
        workspace = root_path / "workspace"
        tests_dir = root_path / "tests"
        log_dir = root_path / "logs"
        trace_path = root_path / "trace.json"
        workspace.mkdir()
        tests_dir.mkdir()
        (workspace / "answer.json").write_text(json.dumps(answer))
        (tests_dir / "expected.json").write_text(json.dumps(expected))
        trace_path.write_text(json.dumps({"events": events}))
        env = {
            **os.environ,
            "TEMPO_BENCH_WORKSPACE": str(workspace),
            "TEMPO_BENCH_TESTS_DIR": str(tests_dir),
            "TEMPO_BENCH_LOG_DIR": str(log_dir),
            "TEMPO_BENCH_TRACE_PATH": str(trace_path),
        }
        result = subprocess.run(
            [sys.executable, str(CHECK)],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        return {
            "reward": json.loads((log_dir / "reward.json").read_text()),
            "validation": json.loads((log_dir / "validation.json").read_text()),
        }


class McpEvalCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.events = [
            {"allowed": True, "tool": "v1_transactions_get"},
            {"allowed": True, "tool": "docs_search"},
        ]
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
        result = run_check(
            {
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
            },
            self.expected,
            self.events,
        )
        self.assertEqual(result["reward"]["reward"], 1)
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
        self.assertEqual(result["reward"]["reward"], 0)
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


if __name__ == "__main__":
    unittest.main()
