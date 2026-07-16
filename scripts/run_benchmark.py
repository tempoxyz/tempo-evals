#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import jinja2
import tomlkit
import yaml


class BenchmarkKey(StrEnum):
    TEMPO = "tempo"
    TEMPO_MCP = "tempo-mcp"
    MPP = "mpp"


# All run variant data (job specs, prefixes, auth flags, Daytona runner
# settings) lives in config/variants.yaml. `npm run sync` compiles each
# variant's "job" spec into config/generated/, and runs use those checked-in
# files.
RUN_CONFIG: dict[str, Any] = yaml.safe_load(Path("config/variants.yaml").read_text())
TASKS_CONFIG: dict[str, Any] = yaml.safe_load(Path("config/tasks.yaml").read_text())
VARIANTS: dict[str, dict[str, Any]] = RUN_CONFIG["variants"]
RAW_BENCHMARKS: dict[str, dict[str, Any]] = yaml.safe_load(
    Path("config/benchmarks.yaml").read_text()
)["benchmarks"]
BENCHMARKS: dict[BenchmarkKey, dict[str, Any]] = {
    key: RAW_BENCHMARKS[key.value] for key in BenchmarkKey
}
TEMPO_PROFILES: list[dict[str, Any]] = TASKS_CONFIG["profiles"]


def tempo_profile(profile_id: str) -> dict[str, Any]:
    for profile in TEMPO_PROFILES:
        if profile["id"] == profile_id:
            return profile
    raise RuntimeError(f"Missing Tempo profile: {profile_id}")


DOCS_PROFILE = tempo_profile("docs")
MCP_PROFILE = tempo_profile("mcp")
MCP_DIRECT_PROFILE = tempo_profile("mcp-direct")
MCP_CODE_PROFILE = tempo_profile("mcp-code")
PROFILE_IDS = tuple(profile["id"] for profile in TEMPO_PROFILES)
DEFAULT_PROFILE_IDS = (DOCS_PROFILE["id"], MCP_PROFILE["id"])


def usage() -> None:
    print("""Usage: npm run <script> -- [options]

Direct: uv run python scripts/run_benchmark.py <variant> [options]

Variants:
  local-oracle       Oracle validation on local Docker
  local-oracle-dev   Fast oracle iteration on local Docker
  local-agent        Claude Code matrix on local Docker
  local-agent-dev    One-attempt Claude Code smoke run on local Docker
  model              One local harness/model run over tasks
  daytona-oracle     Oracle validation on Daytona
  daytona-agent      Claude Code matrix on Daytona
  daytona-agent-dev  One-attempt Claude Code smoke run on Daytona
  production-daytona Production Daytona run over configured models
  sync               Sync shared MPP assets and compiled job configs
  dataset            Sync shared assets and Harbor dataset digests
  build-base         Build the shared task base image locally
  check-dataset      Verify dataset digests are fresh
  check-generated    Verify sync leaves no generated diff
  clean-jobs         Remove local Harbor job outputs
  clean              Remove local Harbor job outputs and Daytona staging cache

Options:
  --env-file PATH          Load env file for Harbor and preflight checks
                           (default: .env when present)
  --job-name NAME          Override generated job name; production runs use it
                           as the run group and include the profile suffix
  --models-config PATH     Model matrix config
                           (default: config/models.production.yaml)
  --n-attempts N          Override production attempts per task and model
                          (default: 3)
  --concurrency N         Override n_concurrent_trials per profile job
                          (default: 16 for production runs)
  --agent-concurrency N   Override per-profile agent concurrency pools
  --max-retries N         Retry transient trial/setup failures
                          (default: 2 for Daytona runs)
  --agent NAME            Agent for the model variant (default: claude-code)
  --model NAME            Model for the model variant (default: haiku)
  --task-filter GLOB      Include matching task names for model and config variants
  --task-suite SUITE      Task family: tempo, tempo-mcp, mpp, or all
                          (default: tempo; use all explicitly for full matrix)
  --n-tasks N             Limit task count for the model variant
  --tasks PATH            Task dataset path for dataset/model variants
                          (default: tasks/tempo-v1)
  --docs-sha SHA          Override the pinned documentation revision for a run
  --profile PROFILE       Access profile: docs, mcp, mcp-direct, mcp-code,
                          mcp-both, or all (default: docs)
  --base-image REF        Immutable Daytona base image tag or digest (required)
  --no-force-build        Ask Harbor to reuse Docker environment builds
  --no-delete             Keep Harbor environments after the run for debugging
  --disable-verification  Skip verifier execution
  --install-only          Run agent setup/install only and skip verification
  --debug                 Enable Harbor debug logging
  --no-sync               Skip task asset and dataset sync before running Harbor
""")


def read_positive_integer(value: str, option: str) -> str:
    if not value.isdecimal() or int(value) < 1:
        msg = f"{option} must be a positive integer"
        raise argparse.ArgumentTypeError(msg)
    return value


def parse_args(argv: list[str]) -> tuple[str | None, dict[str, Any]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("variant", nargs="?")
    parser.add_argument("--help", "-h", action="store_true", dest="help")
    parser.add_argument("--env-file", default=".env" if Path(".env").exists() else None)
    parser.add_argument("--job-name")
    parser.add_argument("--models-config")
    parser.add_argument(
        "--n-attempts",
        type=lambda value: read_positive_integer(value, "--n-attempts"),
    )
    parser.add_argument(
        "--concurrency",
        type=lambda value: read_positive_integer(value, "--concurrency"),
    )
    parser.add_argument(
        "--agent-concurrency",
        type=lambda value: read_positive_integer(value, "--agent-concurrency"),
    )
    parser.add_argument(
        "--max-retries",
        type=lambda value: read_positive_integer(value, "--max-retries"),
    )
    parser.add_argument("--agent")
    parser.add_argument("--model")
    parser.add_argument("--task-filter")
    parser.add_argument("--task-suite", choices=["tempo", "tempo-mcp", "mpp", "all"])
    parser.add_argument(
        "--n-tasks", type=lambda value: read_positive_integer(value, "--n-tasks")
    )
    parser.add_argument("--tasks")
    parser.add_argument("--docs-sha")
    parser.add_argument(
        "--profile",
        choices=(*PROFILE_IDS, "mcp-both", "all"),
        default=DOCS_PROFILE["id"],
    )
    parser.add_argument("--base-image")
    parser.add_argument("--no-sync", action="store_false", dest="sync", default=True)
    parser.add_argument("--no-force-build", action="store_true")
    parser.add_argument("--no-delete", action="store_true")
    parser.add_argument("--disable-verification", action="store_true")
    parser.add_argument("--install-only", action="store_true")
    parser.add_argument("--debug", action="store_true")

    namespace = parser.parse_args(argv)
    return namespace.variant, vars(namespace)


def load_env_file(file_path: str | None) -> None:
    if not file_path:
        return
    path = Path(file_path)
    if not path.exists():
        msg = f"Env file not found: {file_path}"
        raise RuntimeError(msg)
    for line in path.read_text().splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        key, separator, raw_value = trimmed.partition("=")
        if not separator or not key.isidentifier():
            continue
        os.environ.setdefault(key, raw_value.strip("\"'"))


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def production_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def run(command: str, args: list[str]) -> None:
    result = subprocess.run([command, *args], env=os.environ, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def run_status(command: str, args: list[str]) -> int:
    return subprocess.run([command, *args], env=os.environ, check=False).returncode


def run_python(script: str, args: list[str] | None = None) -> None:
    run(sys.executable, [script, *(args or [])])


DOCS_SHA_PATTERN = re.compile(r"[0-9a-fA-F]{7,40}")
DOCS_ACCESS_LOG = "/var/log/tempo-docs/access.log"
DOCS_TLS_DIR = "docs-tls"
DOCS_CA_FILE = "ca.crt"
DOCS_CA_DESTINATION = "/usr/local/share/ca-certificates/tempo-bench-docs.crt"
MCP_UPSTREAM_PLACEHOLDER = "${TEMPO_MCP_EVAL_URL:-https://api.tempo.xyz/mcp}"
DOCS_TLS_VALIDITY_DAYS = "30"


def read_docs_lock() -> dict[str, Any]:
    lock_path = Path("config/tempo-docs.lock.json")
    lock = json.loads(lock_path.read_text())
    if (
        lock.get("schemaVersion") != 1
        or not isinstance(lock.get("repo"), str)
        or not lock["repo"]
    ):
        msg = f"Invalid Tempo docs lock: {lock_path}"
        raise RuntimeError(msg)
    if lock.get("sha") is not None and not isinstance(lock["sha"], str):
        raise RuntimeError(f"Invalid Tempo docs SHA in {lock_path}")
    return lock


def docs_source(options: dict[str, Any]) -> dict[str, str]:
    lock = read_docs_lock()
    sha = options.get("docs_sha") or lock.get("sha")
    if not sha:
        return {"mode": "public"}
    if not isinstance(sha, str) or not DOCS_SHA_PATTERN.fullmatch(sha):
        raise RuntimeError(f"Invalid Tempo docs SHA: {sha!r}")
    return {"mode": "pinned", "repo": lock["repo"], "sha": sha.lower()}


def uses_live_mcp_eval(options: dict[str, Any]) -> bool:
    return options.get("task_suite") == "tempo-mcp"


def ensure_docs_bundle(source: dict[str, str]) -> str | None:
    if source["mode"] == "public":
        return None
    run_python("scripts/prepare_docs_bundle.py", ["--sha", source["sha"]])
    bundle_path = Path(".cache") / "tempo-docs" / source["sha"] / "public"
    bundle_path = bundle_path.resolve()
    if not (bundle_path / "developers" / "llms.txt").exists():
        msg = f"Pinned Tempo docs bundle was not created at {bundle_path}"
        raise RuntimeError(msg)
    return str(bundle_path)


def preflight(variant: dict[str, Any], options: dict[str, Any]) -> None:
    effective_agent = options.get("agent") or variant.get("default_agent")
    needs_agent_auth = variant.get("needs_agent_auth") and effective_agent != "oracle"
    if needs_agent_auth and not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "Missing Claude Code and verifier judge auth: set ANTHROPIC_API_KEY."
        )
    if (
        variant.get("needs_daytona_auth")
        and not os.environ.get("DAYTONA_API_KEY")
        and not (
            os.environ.get("DAYTONA_JWT_TOKEN")
            and os.environ.get("DAYTONA_ORGANIZATION_ID")
        )
    ):
        msg = (
            "Missing Daytona auth: set DAYTONA_API_KEY, or both DAYTONA_JWT_TOKEN "
            "and DAYTONA_ORGANIZATION_ID."
        )
        raise RuntimeError(msg)


def preflight_mcp_target(options: dict[str, Any]) -> None:
    if options["profile"] not in {MCP_DIRECT_PROFILE["id"], MCP_CODE_PROFILE["id"]}:
        return
    run_python(
        "scripts/verify_tempo_mcp.py",
        ["--url", os.environ.get("TEMPO_MCP_EVAL_URL", "https://api.tempo.xyz/mcp")],
    )


def preflight_production_agents(model_config: dict[str, Any]) -> None:
    if any(model["agent"] == "codex" for model in model_config["models"]) and not (
        os.environ.get("OPENAI_API_KEY")
    ):
        raise RuntimeError("Missing Codex auth: set OPENAI_API_KEY.")


def task_path(options: dict[str, Any]) -> str:
    return options.get("tasks") or "tasks/tempo-v1"


def sync_generated() -> None:
    run_python("scripts/sync_shared.py")
    compile_job_configs()


def base_image_ref() -> str:
    return str(read_yaml("config/tasks.yaml")["base_image"])


def build_base_image() -> None:
    """Build the shared task base image locally so task Dockerfiles can
    resolve their FROM without pulling. Docker layer caching makes repeat
    builds cheap. Daytona runs pull the published image instead."""
    run(
        "docker",
        [
            "build",
            "-t",
            base_image_ref(),
            "-f",
            "shared/global/docker/base/Dockerfile",
            ".",
        ],
    )


def daytona_base_image(options: dict[str, Any]) -> str:
    image = options.get("base_image")
    if not image:
        raise RuntimeError(
            "Daytona requires --base-image. Publish a branch image in CI and use its "
            "tag or digest."
        )
    return image


def sync_dataset(options: dict[str, Any]) -> None:
    sync_generated()
    run("uv", ["run", "harbor", "sync", task_path(options)])


def parse_model_config(file_path: str, agent_concurrency: str | None) -> dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        msg = f"Model config not found: {file_path}"
        raise RuntimeError(msg)
    parsed = yaml.safe_load(path.read_text()) or {}
    raw_models = parsed.get("models") if isinstance(parsed, dict) else []
    models = [
        normalize_production_model(model, index, file_path, agent_concurrency)
        for index, model in enumerate(
            raw_models if isinstance(raw_models, list) else []
        )
    ]
    if not models:
        msg = f"No models configured in {file_path}"
        raise RuntimeError(msg)
    return {"models": models}


def normalize_production_model(
    value: Any,
    index: int,
    file_path: str,
    agent_concurrency: str | None,
) -> dict[str, Any]:
    if isinstance(value, str):
        return {
            "agent": "claude-code",
            "model_name": value,
            "n_concurrent": agent_concurrency,
        }
    if not isinstance(value, dict):
        msg = f"Invalid model entry {index + 1} in {file_path}"
        raise RuntimeError(msg)
    model_name = string_field(value, "model_name") or string_field(value, "model")
    if not model_name:
        msg = f"Missing model_name for model entry {index + 1} in {file_path}"
        raise RuntimeError(msg)
    n_concurrent = string_field(value, "n_concurrent")
    return {
        "agent": string_field(value, "agent")
        or string_field(value, "agent_name")
        or "claude-code",
        "model_name": model_name,
        "n_concurrent": agent_concurrency
        or validate_optional_positive_integer(n_concurrent, "n_concurrent"),
        "concurrency_group": string_field(value, "concurrency_group"),
    }


def string_field(obj: dict[str, Any], key: str) -> str | None:
    value = obj.get(key)
    return None if value is None else str(value)


def validate_optional_positive_integer(value: str | None, option: str) -> str | None:
    return None if value is None else read_positive_integer(value, option)


def production_job_dir(job_name: str) -> Path:
    if job_name in {"", ".", ".."} or Path(job_name).name != job_name:
        raise RuntimeError("Production job name must be one path component")
    return Path("jobs") / job_name


def benchmark_key(value: str | BenchmarkKey | None) -> BenchmarkKey:
    return BenchmarkKey(value or BenchmarkKey.TEMPO)


def run_benchmark_key(variant: dict[str, Any], task_suite: str | None) -> BenchmarkKey:
    # An all-suite run combines datasets, so retain the variant's benchmark
    # identity for the generated job name.
    if task_suite == "all":
        return benchmark_key(variant.get("benchmark"))
    return benchmark_key(task_suite or variant.get("benchmark"))


def dump_yaml(value: dict[str, Any]) -> str:
    return yaml.safe_dump(value, sort_keys=False, default_flow_style=False)


def read_yaml(file_path: str | Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(file_path).read_text()) or {}
    if not isinstance(value, dict):
        msg = f"YAML document must be an object: {file_path}"
        raise RuntimeError(msg)
    return value


GENERATED_CONFIG_DIR = Path("config/generated")
GENERATED_CONFIG_HEADER = (
    "# AUTO-GENERATED BY npm run sync FROM config/job.yaml.j2 AND\n"
    "# config/variants.yaml. DO NOT EDIT MANUALLY.\n"
)


def compiled_config_path(variant_name: str) -> Path:
    return GENERATED_CONFIG_DIR / f"job.{variant_name}.yaml"


def compile_job_configs() -> None:
    GENERATED_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    expected: set[str] = set()
    for variant_name, variant in VARIANTS.items():
        if not variant.get("job"):
            continue
        path = compiled_config_path(variant_name)
        expected.add(path.name)
        config = render_job_config(
            variant["job"], benchmark=benchmark_key(variant.get("benchmark"))
        )
        path.write_text(f"{GENERATED_CONFIG_HEADER}{dump_yaml(config)}")
    for entry in GENERATED_CONFIG_DIR.glob("job.*.yaml"):
        if entry.name not in expected:
            entry.unlink()


def load_compiled_config(variant_name: str) -> dict[str, Any]:
    path = compiled_config_path(variant_name)
    if not path.exists():
        msg = f"Missing compiled job config: {path}. Run `npm run sync` first."
        raise RuntimeError(msg)
    return read_yaml(path)


def versioned_name(benchmark: BenchmarkKey, suffix: str) -> str:
    return f"{BENCHMARKS[benchmark]['id']}-{suffix}"


def render_job_config(
    job: dict[str, Any], benchmark: BenchmarkKey | None = BenchmarkKey.TEMPO
) -> dict[str, Any]:
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader("config"),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    rendered = environment.get_template("job.yaml.j2").render(
        job_name=(
            versioned_name(benchmark, job["job_name"])
            if benchmark is not None
            else job["job_name"]
        ),
        jobs_dir=job.get("jobs_dir", "jobs"),
        n_attempts=job["n_attempts"],
        n_concurrent_trials=job["n_concurrent_trials"],
        environment_type=job["environment_type"],
        force_build=job["force_build"],
        agents=job["agents"],
        dind_image=RUN_CONFIG["daytona"]["dind_image"],
    )
    config = yaml.safe_load(rendered)
    datasets = (
        job["datasets"]
        if "datasets" in job
        else read_yaml("config/datasets.yaml").get("datasets", [])
    )
    config["datasets"] = copy.deepcopy(datasets)
    return config


def production_agent(model: dict[str, Any]) -> dict[str, Any]:
    agent: dict[str, Any] = {
        "name": model["agent"],
        "model_name": model["model_name"],
    }
    if model.get("n_concurrent"):
        agent["n_concurrent"] = int(model["n_concurrent"])
    if model.get("concurrency_group"):
        agent["concurrency_group"] = model["concurrency_group"]
    return agent


def production_job(
    run_id: str,
    model_config: dict[str, Any],
    options: dict[str, Any],
) -> dict[str, Any]:
    job_dir = production_job_dir(run_id)
    return {
        "job_name": job_dir.name,
        "jobs_dir": str(job_dir.parent),
        "n_attempts": int(options.get("n_attempts") or "3"),
        "n_concurrent_trials": int(options.get("concurrency") or "16"),
        "environment_type": "daytona",
        "force_build": False,
        "agents": [production_agent(model) for model in model_config["models"]],
        "datasets": datasets_for_suite(options.get("task_suite") or "tempo"),
    }


def run_production_variant(
    run_id: str,
    options: dict[str, Any],
    docs_bundle: str | None,
) -> None:
    models_config_path = options.get("models_config") or "config/models.production.yaml"
    model_config = parse_model_config(
        models_config_path, options.get("agent_concurrency")
    )
    preflight_production_agents(model_config)
    job = production_job(run_id, model_config, options)
    config = stage_daytona_config(
        render_job_config(job, benchmark=None), run_id, docs_bundle, options
    )
    max_retries = options.get("max_retries") or "2"
    args = ["run", "harbor", "run", "-c", config]
    if options.get("env_file"):
        args.extend(["--env-file", options["env_file"]])
    args.extend(["--max-retries", max_retries])
    os.environ["TEMPO_DOCS_BUNDLE_PATH"] = ""
    args.append("-y")
    status = run_status("uv", args)
    if status != 0:
        raise RuntimeError(f"Production benchmark {run_id} failed with status {status}")


def prepare_production_profiles(
    variant: dict[str, Any], options: dict[str, Any]
) -> None:
    """Validate and stage shared inputs before profile jobs run in parallel."""
    load_env_file(options.get("env_file"))
    preflight(variant, options)
    models_config_path = options.get("models_config") or "config/models.production.yaml"
    model_config = parse_model_config(
        models_config_path, options.get("agent_concurrency")
    )
    preflight_production_agents(model_config)
    if options.get("sync"):
        sync_dataset(options)
    source = {"mode": "live"} if uses_live_mcp_eval(options) else docs_source(options)
    if source["mode"] != "live":
        ensure_docs_bundle(source)


def mpp_task_filter(task_filter: str) -> str | None:
    prefixes = ("tempo/mpp-", "tempo-mpp/", "mpp/", "mpp-")
    for prefix in prefixes:
        if task_filter.startswith(prefix):
            return task_filter.removeprefix(prefix)
    return task_filter if task_filter.startswith(("server-", "client-")) else None


def datasets_for_suite(task_suite: str) -> list[dict[str, Any]]:
    if task_suite == "tempo":
        return copy.deepcopy(RUN_CONFIG["tempo_only_datasets"])
    if task_suite == "mpp":
        return copy.deepcopy(RUN_CONFIG["mpp_only_datasets"])
    if task_suite == "tempo-mcp":
        return copy.deepcopy(RUN_CONFIG["mcp_only_datasets"])
    return copy.deepcopy(read_yaml("config/datasets.yaml").get("datasets", []))


def apply_task_suite(
    config: dict[str, Any],
    task_suite: str | None,
) -> dict[str, Any]:
    config["datasets"] = datasets_for_suite(task_suite or "tempo")
    return config


def apply_task_filter(
    config: dict[str, Any],
    task_filter: str | None,
) -> dict[str, Any]:
    if not task_filter:
        return config

    if mpp_filter := mpp_task_filter(task_filter):
        config["datasets"] = [{"path": "tasks/mpp", "task_names": [mpp_filter]}]
        return config

    tempo_prefixes = ("tempo-v1/", "tempo-mcp-v1/", "tempo/")
    filters = [task_filter]
    for prefix in tempo_prefixes:
        if task_filter.startswith(prefix):
            filters.append(task_filter.removeprefix(prefix))
            break
    for dataset in config.get("datasets", []):
        if dataset.get("path") in {"tasks", "tasks/tempo-v1", "tasks/tempo-mcp-v1"}:
            dataset["task_names"] = filters
            config["datasets"] = [dataset]
            return config

    msg = "Could not apply task filter to config"
    raise RuntimeError(msg)


def apply_model_override(
    config: dict[str, Any],
    model: str | None,
) -> dict[str, Any]:
    if not model:
        return config
    updated = False
    for agent in config.get("agents", []):
        if "model_name" in agent:
            agent["model_name"] = model
            updated = True
    if updated:
        return config

    msg = "Could not apply model override to config"
    raise RuntimeError(msg)


def apply_profile(config: dict[str, Any], profile_id: str) -> dict[str, Any]:
    if profile_id == DOCS_PROFILE["id"]:
        return config

    profile = tempo_profile(profile_id)
    for agent in config.get("agents", []):
        if agent.get("name") != "oracle":
            agent["mcp_servers"] = copy.deepcopy(profile["mcp_servers"])
    return config


def apply_pair_id(config: dict[str, Any], pair_id: str | None) -> dict[str, Any]:
    if not pair_id:
        return config
    for agent in config.get("agents", []):
        if agent.get("name") != "oracle":
            agent.setdefault("env", {})["TEMPO_BENCH_PAIR_ID"] = pair_id
    return config


def redirect_dataset_paths(config: dict[str, Any], staging_root: Path) -> None:
    path_map = {
        "tasks/mpp": str(staging_root / "tasks" / "mpp"),
        "tasks/tempo-v1": str(staging_root / "tasks" / "tempo-v1"),
        "tasks/tempo-mcp-v1": str(staging_root / "tasks" / "tempo-mcp-v1"),
        "tasks": str(staging_root / "tasks" / "tempo-v1"),
    }
    changed = False
    for dataset in config.get("datasets", []):
        if dataset.get("path") in path_map:
            dataset["path"] = path_map[dataset["path"]]
            changed = True
    if not changed:
        msg = "Could not redirect dataset path in config"
        raise RuntimeError(msg)


def copy_tasks(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        symlinks=False,
        ignore=lambda _directory, names: [
            name for name in names if name in {"node_modules", "package-lock.json"}
        ],
    )


def run_openssl(args: list[str]) -> None:
    result = subprocess.run(
        ["openssl", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"openssl {' '.join(args)} failed: {output}")


def generate_docs_tls_assets(environment_dir: Path) -> Path:
    """Create an ephemeral CA and docs.tempo.xyz leaf certificate for one run."""
    tls_dir = environment_dir / DOCS_TLS_DIR
    shutil.rmtree(tls_dir, ignore_errors=True)
    tls_dir.mkdir(parents=True)

    ca_key = tls_dir / "ca.key"
    ca_cert = tls_dir / DOCS_CA_FILE
    leaf_key = tls_dir / "docs.key"
    leaf_csr = tls_dir / "docs.csr"
    leaf_cert = tls_dir / "docs.crt"
    extensions = tls_dir / "docs.ext"

    run_openssl(
        [
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(ca_key),
            "-out",
            str(ca_cert),
            "-days",
            DOCS_TLS_VALIDITY_DAYS,
            "-subj",
            "/CN=Tempo Bench Ephemeral Docs CA",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
        ]
    )
    run_openssl(
        [
            "req",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(leaf_key),
            "-out",
            str(leaf_csr),
            "-subj",
            "/CN=docs.tempo.xyz",
        ]
    )
    extensions.write_text(
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\n"
        "subjectAltName=DNS:docs.tempo.xyz\n"
    )
    run_openssl(
        [
            "x509",
            "-req",
            "-in",
            str(leaf_csr),
            "-CA",
            str(ca_cert),
            "-CAkey",
            str(ca_key),
            "-CAserial",
            str(tls_dir / "ca.srl"),
            "-CAcreateserial",
            "-out",
            str(leaf_cert),
            "-days",
            DOCS_TLS_VALIDITY_DAYS,
            "-extfile",
            str(extensions),
        ]
    )
    ca_key.unlink()
    leaf_csr.unlink()
    extensions.unlink()
    (tls_dir / "ca.srl").unlink(missing_ok=True)
    return tls_dir


def trust_docs_ca(environment_dir: Path, tls_dir: Path) -> None:
    dockerfile = environment_dir / "Dockerfile"
    ca_path = tls_dir.relative_to(environment_dir) / DOCS_CA_FILE
    content = dockerfile.read_text().rstrip()
    dockerfile.write_text(
        f"{content}\n\n"
        f"COPY {ca_path.as_posix()} {DOCS_CA_DESTINATION}\n"
        "RUN update-ca-certificates\n"
        f"ENV NODE_EXTRA_CA_CERTS={DOCS_CA_DESTINATION}\n"
    )
    (environment_dir / ".dockerignore").write_text("docs-tls/*\n!docs-tls/ca.crt\n")


def stage_pinned_docs_task(task_dir: Path, docs_bundle: str) -> None:
    task_config_path = task_dir / "task.toml"
    config = tomlkit.parse(task_config_path.read_text())
    artifacts = config.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError(f"Missing artifacts array in staged task: {task_dir}")
    access_log = tomlkit.inline_table()
    access_log["source"] = DOCS_ACCESS_LOG
    access_log["service"] = "tempo-docs"
    artifacts.append(access_log)
    task_config_path.write_text(tomlkit.dumps(config))

    environment_dir = task_dir / "environment"
    shutil.copyfile(
        "shared/tempo/docker/compose/tempo-docs.yaml",
        environment_dir / "docker-compose.yaml",
    )
    shutil.copytree(
        "shared/tempo/docs/tempo-docs",
        environment_dir / "tempo-docs",
        dirs_exist_ok=True,
    )
    shutil.copytree(
        docs_bundle, environment_dir / "tempo-docs-bundle", dirs_exist_ok=True
    )
    trust_docs_ca(environment_dir, generate_docs_tls_assets(environment_dir))


def override_staged_base_image(staging_root: Path, image: str) -> None:
    expected = f"FROM {base_image_ref()}"
    for dockerfile in staging_root.glob("tasks/*/*/environment/Dockerfile"):
        content = dockerfile.read_text()
        if expected not in content:
            raise RuntimeError(f"Unexpected base image in staged task: {dockerfile}")
        dockerfile.write_text(content.replace(expected, f"FROM {image}", count=1))


def stage_task_datasets(
    staging_root: Path,
    docs_bundle: str | None,
    base_image: str | None = None,
) -> None:
    staged_tasks = staging_root / "tasks" / "tempo-v1"
    staged_tasks.parent.mkdir(parents=True, exist_ok=True)
    copy_tasks(Path("tasks/tempo-v1"), staged_tasks)
    if Path("tasks/tempo-mcp-v1").exists():
        mcp_tasks = staging_root / "tasks" / "tempo-mcp-v1"
        copy_tasks(Path("tasks/tempo-mcp-v1"), mcp_tasks)
        for task_dir in mcp_tasks.iterdir():
            if not task_dir.is_dir() or not (task_dir / "task.toml").exists():
                continue
            environment_dir = task_dir / "environment"
            shutil.copyfile(
                "shared/tempo/docker/compose/tempo-mcp-eval.yaml",
                environment_dir / "docker-compose.yaml",
            )
            upstream_url = os.environ.get("TEMPO_MCP_EVAL_URL")
            if upstream_url:
                compose_path = environment_dir / "docker-compose.yaml"
                compose_path.write_text(
                    compose_path.read_text().replace(
                        MCP_UPSTREAM_PLACEHOLDER,
                        upstream_url,
                    )
                )
            shutil.copytree(
                "shared/tempo/mcp-bridge",
                environment_dir / "mcp-bridge",
                dirs_exist_ok=True,
            )
            shutil.copyfile(
                "shared/tempo/mcp-eval/check.py", task_dir / "tests" / "check.py"
            )
            shutil.copyfile(
                "shared/tempo/mcp-eval/validation.py",
                task_dir / "tests" / "validation.py",
            )
            shutil.copyfile(
                "shared/tempo/mcp-eval/test.sh", task_dir / "tests" / "test.sh"
            )
            (task_dir / "tests" / "test.sh").chmod(0o755)
            shutil.copyfile(
                task_dir / "instruction.md", task_dir / "tests" / "instruction.md"
            )
            shutil.copytree(
                "shared/tempo/mcp-eval/quality",
                task_dir / "tests" / "quality",
                dirs_exist_ok=True,
            )
    if Path("tasks/mpp").exists():
        copy_tasks(Path("tasks/mpp"), staging_root / "tasks" / "mpp")
    if base_image is not None:
        override_staged_base_image(staging_root, base_image)
    if docs_bundle is not None:
        for task_dir in staged_tasks.iterdir():
            if task_dir.is_dir() and (task_dir / "task.toml").exists():
                stage_pinned_docs_task(task_dir, docs_bundle)


def finalize_config(config: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    return apply_model_override(
        apply_task_filter(
            apply_task_suite(config, options.get("task_suite")),
            options.get("task_filter"),
        ),
        options.get("model"),
    )


def stage_daytona_config(
    config: dict[str, Any],
    run_id: str,
    docs_bundle: str | None,
    options: dict[str, Any],
) -> str:
    staging_root = Path(".cache") / "harbor-daytona" / run_id
    staged_config = staging_root / "job.yaml"

    shutil.rmtree(staging_root, ignore_errors=True)
    stage_task_datasets(staging_root, docs_bundle, daytona_base_image(options))

    config = apply_pair_id(
        apply_profile(finalize_config(config, options), options["profile"]),
        options.get("pair_id"),
    )
    redirect_dataset_paths(config, staging_root)
    staged_config.write_text(dump_yaml(config))
    return str(staged_config)


def stage_filtered_config(
    config: dict[str, Any],
    run_id: str,
    options: dict[str, Any],
    docs_bundle: str | None,
) -> str:
    staging_root = Path(".cache") / "harbor-config" / run_id
    staged_config = staging_root / "job.yaml"
    shutil.rmtree(staging_root, ignore_errors=True)
    staging_root.mkdir(parents=True, exist_ok=True)
    config = apply_pair_id(
        apply_profile(finalize_config(config, options), options["profile"]),
        options.get("pair_id"),
    )
    if (
        docs_bundle is not None
        or options["profile"] in {MCP_DIRECT_PROFILE["id"], MCP_CODE_PROFILE["id"]}
        or options.get("task_suite") in {"tempo-mcp", "all"}
    ):
        stage_task_datasets(staging_root, docs_bundle)
        redirect_dataset_paths(config, staging_root)
    staged_config.write_text(dump_yaml(config))
    return str(staged_config)


def main(argv: list[str]) -> None:
    variant_name, options = parse_args(argv)
    if options.get("help") or not variant_name:
        usage()
        raise SystemExit(0 if options.get("help") else 1)
    if variant_name == "sync":
        sync_generated()
        return
    if variant_name == "dataset":
        sync_dataset(options)
        return
    if variant_name == "build-base":
        build_base_image()
        return
    if variant_name == "check-dataset":
        sync_dataset(options)
        run("git", ["diff", "--exit-code", f"{task_path(options)}/dataset.toml"])
        return
    if variant_name == "check-generated":
        sync_dataset(options)
        run("git", ["diff", "--exit-code"])
        return
    if variant_name == "clean-jobs":
        shutil.rmtree("jobs", ignore_errors=True)
        Path("jobs").mkdir(parents=True, exist_ok=True)
        return
    if variant_name == "clean":
        shutil.rmtree("jobs", ignore_errors=True)
        shutil.rmtree(Path(".cache") / "harbor-daytona", ignore_errors=True)
        shutil.rmtree(Path(".cache") / "harbor-config", ignore_errors=True)
        shutil.rmtree(Path(".cache") / "harbor-production", ignore_errors=True)
        Path("jobs").mkdir(parents=True, exist_ok=True)
        return

    if options["profile"] in {"all", "mcp-both"}:
        variant = VARIANTS.get(variant_name)
        if not variant:
            usage()
            raise RuntimeError(f"Unknown variant: {variant_name}")
        if not variant.get("job") and not variant.get("production"):
            raise RuntimeError(
                "The all profile requires a job-backed or production benchmark variant."
            )
        if variant.get("production"):
            prepare_production_profiles(variant, options)
        first_profile_sync = False if variant.get("production") else options["sync"]
        benchmark = run_benchmark_key(variant, options.get("task_suite"))
        prefix = versioned_name(benchmark, variant["prefix"])
        pair_id = options.get("job_name") or (
            f"{prefix}-{production_timestamp()}"
            if variant.get("production")
            else f"{prefix}-mcp-pair-{timestamp()}"
        )
        profile_options = [
            options
            | {
                "profile": profile_id,
                "job_name": (
                    pair_id if variant.get("production") else f"{pair_id}-{profile_id}"
                ),
                "pair_id": pair_id,
                "sync": first_profile_sync if index == 0 else False,
            }
            for index, profile_id in enumerate(
                (MCP_DIRECT_PROFILE["id"], MCP_CODE_PROFILE["id"])
                if options["profile"] == "mcp-both"
                else DEFAULT_PROFILE_IDS
            )
        ]
        with ThreadPoolExecutor(max_workers=len(profile_options)) as executor:
            futures = [
                executor.submit(run_benchmark_variant, variant_name, profile)
                for profile in profile_options
            ]
            for future in futures:
                future.result()
        return

    run_benchmark_variant(variant_name, options)


def run_benchmark_variant(variant_name: str, options: dict[str, Any]) -> None:

    variant = VARIANTS.get(variant_name)
    if not variant:
        usage()
        msg = f"Unknown variant: {variant_name}"
        raise RuntimeError(msg)

    if (
        options["profile"]
        in {
            MCP_PROFILE["id"],
            MCP_DIRECT_PROFILE["id"],
            MCP_CODE_PROFILE["id"],
        }
        and not variant.get("job")
        and not variant.get("production")
    ):
        raise RuntimeError(
            "The MCP profile requires a job-backed or production benchmark variant."
        )

    source = {"mode": "live"} if uses_live_mcp_eval(options) else docs_source(options)
    load_env_file(options.get("env_file"))
    preflight(variant, options)
    preflight_mcp_target(options)
    if options.get("sync"):
        sync_dataset(options)
    if not variant.get("needs_daytona_auth"):
        build_base_image()
    docs_bundle = None if source["mode"] == "live" else ensure_docs_bundle(source)

    benchmark = run_benchmark_key(variant, options.get("task_suite"))
    default_run_name = versioned_name(benchmark, variant["prefix"])
    run_group = options.get("job_name")
    if variant.get("production"):
        run_group = run_group or f"{default_run_name}-{production_timestamp()}"
        run_id = f"{run_group}-{options['profile']}"
    else:
        run_id = run_group or f"{default_run_name}-{options['profile']}-{timestamp()}"
    args = ["run", "harbor", "run"]
    if variant.get("production"):
        run_production_variant(run_id, options, docs_bundle)
        return

    if variant.get("job"):
        job_config = load_compiled_config(variant_name)
        config = (
            stage_daytona_config(job_config, run_id, docs_bundle, options)
            if variant.get("needs_daytona_auth")
            else stage_filtered_config(job_config, run_id, options, docs_bundle)
        )
        args.extend(["-c", config])
    else:
        args.extend(
            [
                "--path",
                options.get("tasks") or variant.get("path") or "tasks/tempo-v1",
            ]
        )
        args.extend(
            [
                "--agent",
                options.get("agent") or variant.get("default_agent") or "claude-code",
            ]
        )
        model = options.get("model") or variant.get("default_model")
        if model:
            args.extend(["--model", model])
        if options.get("task_filter"):
            args.extend(["--include-task-name", options["task_filter"]])
        if options.get("n_tasks"):
            args.extend(["--n-tasks", options["n_tasks"]])
    if options.get("env_file"):
        args.extend(["--env-file", options["env_file"]])
    args.extend(["--job-name", run_id])
    if options.get("concurrency"):
        args.extend(["--n-concurrent", options["concurrency"]])
    if options.get("agent_concurrency"):
        args.extend(["--n-concurrent-agents", options["agent_concurrency"]])
    if options.get("no_force_build"):
        args.append("--no-force-build")
    if options.get("no_delete"):
        args.append("--no-delete")
    if options.get("disable_verification"):
        args.append("--disable-verification")
    if options.get("install_only"):
        args.append("--install-only")
    if options.get("debug"):
        args.append("--debug")
    max_retries = options.get("max_retries") or (
        "2" if variant.get("needs_daytona_auth") else None
    )
    if max_retries:
        args.extend(["--max-retries", max_retries])
    os.environ["TEMPO_DOCS_BUNDLE_PATH"] = (
        "" if variant.get("needs_daytona_auth") or docs_bundle is None else docs_bundle
    )
    args.append("-y")
    run("uv", args)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except RuntimeError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error
