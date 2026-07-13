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
REWARD_COMPONENTS = (
    "schema_valid",
    "docs_source_valid",
    "mcp_tool_mix_valid",
    "data_evidence_valid",
    "task_requirements_valid",
)


def component_reward(components: dict[str, int]) -> float:
    """Return the equal-weight deterministic correctness score."""
    return sum(int(bool(components.get(key))) for key in REWARD_COMPONENTS) / len(
        REWARD_COMPONENTS
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
            tool = (
                source.removeprefix(prefix)
                .split("?", maxsplit=1)[0]
                .split("#", maxsplit=1)[0]
            )
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
    """Validate data evidence while preserving recognized docs citations as warnings."""
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
    sources = answer.get("sources")
    if not isinstance(sources, list):
        return ["sources must be an array"]

    errors = []
    structured = expected.get("structured")
    if not isinstance(structured, dict):
        errors.append("expected structured requirements must be an object")
    else:
        required_fields = structured.get("required_fields", [])
        if not isinstance(required_fields, list):
            errors.append("expected required_fields must be an array")
        else:
            for field in required_fields:
                value = answer.get(field) if isinstance(field, str) else None
                if value in (None, "") or value == [] or value == {}:
                    errors.append(f"answer is missing structured field: {field}")
        array_fields = structured.get("array_fields", {})
        if not isinstance(array_fields, dict):
            errors.append("expected array_fields must be an object")
        else:
            for field, requirement in array_fields.items():
                value = answer.get(field)
                if not isinstance(value, list):
                    errors.append(f"answer field must be an array: {field}")
                    continue
                if not isinstance(requirement, dict):
                    errors.append(
                        f"expected array field requirement is invalid: {field}"
                    )
                    continue
                min_items = requirement.get("min_items", 1)
                if not isinstance(min_items, int) or len(value) < min_items:
                    errors.append(
                        f"answer field needs at least {min_items} item(s): {field}"
                    )
                    continue
                item_fields = requirement.get("item_required_fields", [])
                item_patterns = requirement.get("item_patterns", {})
                if not isinstance(item_fields, list) or not isinstance(
                    item_patterns, dict
                ):
                    errors.append(f"expected item requirement is invalid: {field}")
                    continue
                for item_field, pattern in item_patterns.items():
                    if not isinstance(item_field, str) or not isinstance(pattern, str):
                        errors.append(f"expected item requirement is invalid: {field}")
                        continue
                for index, item in enumerate(value):
                    if not isinstance(item, dict):
                        errors.append(
                            f"answer item must be an object: {field}[{index}]"
                        )
                        continue
                    for item_field in item_fields:
                        item_value = (
                            item.get(item_field)
                            if isinstance(item_field, str)
                            else None
                        )
                        item_label = f"{field}[{index}].{item_field}"
                        if item_field == "evidence_refs":
                            if not isinstance(item_value, list):
                                errors.append(
                                    f"answer item has invalid field: {item_label}"
                                )
                            continue
                        if (
                            item_value in (None, "")
                            or item_value == []
                            or item_value == {}
                        ):
                            errors.append(f"answer item is missing field: {item_label}")
                    for item_field, pattern in item_patterns.items():
                        item_value = item.get(item_field)
                        if not isinstance(item_value, str) or not re.search(
                            pattern, item_value, flags=re.IGNORECASE
                        ):
                            errors.append(
                                f"answer item field must match pattern: "
                                f"{field}[{index}].{item_field}"
                            )
                any_item_patterns = requirement.get("any_item_patterns", [])
                if not isinstance(any_item_patterns, list):
                    errors.append(f"expected item requirement is invalid: {field}")
                    continue
                for pattern_requirement in any_item_patterns:
                    if not isinstance(pattern_requirement, dict):
                        errors.append(f"expected item requirement is invalid: {field}")
                        continue
                    fields = pattern_requirement.get("fields")
                    pattern = pattern_requirement.get("pattern")
                    if not isinstance(fields, list) or not isinstance(pattern, str):
                        errors.append(f"expected item requirement is invalid: {field}")
                        continue
                    if not any(
                        isinstance(item, dict)
                        and any(
                            isinstance(item.get(candidate), str)
                            and re.search(pattern, item[candidate], flags=re.IGNORECASE)
                            for candidate in fields
                            if isinstance(candidate, str)
                        )
                        for item in value
                    ):
                        errors.append(
                            f"answer field needs an item matching pattern: {field}"
                        )
    minimum_sources = expected.get("minimum_sources", 1)
    if not isinstance(minimum_sources, int) or len(sources) < minimum_sources:
        errors.append(f"answer must provide at least {minimum_sources} sources")
    required_tools = expected.get("required_data_tools", [])
    actual_tools = used_data_tools(events)
    for tool in required_tools:
        if not isinstance(tool, str) or tool not in actual_tools:
            errors.append(f"answer must use data tool: {tool}")
    required_tool_groups = expected.get("required_data_tool_any_of", [])
    if not isinstance(required_tool_groups, list):
        errors.append("expected required_data_tool_any_of must be an array")
    else:
        for group in required_tool_groups:
            if not isinstance(group, list) or not group or not all(
                isinstance(tool, str) for tool in group
            ):
                errors.append("expected data tool group is invalid")
            elif not actual_tools.intersection(group):
                errors.append(
                    "answer must use one data tool from: " + ", ".join(group)
                )
    return errors
