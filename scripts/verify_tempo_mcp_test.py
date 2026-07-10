from __future__ import annotations

import unittest

from scripts.verify_tempo_mcp import parse_mcp_response, verify_tools


class VerifyTempoMcpTest(unittest.TestCase):
    def test_accepts_the_complete_tempo_mcp_schema(self) -> None:
        verify_tools({"search", "find_pages", "read_page", "code"}, {"search", "code"})

    def test_rejects_missing_required_tools(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "code"):
            verify_tools({"search", "find_pages", "read_page"}, {"search", "code"})

    def test_parses_streamable_http_event(self) -> None:
        self.assertEqual(
            parse_mcp_response(b'event: message\ndata: {"jsonrpc":"2.0","id":1}\n\n'),
            {"jsonrpc": "2.0", "id": 1},
        )


if __name__ == "__main__":
    unittest.main()
