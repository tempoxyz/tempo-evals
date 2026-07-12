"""Shared deterministic checks for Tempo MCP investigation tasks."""

from __future__ import annotations

import re
from typing import Any

DOCS_PREFIX = "docs_"
DATA_PREFIXES = ("v1_", "rpc_")
DATA_SOURCE_PREFIXES = (
    "mcp://tempo/",
    "mcp://tempo-direct/",
    "mcp://tempo-code/",
)
TEMPO_DOCS_URLS = (
    "https://docs.tempo.xyz",
    "https://developers.tempo.xyz/docs",
    "https://accounts.tempo.xyz/docs",
    "https://tips.sh",
)


def is_tempo_docs_url(source: Any) -> bool:
    """Return whether source is a Tempo documentation URL, including a bare origin."""
    return isinstance(source, str) and any(
        source == base or source.startswith(f"{base}/") for base in TEMPO_DOCS_URLS
    )


def data_tool_from_source(source: Any) -> str:
    """Normalize a supported MCP evidence URI to its underlying data tool name."""
    if not isinstance(source, str):
        raise ValueError("each evidence source must be an MCP data-tool URI")
    for prefix in DATA_SOURCE_PREFIXES:
        if source.startswith(prefix):
            tool = source.removeprefix(prefix)
            if tool:
                return tool
    raise ValueError("each evidence source must be an MCP data-tool URI")


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
        tool = data_tool_from_source(source)
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
        tool = data_tool_from_source(item["source"])
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


def expected_answer_errors(
    answer: dict[str, Any], expected: dict[str, Any], events: list[dict[str, Any]]
) -> list[str]:
    """Return task-specific deterministic answer-validation failures."""
    text = answer.get("answer")
    sources = answer.get("sources")
    if not isinstance(text, str):
        return ["answer must be a string"]
    if not isinstance(sources, list):
        return ["sources must be an array"]

    errors = []
    normalized = text.casefold()
    for term in expected.get("required_terms", []):
        if not isinstance(term, str) or term.casefold() not in normalized:
            errors.append(f"answer must address task concept: {term}")
    for requirement in expected.get("required_patterns", []):
        if not isinstance(requirement, dict):
            errors.append("expected pattern requirement must be an object")
            continue
        pattern = requirement.get("pattern")
        count = requirement.get("min_matches", 1)
        name = requirement.get("name", "required evidence")
        if not isinstance(pattern, str) or not isinstance(count, int):
            errors.append("expected pattern requirement is invalid")
            continue
        if len(re.findall(pattern, text, flags=re.IGNORECASE)) < count:
            errors.append(f"answer is missing {name}")
    minimum_sources = expected.get("minimum_sources", 1)
    if not isinstance(minimum_sources, int) or len(sources) < minimum_sources:
        errors.append(f"answer must provide at least {minimum_sources} sources")
    required_tools = expected.get("required_data_tools", [])
    actual_tools = used_data_tools(events)
    for tool in required_tools:
        if not isinstance(tool, str) or tool not in actual_tools:
            errors.append(f"answer must use data tool: {tool}")
    return errors
