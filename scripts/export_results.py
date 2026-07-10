#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

JsonObject = dict[str, Any]
Numeric = float | int | str

MCP_PROFILE_SUFFIX = "-mcp"

TRIAL_COLUMNS = [
    "run_id",
    "job_name",
    "trial_name",
    "task_name",
    "task_family",
    "profile",
    "agent",
    "model",
    "attempt_index",
    "reward",
    "passed",
    "exception_type",
    "exception_message",
    "started_at",
    "finished_at",
    "duration_sec",
    "environment_setup_duration_sec",
    "agent_setup_duration_sec",
    "agent_execution_duration_sec",
    "verifier_duration_sec",
    "input_tokens",
    "cache_tokens",
    "output_tokens",
    "cost_usd",
    "task_checksum",
    "git_sha",
    "docs_source",
    "result_path",
]

SUMMARY_COLUMNS = [
    "run_id",
    "job_name",
    "model",
    "agent",
    "task_name",
    "task_family",
    "profile",
    "n_trials",
    "n_passed",
    "pass_rate",
    "n_errors",
    "mean_reward",
    "input_tokens",
    "cache_tokens",
    "output_tokens",
    "cost_usd",
]


def read_json(file_path: Path) -> JsonObject | None:
    try:
        return json.loads(file_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def read_metadata(job_dir: Path) -> JsonObject:
    return read_json(job_dir.parent / "metadata.json") or {}


def command_output(command: str, args: list[str]) -> str:
    result = subprocess.run(
        [command, *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def default_docs_source() -> str:
    sha = (read_json(Path("config/tempo-docs.lock.json")) or {}).get("sha")
    return str(sha) if sha else "public"


def default_run_id(job_dir: Path, metadata: JsonObject) -> str:
    if metadata.get("run_id"):
        return str(metadata["run_id"])
    return job_dir.parent.name if job_dir.name == "harbor-job" else job_dir.name


def default_out_dir(job_dir: Path) -> Path:
    return (
        job_dir.parent / "exports"
        if job_dir.name == "harbor-job"
        else job_dir / "exports"
    )


def build_context(job_dir: Path, run_id: str, metadata: JsonObject) -> JsonObject:
    source = metadata.get("docs_source")
    return {
        "run_id": run_id,
        "job_name": job_dir.name,
        "git_sha": metadata.get("git_sha")
        or command_output("git", ["rev-parse", "HEAD"]),
        "docs_source": source
        if isinstance(source, str) and source
        else default_docs_source(),
        "tempo_profile": profile_from_job(job_dir),
    }


def result_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("result.json")
        if "exports" not in path.relative_to(root).parts
    )


def profile_from_job(job_dir: Path) -> str:
    config = read_json(job_dir / "config.json") or {}
    for agent in as_object(config).get("agents", []):
        if not isinstance(agent, dict):
            continue
        for server in agent.get("mcp_servers") or []:
            if isinstance(server, dict) and server.get("name") == "tempo":
                return "mcp"
    return "docs"


def parse_task_name(task_name: str, tempo_profile: str = "docs") -> dict[str, str]:
    if task_name.endswith(MCP_PROFILE_SUFFIX):
        return {"task_family": task_name[: -len(MCP_PROFILE_SUFFIX)], "profile": "mcp"}
    if task_name.startswith("tempo-v1/"):
        return {"task_family": task_name, "profile": tempo_profile}
    return {"task_family": task_name, "profile": "unknown"}


def as_object(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def as_number(value: Any) -> float | int | None:
    return (
        value
        if isinstance(value, int | float) and not isinstance(value, bool)
        else None
    )


def as_string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def duration_sec(timing: Any) -> Numeric:
    timing_obj = as_object(timing)
    started = parse_time(as_string(timing_obj.get("started_at")))
    finished = parse_time(as_string(timing_obj.get("finished_at")))
    if not started or not finished:
        return ""
    return max((finished - started).total_seconds(), 0)


def collect_agent_contexts(result: JsonObject) -> list[JsonObject]:
    contexts: list[JsonObject] = []
    agent_result = as_object(result.get("agent_result"))
    if agent_result:
        contexts.append(agent_result)
    for step in (
        result.get("step_results")
        if isinstance(result.get("step_results"), list)
        else []
    ):
        step_agent_result = as_object(as_object(step).get("agent_result"))
        if step_agent_result:
            contexts.append(step_agent_result)
    return contexts


def sum_optional(objects: list[JsonObject], key: str) -> Numeric:
    total: float | int = 0
    found = False
    for obj in objects:
        value = as_number(obj.get(key))
        if value is None:
            continue
        total += value
        found = True
    return total if found else ""


def token_totals(result: JsonObject) -> dict[str, Numeric]:
    contexts = collect_agent_contexts(result)
    return {
        "input": sum_optional(contexts, "n_input_tokens"),
        "cache": sum_optional(contexts, "n_cache_tokens"),
        "output": sum_optional(contexts, "n_output_tokens"),
        "cost": sum_optional(contexts, "cost_usd"),
    }


def extract_rewards(result: JsonObject) -> dict[str, float | int]:
    raw_rewards = as_object(as_object(result.get("verifier_result")).get("rewards"))
    return {
        key: value for key, value in raw_rewards.items() if as_number(value) is not None
    }


def primary_reward(rewards: dict[str, float | int]) -> Numeric:
    if isinstance(rewards.get("reward"), int | float):
        return rewards["reward"]
    if isinstance(rewards.get("score"), int | float):
        return rewards["score"]
    values = list(rewards.values())
    return values[0] if len(values) == 1 else ""


def parse_trial_result(file_path: Path, context: JsonObject) -> JsonObject | None:
    result = read_json(file_path)
    if not result or not isinstance(result.get("task_name"), str):
        return None
    if not isinstance(result.get("trial_name"), str):
        return None

    agent_info = as_object(result.get("agent_info"))
    model_info = as_object(agent_info.get("model_info"))
    exception_info = as_object(result.get("exception_info"))
    task = parse_task_name(result["task_name"], as_string(context.get("tempo_profile")))
    rewards = extract_rewards(result)
    reward = primary_reward(rewards)
    tokens = token_totals(result)

    return {
        "run_id": context["run_id"],
        "job_name": context["job_name"],
        "trial_name": result["trial_name"],
        "task_name": result["task_name"],
        "task_family": task["task_family"],
        "profile": task["profile"],
        "agent": as_string(agent_info.get("name")),
        "model": as_string(model_info.get("name")),
        "attempt_index": 0,
        "reward": reward,
        "passed": isinstance(reward, int | float) and reward >= 1,
        "exception_type": as_string(exception_info.get("exception_type")),
        "exception_message": as_string(exception_info.get("exception_message")),
        "started_at": as_string(result.get("started_at")),
        "finished_at": as_string(result.get("finished_at")),
        "duration_sec": duration_sec(
            {
                "started_at": result.get("started_at"),
                "finished_at": result.get("finished_at"),
            },
        ),
        "environment_setup_duration_sec": duration_sec(result.get("environment_setup")),
        "agent_setup_duration_sec": duration_sec(result.get("agent_setup")),
        "agent_execution_duration_sec": duration_sec(result.get("agent_execution")),
        "verifier_duration_sec": duration_sec(result.get("verifier")),
        "input_tokens": tokens["input"],
        "cache_tokens": tokens["cache"],
        "output_tokens": tokens["output"],
        "cost_usd": tokens["cost"],
        "task_checksum": as_string(result.get("task_checksum")),
        "git_sha": context["git_sha"],
        "docs_source": context["docs_source"],
        "result_path": str(file_path),
        "rewards": rewards,
    }


def assign_attempt_indexes(rows: list[JsonObject]) -> list[JsonObject]:
    counts: dict[str, int] = {}
    sorted_rows = sorted(rows, key=lambda row: str(row["trial_name"]))
    for row in sorted_rows:
        key = "\0".join([str(row["task_name"]), str(row["agent"]), str(row["model"])])
        counts[key] = counts.get(key, 0) + 1
        row["attempt_index"] = counts[key]
    return sorted_rows


def reward_columns(rows: list[JsonObject]) -> list[str]:
    keys = sorted({key for row in rows for key in row["rewards"]})
    return [f"verifier_reward_{key}" for key in keys]


def trial_csv_rows(rows: list[JsonObject]) -> list[JsonObject]:
    csv_rows = []
    for row in rows:
        csv_row = {key: value for key, value in row.items() if key != "rewards"}
        csv_row.update(
            {f"verifier_reward_{key}": value for key, value in row["rewards"].items()},
        )
        csv_rows.append(csv_row)
    return csv_rows


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return ""
    return value


def write_csv(file_path: Path, columns: list[str], rows: list[JsonObject]) -> None:
    frame = pd.DataFrame(
        [{key: csv_value(row.get(key, "")) for key in columns} for row in rows],
        columns=columns,
    )
    frame.to_csv(file_path, index=False)


def summarize_rows(rows: list[JsonObject]) -> list[JsonObject]:
    if not rows:
        return []

    frame = pd.DataFrame(rows)
    frame["_reward"] = pd.to_numeric(frame["reward"], errors="coerce")
    frame["_passed"] = frame["passed"].astype(int)
    frame["_error"] = frame["exception_type"].astype(bool).astype(int)
    for column in ["input_tokens", "cache_tokens", "output_tokens", "cost_usd"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    group_columns = ["model", "agent", "task_name", "task_family", "profile"]
    summary = (
        frame.groupby(group_columns, as_index=False, sort=False)
        .agg(
            run_id=("run_id", "first"),
            job_name=("job_name", "first"),
            n_trials=("trial_name", "size"),
            n_passed=("_passed", "sum"),
            n_errors=("_error", "sum"),
            mean_reward=("_reward", "mean"),
            input_tokens=("input_tokens", "sum"),
            cache_tokens=("cache_tokens", "sum"),
            output_tokens=("output_tokens", "sum"),
            cost_usd=("cost_usd", "sum"),
        )
        .assign(pass_rate=lambda data: data["n_passed"] / data["n_trials"])
        .sort_values(["model", "task_name", "profile"], kind="stable")
    )
    summary["mean_reward"] = summary["mean_reward"].where(
        summary["mean_reward"].notna(),
        "",
    )
    return summary[SUMMARY_COLUMNS].to_dict("records")


def write_summary_json(
    file_path: Path,
    job_dir: Path,
    run_id: str,
    trials: list[JsonObject],
    summary: list[JsonObject],
) -> None:
    reward_keys = sorted({key for row in trials for key in row["rewards"]})
    file_path.write_text(
        f"{
            json.dumps(
                {
                    'schema_version': 1,
                    'run_id': run_id,
                    'job_dir': str(job_dir),
                    'exported_at': datetime.now().astimezone().isoformat(),
                    'n_trials': len(trials),
                    'reward_keys': reward_keys,
                    'summary': summary,
                },
                indent=2,
            )
        }\n",
    )


def export_results(
    job_dir: str | Path,
    run_id: str | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    job_path = Path(job_dir).resolve()
    if not job_path.exists():
        msg = f"Job directory not found: {job_path}"
        raise FileNotFoundError(msg)

    metadata = read_metadata(job_path)
    effective_run_id = run_id or default_run_id(job_path, metadata)
    out_path = (
        Path(out_dir).resolve() if out_dir else default_out_dir(job_path).resolve()
    )
    context = build_context(job_path, effective_run_id, metadata)
    trials = assign_attempt_indexes(
        [
            row
            for file_path in result_files(job_path)
            if (row := parse_trial_result(file_path, context)) is not None
        ],
    )
    summary = summarize_rows(trials)

    out_path.mkdir(parents=True, exist_ok=True)
    write_csv(
        out_path / "trials.csv",
        [*TRIAL_COLUMNS, *reward_columns(trials)],
        trial_csv_rows(trials),
    )
    write_csv(out_path / "summary.csv", SUMMARY_COLUMNS, summary)
    write_summary_json(
        out_path / "summary.json", job_path, effective_run_id, trials, summary
    )

    return {
        "run_id": effective_run_id,
        "out_dir": str(out_path),
        "trials": trials,
        "summary": summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="results:export",
        description="Export Harbor trial results to CSV and JSON.",
    )
    parser.add_argument(
        "--job",
        required=True,
        help="Harbor job directory, for example runs/<run_id>/harbor-job",
    )
    parser.add_argument("--run-id", help="Run id to write into exports")
    parser.add_argument("--out-dir", help="Output directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = export_results(args.job, run_id=args.run_id, out_dir=args.out_dir)
    print(f"Exported {len(result['trials'])} trials to {result['out_dir']}")


if __name__ == "__main__":
    main()
