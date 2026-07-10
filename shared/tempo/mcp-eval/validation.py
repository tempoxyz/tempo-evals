"""Shared deterministic checks for Tempo MCP investigation tasks."""

from __future__ import annotations

from typing import Any

DOCS_PREFIX = "docs_"
DATA_PREFIXES = ("v1_", "rpc_")


def has_required_tool_mix(events: list[dict[str, Any]]) -> bool:
    """Return whether an arm used both chain data and Tempo documentation."""
    tools = {
        event.get("tool")
        for event in events
        if event.get("allowed") is True and isinstance(event.get("tool"), str)
    }
    return any(tool.startswith(DOCS_PREFIX) for tool in tools) and any(
        tool.startswith(DATA_PREFIXES) for tool in tools
    )


def used_data_tools(events: list[dict[str, Any]]) -> set[str]:
    return {
        tool
        for event in events
        if event.get("allowed") is True
        and isinstance((tool := event.get("tool")), str)
        and tool.startswith(DATA_PREFIXES)
    }
