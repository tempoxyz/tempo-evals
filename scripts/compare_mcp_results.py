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
    "cost_usd",
]
KEYS = [
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
    return frame


def compare(direct_path: str, code_path: str) -> pd.DataFrame:
    direct = read_trials(direct_path)
    code = read_trials(code_path)
    direct = direct[direct["profile"] == "mcp-direct"].copy()
    code = code[code["profile"] == "mcp-code"].copy()
    if direct.empty or code.empty:
        raise ValueError("inputs must contain mcp-direct and mcp-code trials")
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
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare direct and code MCP exports")
    parser.add_argument("--direct", required=True, help="direct run exports/trials.csv")
    parser.add_argument("--code", required=True, help="code run exports/trials.csv")
    parser.add_argument("--out", required=True, help="output CSV path")
    args = parser.parse_args()
    result = compare(args.direct, args.code)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.out, index=False)
    print(f"Wrote {len(result)} matched trials to {args.out}")


if __name__ == "__main__":
    main()
