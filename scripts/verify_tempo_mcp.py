#!/usr/bin/env python3
"""Verify a Tempo Streamable HTTP MCP endpoint and Claude Code registration."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from typing import Any
from urllib.request import Request, urlopen

EXPECTED_TOOLS = {
    "docs_search",
    "docs_find_pages",
    "docs_read_page",
    "docs_code",
    "v1_blocks_get",
    "v1_transactions_get",
}
DEFERRED_GATEWAY_TOOLS = {
    "search_tools",
    "get_tool_details",
    "call_read_tool",
    "call_write_tool",
}


def api_key_headers() -> dict[str, str]:
    api_key = os.environ.get("TEMPO_API_KEY")
    return {"authorization": f"Bearer {api_key}"} if api_key else {}


def parse_mcp_response(raw: bytes) -> dict[str, Any]:
    text = raw.decode().strip()
    if text.startswith("event:"):
        data = [
            line.removeprefix("data:").strip()
            for line in text.splitlines()
            if line.startswith("data:")
        ]
        if not data:
            raise RuntimeError("MCP SSE response did not contain a data event")
        text = data[-1]
    return json.loads(text)


def json_rpc(
    url: str, payload: dict[str, Any], headers: dict[str, str]
) -> tuple[dict[str, Any], dict[str, str]]:
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
            "user-agent": "stable-bench-mcp-preflight/1.0",
            **headers,
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310 -- user-selected MCP URL
        return parse_mcp_response(response.read()), dict(response.headers.items())


def json_text_content(payload: dict[str, Any]) -> dict[str, Any]:
    for item in payload.get("result", {}).get("content", []):
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            value = json.loads(item["text"])
            if isinstance(value, dict):
                return value
    raise RuntimeError("MCP tool response did not contain JSON text")


def list_tools(url: str, expected: set[str] | None = None) -> set[str]:
    headers = {"mcp-protocol-version": "2025-06-18", **api_key_headers()}
    initialize, response_headers = json_rpc(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "stable-bench-preflight", "version": "1"},
            },
        },
        headers,
    )
    if "error" in initialize:
        raise RuntimeError(f"MCP initialize failed: {initialize['error']}")
    session_id = response_headers.get("Mcp-Session-Id") or response_headers.get(
        "mcp-session-id"
    )
    if session_id:
        headers["mcp-session-id"] = session_id
    tools, _ = json_rpc(
        url,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        headers,
    )
    if "error" in tools:
        raise RuntimeError(f"MCP tools/list failed: {tools['error']}")
    available = {
        str(tool["name"])
        for tool in tools.get("result", {}).get("tools", [])
        if isinstance(tool, dict) and isinstance(tool.get("name"), str)
    }
    offset = 0
    while expected and expected - available and available >= DEFERRED_GATEWAY_TOOLS:
        response, _ = json_rpc(
            url,
            {
                "jsonrpc": "2.0",
                "id": offset + 3,
                "method": "tools/call",
                "params": {
                    "name": "search_tools",
                    "arguments": {"query": "", "limit": 20, "offset": offset},
                },
            },
            headers,
        )
        page = json_text_content(response)
        available.update(
            tool["name"]
            for tool in page.get("tools", [])
            if isinstance(tool, dict) and tool.get("name") in expected
        )
        next_offset = page.get("nextOffset")
        if not isinstance(next_offset, int) or next_offset <= offset:
            break
        offset = next_offset
    return available


def verify_claude_registration(claude: str, url: str) -> None:
    with tempfile.TemporaryDirectory(prefix="tempo-mcp-preflight-") as config_dir:
        environment = os.environ | {"CLAUDE_CONFIG_DIR": config_dir}
        subprocess.run(
            [claude, "mcp", "add", "--transport", "http", "tempo", url],
            check=True,
            env=environment,
            capture_output=True,
            text=True,
        )
        status = subprocess.run(
            [claude, "mcp", "get", "tempo"],
            check=True,
            env=environment,
            capture_output=True,
            text=True,
        )
        if "Connected" not in status.stdout or url not in status.stdout:
            raise RuntimeError(f"Claude did not connect to {url}: {status.stdout}")


def verify_tools(actual: set[str], expected: set[str]) -> None:
    missing = expected - actual
    if missing:
        raise RuntimeError(
            f"MCP endpoint is missing tools: {', '.join(sorted(missing))}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://api.tempo.xyz/mcp")
    parser.add_argument("--claude", default="claude")
    parser.add_argument("--skip-claude", action="store_true")
    parser.add_argument("--expected-tools", nargs="+", default=sorted(EXPECTED_TOOLS))
    args = parser.parse_args()

    expected = set(args.expected_tools)
    tools = list_tools(args.url, expected)
    verify_tools(tools, expected)
    if not args.skip_claude:
        verify_claude_registration(args.claude, args.url)
    print(
        json.dumps(
            {
                "url": args.url,
                "tools": sorted(tools),
                "claude_checked": not args.skip_claude,
            }
        )
    )


if __name__ == "__main__":
    main()
