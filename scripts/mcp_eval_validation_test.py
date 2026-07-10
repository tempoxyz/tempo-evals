from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared/tempo/mcp-eval"))

from validation import has_required_tool_mix, used_data_tools  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
