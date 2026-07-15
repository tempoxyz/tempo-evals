from __future__ import annotations

import unittest

from scripts.verify_tempo_mcp import json_text_content, parse_mcp_response, verify_tools


class VerifyTempoMcpTest(unittest.TestCase):
    def test_accepts_the_complete_tempo_mcp_schema(self) -> None:
        verify_tools(
            {"docs_search", "docs_code", "v1_blocks_get", "v1_transactions_get"},
            {"docs_search", "docs_code"},
        )

    def test_rejects_missing_required_tools(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "docs_code"):
            verify_tools({"docs_search", "v1_blocks_get"}, {"docs_search", "docs_code"})

    def test_parses_streamable_http_event(self) -> None:
        self.assertEqual(
            parse_mcp_response(b'event: message\ndata: {"jsonrpc":"2.0","id":1}\n\n'),
            {"jsonrpc": "2.0", "id": 1},
        )

    def test_parses_json_tool_content(self) -> None:
        self.assertEqual(
            json_text_content(
                {"result": {"content": [{"text": '{"tools":[],"nextOffset":20}'}]}}
            ),
            {"tools": [], "nextOffset": 20},
        )


if __name__ == "__main__":
    unittest.main()
