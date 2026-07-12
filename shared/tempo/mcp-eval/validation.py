"""Shared deterministic checks for Tempo MCP investigation tasks."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

DOCS_PREFIX = "docs_"
DATA_PREFIXES = ("v1_", "rpc_")
DATA_SOURCE_PREFIXES = (
    "mcp://tempo/",
    "mcp://tempo-direct/",
    "mcp://tempo-code/",
)
TEMPO_DOCS_ORIGINS = (
    ("docs.tempo.xyz", "/"),
    ("developers.tempo.xyz", "/docs"),
    ("accounts.tempo.xyz", "/docs"),
    ("tips.sh", "/"),
)


def is_tempo_docs_url(source: Any) -> bool:
    """Return whether source is an allowed Tempo docs URL, including its bare origin."""
    if not isinstance(source, str):
        return False
    parsed = urlparse(source)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    path = parsed.path or "/"
    for hostname, allowed_path in TEMPO_DOCS_ORIGINS:
        if parsed.hostname != hostname:
            continue
        if (
            allowed_path == "/"
            or path == allowed_path
            or path.startswith(f"{allowed_path}/")
        ):
            return True
    return False


def mcp_tool_from_source(source: Any) -> str:
    """Normalize a supported MCP evidence URI to its underlying tool name."""
    if not isinstance(source, str):
        raise ValueError("each evidence source must be an MCP data-tool URI")
    for prefix in DATA_SOURCE_PREFIXES:
        if source.startswith(prefix):
            tool = source.removeprefix(prefix)
            if tool:
                return tool
    raise ValueError("each evidence source must be an MCP data-tool URI")


def data_tool_from_source(source: Any) -> str:
    """Return the data tool named by source, rejecting docs and unknown MCP tools."""
    tool = mcp_tool_from_source(source)
    if not tool.startswith(DATA_PREFIXES) or docs_tool_name(tool):
        raise ValueError("each evidence source must be an MCP data-tool URI")
    return tool


def docs_tool_name(tool: str) -> bool:
    """Return whether tool is a direct, path-style, or legacy docs tool alias."""
    return tool.startswith((DOCS_PREFIX, "docs/", "v1_docs_"))


def docs_evidence_source(source: Any) -> bool:
    """Return whether source is non-data provenance on an approved Tempo surface."""
    if is_tempo_docs_url(source):
        return True
    try:
        tool = mcp_tool_from_source(source)
        return docs_tool_name(tool) or not tool.startswith(DATA_PREFIXES)
    except ValueError:
        return False


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
) -> dict[str, Any]:
    """Validate trace-backed data evidence without rejecting recognized docs citations."""
    used_tools = used_data_tools(events)
    validated: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(evidence, list) or not evidence:
        return {
            "evidence": validated,
            "errors": ["evidence must be a non-empty array"],
            "warnings": warnings,
        }
    for item in evidence:
        if not isinstance(item, dict):
            errors.append("each evidence item must be an object")
            continue
        source = item.get("source")
        claim = item.get("claim")
        if not isinstance(claim, str) or not claim.strip():
            errors.append("each evidence item must include a non-empty claim")
            continue
        if docs_evidence_source(source):
            warnings.append(
                "documentation provenance in evidence does not count as data evidence"
            )
            continue
        try:
            tool = data_tool_from_source(source)
        except ValueError as error:
            errors.append(str(error))
            continue
        if tool not in used_tools:
            errors.append(f"evidence source was not used: {tool}")
            continue
        validated.append({"source": source, "claim": claim})
    if not validated:
        errors.append("evidence must include at least one trace-backed MCP data tool")
    return {"evidence": validated, "errors": errors, "warnings": warnings}


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
