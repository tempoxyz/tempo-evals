"""Shared deterministic checks for Tempo MCP investigation tasks."""

from __future__ import annotations

from typing import Any

DOCS_PREFIX = "docs_"
DATA_PREFIXES = ("v1_", "rpc_")
DATA_SOURCE_PREFIX = "mcp://tempo/"


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


def validated_data_evidence(
    events: list[dict[str, Any]], evidence: Any
) -> list[dict[str, str]]:
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("evidence must be a non-empty array")
    used_tools = used_data_tools(events)
    validated: list[dict[str, str]] = []
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("each evidence item must be an object")
        source = item.get("source")
        claim = item.get("claim")
        if not isinstance(source, str) or not source.startswith(DATA_SOURCE_PREFIX):
            raise ValueError("each evidence source must be an MCP data-tool URI")
        tool = source.removeprefix(DATA_SOURCE_PREFIX)
        if tool not in used_tools:
            raise ValueError(f"evidence source was not used: {tool}")
        if not isinstance(claim, str) or not claim.strip():
            raise ValueError("each evidence item must include a non-empty claim")
        validated.append({"source": source, "claim": claim})
    return validated


def evidence_summary(
    events: list[dict[str, Any]], evidence: list[dict[str, str]]
) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for item in evidence:
        tool = item["source"].removeprefix(DATA_SOURCE_PREFIX)
        calls = [
            {
                "arguments": event.get("arguments", {}),
                "response_sha256": event.get("response_sha256", ""),
            }
            for event in events
            if event.get("allowed") is True and event.get("tool") == tool
        ]
        summary.append({**item, "calls": calls})
    return summary
