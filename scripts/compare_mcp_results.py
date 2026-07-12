#!/usr/bin/env python3
"""Compare exports from matched mcp-direct and mcp-code Harbor runs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

METRICS = [
    "input_tokens",
    "cache_tokens",
    "output_tokens",
    "model_turns",
    "mcp_calls",
    "duration_sec",
    "agent_execution_duration_sec",
    "cost_usd",
]

TASK_QUALITY_SUMMARY_COLUMNS = [
    "task_family",
    "model",
    "agent",
    "task_checksum",
    "docs_source",
    "n_attempts",
    "n_both_valid",
    "direct_quality_coverage",
    "code_quality_coverage",
    "paired_quality_coverage",
    "direct_mean_quality",
    "direct_median_quality",
    "direct_quality_at_k",
    "code_mean_quality",
    "code_median_quality",
    "code_quality_at_k",
    "mean_quality_delta",
    "median_quality_delta",
]

OVERALL_QUALITY_SUMMARY_COLUMNS = [
    "model",
    "agent",
    "docs_source",
    "n_tasks",
    "n_paired_attempts",
    "both_valid_rate",
    "direct_quality_coverage",
    "code_quality_coverage",
    "paired_quality_coverage",
    "direct_mean_quality",
    "direct_median_quality",
    "direct_quality_at_k",
    "code_mean_quality",
    "code_median_quality",
    "code_quality_at_k",
    "mean_quality_delta",
    "median_quality_delta",
]
KEYS = [
    "pair_id",
    "task_family",
    "model",
    "agent",
    "attempt_index",
    "task_checksum",
    "docs_source",
]


def read_trials(path: str) -> pd.DataFrame:
    frame = pd.read_csv(path, keep_default_na=False)
    required = set(KEYS + ["profile", "passed", *METRICS])
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")
    if "quality" not in frame.columns:
        frame["quality"] = pd.NA
    return frame


def compare(direct_path: str, code_path: str) -> pd.DataFrame:
    direct = read_trials(direct_path)
    code = read_trials(code_path)
    direct = direct[direct["profile"] == "mcp-direct"].copy()
    code = code[code["profile"] == "mcp-code"].copy()
    if direct.empty or code.empty:
        raise ValueError("inputs must contain mcp-direct and mcp-code trials")
    if (
        not direct["pair_id"].astype(str).str.strip().all()
        or not code["pair_id"].astype(str).str.strip().all()
    ):
        raise ValueError("all MCP trials must include a pair_id")
    merged = direct.merge(
        code, on=KEYS, suffixes=("_direct", "_code"), validate="one_to_one"
    )
    for metric in METRICS:
        merged[f"{metric}_delta"] = pd.to_numeric(
            merged[f"{metric}_direct"], errors="coerce"
        ) - pd.to_numeric(merged[f"{metric}_code"], errors="coerce")
    valid_column = "eligible" if "eligible_direct" in merged.columns else "passed"
    merged["both_valid"] = merged[f"{valid_column}_direct"].astype(str).str.lower().eq(
        "true"
    ) & merged[f"{valid_column}_code"].astype(str).str.lower().eq("true")
    for profile in ("direct", "code"):
        merged[f"quality_{profile}"] = pd.to_numeric(
            merged[f"quality_{profile}"], errors="coerce"
        )
    merged["quality_comparable"] = (
        merged["both_valid"]
        & merged["quality_direct"].notna()
        & merged["quality_code"].notna()
    )
    merged["quality_delta"] = (merged["quality_code"] - merged["quality_direct"]).where(
        merged["quality_comparable"]
    )
    return merged


def summarize_quality_comparison(
    compared: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    group_columns = ["task_family", "model", "agent", "task_checksum", "docs_source"]
    frame = compared.copy()
    frame["_both_valid"] = frame["both_valid"].astype(int)
    frame["_direct_quality"] = pd.to_numeric(frame["quality_direct"], errors="coerce")
    frame["_code_quality"] = pd.to_numeric(frame["quality_code"], errors="coerce")
    frame["_quality_delta"] = pd.to_numeric(frame["quality_delta"], errors="coerce")
    task_aggregate = (
        frame.groupby(group_columns, as_index=False, sort=False)
        .agg(
            n_attempts=("attempt_index", "size"),
            n_both_valid=("_both_valid", "sum"),
            direct_quality_count=("_direct_quality", "count"),
            code_quality_count=("_code_quality", "count"),
            paired_quality_count=("_quality_delta", "count"),
            direct_mean_quality=("_direct_quality", "mean"),
            direct_median_quality=("_direct_quality", "median"),
            direct_quality_at_k=("_direct_quality", "max"),
            code_mean_quality=("_code_quality", "mean"),
            code_median_quality=("_code_quality", "median"),
            code_quality_at_k=("_code_quality", "max"),
            mean_quality_delta=("_quality_delta", "mean"),
            median_quality_delta=("_quality_delta", "median"),
        )
        .assign(
            direct_quality_coverage=lambda data: (
                data["direct_quality_count"] / data["n_attempts"]
            ),
            code_quality_coverage=lambda data: (
                data["code_quality_count"] / data["n_attempts"]
            ),
            paired_quality_coverage=lambda data: (
                data["paired_quality_count"] / data["n_attempts"]
            ),
        )
    )
    task_summary = task_aggregate[TASK_QUALITY_SUMMARY_COLUMNS]
    overall = (
        task_aggregate.groupby(
            ["model", "agent", "docs_source"], as_index=False, sort=False
        )
        .agg(
            n_tasks=("task_family", "size"),
            n_paired_attempts=("n_attempts", "sum"),
            n_both_valid=("n_both_valid", "sum"),
            direct_quality_count=("direct_quality_count", "sum"),
            code_quality_count=("code_quality_count", "sum"),
            paired_quality_count=("paired_quality_count", "sum"),
            direct_mean_quality=("direct_mean_quality", "mean"),
            direct_median_quality=("direct_median_quality", "median"),
            direct_quality_at_k=("direct_quality_at_k", "mean"),
            code_mean_quality=("code_mean_quality", "mean"),
            code_median_quality=("code_median_quality", "median"),
            code_quality_at_k=("code_quality_at_k", "mean"),
            mean_quality_delta=("mean_quality_delta", "mean"),
            median_quality_delta=("median_quality_delta", "median"),
        )
        .assign(
            both_valid_rate=lambda data: (
                data["n_both_valid"] / data["n_paired_attempts"]
            ),
            direct_quality_coverage=lambda data: (
                data["direct_quality_count"] / data["n_paired_attempts"]
            ),
            code_quality_coverage=lambda data: (
                data["code_quality_count"] / data["n_paired_attempts"]
            ),
            paired_quality_coverage=lambda data: (
                data["paired_quality_count"] / data["n_paired_attempts"]
            ),
        )
    )
    return task_summary, overall[OVERALL_QUALITY_SUMMARY_COLUMNS]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare direct and code MCP exports")
    parser.add_argument("--direct", required=True, help="direct run exports/trials.csv")
    parser.add_argument("--code", required=True, help="code run exports/trials.csv")
    parser.add_argument("--out", required=True, help="output CSV path")
    parser.add_argument("--task-summary-out", help="per-task quality summary CSV")
    parser.add_argument("--overall-summary-out", help="overall quality summary CSV")
    args = parser.parse_args()
    result = compare(args.direct, args.code)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out_path, index=False)
    task_summary, overall_summary = summarize_quality_comparison(result)
    task_summary_path = (
        Path(args.task_summary_out)
        if args.task_summary_out
        else out_path.with_name(f"{out_path.stem}-task-quality.csv")
    )
    overall_summary_path = (
        Path(args.overall_summary_out)
        if args.overall_summary_out
        else out_path.with_name(f"{out_path.stem}-overall-quality.csv")
    )
    task_summary.to_csv(task_summary_path, index=False)
    overall_summary.to_csv(overall_summary_path, index=False)
    print(f"Wrote {len(result)} matched trials to {args.out}")
    print(f"Wrote task quality summary to {task_summary_path}")
    print(f"Wrote overall quality summary to {overall_summary_path}")


if __name__ == "__main__":
    main()
