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
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import jinja2
import tomlkit
import yaml


class BenchmarkKey(StrEnum):
    TEMPO = "tempo"
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
PROFILE_IDS = tuple(profile["id"] for profile in TEMPO_PROFILES)


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
  sync               Sync generated task assets and compiled job configs
  dataset            Sync generated task assets and Harbor dataset digests
  build-base         Build the shared task base image locally
  check-dataset      Verify dataset digests are fresh
  check-generated    Verify sync leaves no generated diff
  clean-jobs         Remove local Harbor job outputs
  clean              Remove local Harbor job outputs and Daytona staging cache

Options:
  --env-file PATH          Load env file for Harbor and preflight checks
                           (default: .env when present)
  --job-name NAME          Override generated job name
  --models-config PATH     Production model matrix config
                           (default: config/models.production.yaml)
  --concurrency N         Override n_concurrent_trials
  --agent-concurrency N   Override per-agent n_concurrent
  --max-retries N         Retry transient trial/setup failures
                          (default: 2 for Daytona runs)
  --agent NAME            Agent for the model variant (default: claude-code)
  --model NAME            Model for the model variant (default: haiku)
  --task-filter GLOB      Include matching task names for model and config variants
  --task-suite SUITE      Task family for config variants: tempo, mpp, or all
                          (default: tempo; use all explicitly for full matrix)
  --n-tasks N             Limit task count for the model variant
  --tasks PATH            Task dataset path for dataset/model variants
                          (default: tasks/tempo-v1)
  --docs-sha SHA          Serve docs pinned to this SHA instead of public docs
  --profile PROFILE       Tempo access profile: docs, mcp, or all (default: docs)
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
    parser.add_argument("--task-suite", choices=["tempo", "mpp", "all"])
    parser.add_argument(
        "--n-tasks", type=lambda value: read_positive_integer(value, "--n-tasks")
    )
    parser.add_argument("--tasks")
    parser.add_argument("--docs-sha")
    parser.add_argument(
        "--profile", choices=(*PROFILE_IDS, "all"), default=DOCS_PROFILE["id"]
    )
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


def run(command: str, args: list[str]) -> None:
    result = subprocess.run([command, *args], env=os.environ, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def run_status(command: str, args: list[str]) -> int:
    return subprocess.run([command, *args], env=os.environ, check=False).returncode


def run_output(command: str, args: list[str]) -> str | None:
    result = subprocess.run(
        [command, *args],
        env=os.environ,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def run_python(script: str, args: list[str] | None = None) -> None:
    run(sys.executable, [script, *(args or [])])


DOCS_SHA_PATTERN = re.compile(r"[0-9a-fA-F]{7,40}")
DOCS_ACCESS_LOG = "/var/log/tempo-docs/access.log"
DOCS_TLS_DIR = "docs-tls"
DOCS_CA_FILE = "ca.crt"
DOCS_CA_DESTINATION = "/usr/local/share/ca-certificates/tempo-bench-docs.crt"
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


def sync_dataset(options: dict[str, Any]) -> None:
    sync_generated()
    run("uv", ["run", "harbor", "sync", task_path(options)])


def parse_model_config(file_path: str, agent_concurrency: str | None) -> dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        msg = f"Production model config not found: {file_path}"
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
        msg = f"No production models configured in {file_path}"
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


def production_run_root(run_id: str) -> Path:
    return Path("runs") / run_id


def production_job_dir(run_id: str) -> Path:
    return production_run_root(run_id) / "harbor-job"


def write_production_metadata(run_id: str, metadata: dict[str, Any]) -> None:
    run_root = production_run_root(run_id)
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "metadata.json").write_text(f"{json.dumps(metadata, indent=2)}\n")


def benchmark_key(value: str | BenchmarkKey | None) -> BenchmarkKey:
    return BenchmarkKey(value or BenchmarkKey.TEMPO)


def benchmark_provenance(task_suite: str | None) -> list[dict[str, str]]:
    keys = (
        (BenchmarkKey.TEMPO, BenchmarkKey.MPP)
        if task_suite == "all"
        else (benchmark_key(task_suite),)
    )
    return [
        {"id": BENCHMARKS[key]["id"], "dataset": BENCHMARKS[key]["dataset"]}
        for key in keys
    ]


def run_benchmark_key(variant: dict[str, Any], task_suite: str | None) -> BenchmarkKey:
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
    job: dict[str, Any], benchmark: BenchmarkKey = BenchmarkKey.TEMPO
) -> dict[str, Any]:
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader("config"),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    rendered = environment.get_template("job.yaml.j2").render(
        job_name=versioned_name(benchmark, job["job_name"]),
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
    return {
        "job_name": "harbor-job",
        "jobs_dir": str(production_run_root(run_id)),
        "n_attempts": 3,
        "n_concurrent_trials": int(options.get("concurrency") or "32"),
        "environment_type": "daytona",
        "force_build": False,
        "agents": [production_agent(model) for model in model_config["models"]],
        "datasets": RUN_CONFIG["tempo_only_datasets"],
    }


def run_production_variant(
    run_id: str,
    options: dict[str, Any],
    source: dict[str, str],
    docs_bundle: str | None,
) -> None:
    models_config_path = options.get("models_config") or "config/models.production.yaml"
    model_config = parse_model_config(
        models_config_path, options.get("agent_concurrency")
    )
    preflight_production_agents(model_config)
    job = production_job(run_id, model_config, options)
    config = stage_daytona_config(render_job_config(job), run_id, docs_bundle, options)
    max_retries = options.get("max_retries") or "2"
    started_at = datetime.now().astimezone().isoformat()
    metadata = {
        "schema_version": 1,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": None,
        "status": "running",
        "harbor_job_dir": str(production_job_dir(run_id)),
        "models_config": models_config_path,
        "models": [
            {
                "agent": model["agent"],
                "model_name": model["model_name"],
                "n_concurrent": model.get("n_concurrent"),
                "concurrency_group": model.get("concurrency_group"),
            }
            for model in model_config["models"]
        ],
        "benchmarks": benchmark_provenance(options.get("task_suite")),
        "task_suite": options.get("task_suite") or "tempo",
        "task_filter": options.get("task_filter"),
        "n_attempts": job["n_attempts"],
        "n_concurrent_trials": str(job["n_concurrent_trials"]),
        "max_retries": max_retries,
        "docs_source": source.get("sha", "public"),
        "docs_bundle": docs_bundle,
        "profile": options["profile"],
        "git_sha": run_output("git", ["rev-parse", "HEAD"]),
        "git_branch": run_output("git", ["branch", "--show-current"]),
        "harbor_version": run_output("uv", ["run", "harbor", "--version"]),
    }

    write_production_metadata(run_id, metadata)
    args = ["run", "harbor", "run", "-c", config]
    if options.get("env_file"):
        args.extend(["--env-file", options["env_file"]])
    args.extend(["--max-retries", max_retries])
    os.environ["TEMPO_DOCS_BUNDLE_PATH"] = ""
    args.append("-y")

    status = run_status("uv", args)
    write_production_metadata(
        run_id,
        {
            **metadata,
            "finished_at": datetime.now().astimezone().isoformat(),
            "status": "completed" if status == 0 else "failed",
            "exit_status": status,
        },
    )
    raise SystemExit(status)


def mpp_task_filter(task_filter: str) -> str | None:
    prefixes = ("tempo/mpp-", "tempo-mpp/", "mpp/", "mpp-")
    for prefix in prefixes:
        if task_filter.startswith(prefix):
            return task_filter.removeprefix(prefix)
    return task_filter if task_filter.startswith("server-") else None


def datasets_for_suite(task_suite: str) -> list[dict[str, Any]]:
    if task_suite == "tempo":
        return copy.deepcopy(RUN_CONFIG["tempo_only_datasets"])
    if task_suite == "mpp":
        return copy.deepcopy(RUN_CONFIG["mpp_only_datasets"])
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

    tempo_prefixes = ("tempo-v1/", "tempo/")
    filters = [task_filter]
    for prefix in tempo_prefixes:
        if task_filter.startswith(prefix):
            filters.append(task_filter.removeprefix(prefix))
            break
    for dataset in config.get("datasets", []):
        if dataset.get("path") in {"tasks", "tasks/tempo-v1"}:
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

    for agent in config.get("agents", []):
        if agent.get("name") != "oracle":
            agent["mcp_servers"] = copy.deepcopy(MCP_PROFILE["mcp_servers"])
    return config


def redirect_dataset_paths(config: dict[str, Any], staging_root: Path) -> None:
    path_map = {
        "tasks/mpp": str(staging_root / "tasks" / "mpp"),
        "tasks/tempo-v1": str(staging_root / "tasks" / "tempo-v1"),
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
            "/CN=tempo.xyz",
        ]
    )
    extensions.write_text(
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\n"
        "subjectAltName=DNS:docs.tempo.xyz,DNS:tempo.xyz\n"
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
        "shared/tempo/docker/compose/tempo-localnet-docs.yaml",
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


def stage_task_datasets(staging_root: Path, docs_bundle: str | None) -> None:
    staged_tasks = staging_root / "tasks" / "tempo-v1"
    staged_tasks.parent.mkdir(parents=True, exist_ok=True)
    copy_tasks(Path("tasks/tempo-v1"), staged_tasks)
    if Path("tasks/mpp").exists():
        copy_tasks(Path("tasks/mpp"), staging_root / "tasks" / "mpp")
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
    stage_task_datasets(staging_root, docs_bundle)

    config = apply_profile(finalize_config(config, options), options["profile"])
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
    config = apply_profile(finalize_config(config, options), options["profile"])
    if docs_bundle is not None:
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

    if options["profile"] == "all":
        variant = VARIANTS.get(variant_name)
        if not variant:
            usage()
            raise RuntimeError(f"Unknown variant: {variant_name}")
        if not variant.get("job"):
            raise RuntimeError(
                "The all profile requires a job-backed benchmark variant."
            )
        profile_options = [
            options
            | {
                "profile": profile_id,
                "job_name": (
                    f"{options['job_name']}-{profile_id}"
                    if options.get("job_name")
                    else None
                ),
                "sync": options["sync"] if index == 0 else False,
            }
            for index, profile_id in enumerate(PROFILE_IDS)
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

    if options["profile"] == MCP_PROFILE["id"] and not variant.get("job"):
        raise RuntimeError("The MCP profile requires a job-backed benchmark variant.")

    source = docs_source(options)
    load_env_file(options.get("env_file"))
    preflight(variant, options)
    if options.get("sync"):
        sync_dataset(options)
    if not variant.get("needs_daytona_auth"):
        build_base_image()
    docs_bundle = ensure_docs_bundle(source)

    benchmark = run_benchmark_key(variant, options.get("task_suite"))
    default_run_name = versioned_name(benchmark, variant["prefix"])
    run_id = options.get("job_name") or (
        f"{default_run_name}-{options['profile']}-{timestamp()}"
    )
    args = ["run", "harbor", "run"]
    if variant.get("production"):
        run_production_variant(run_id, options, source, docs_bundle)

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
