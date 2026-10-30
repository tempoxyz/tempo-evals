#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import fnmatch
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
from threading import Lock
from typing import Any

import jinja2
import tomlkit
import yaml
from dotenv.parser import parse_stream


class BenchmarkKey(StrEnum):
    TEMPO = "tempo"
    TEMPO_MCP = "tempo-mcp"
    MPP = "mpp"
    CHECKOUT = "checkout"


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
CHECKOUT_PROFILES = {
    profile["id"]: profile for profile in TASKS_CONFIG["checkout"]["profiles"]
}


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
MCP_ORACLE_DOCS_TOOLS = {
    MCP_DIRECT_PROFILE["id"]: "docs_search",
    MCP_CODE_PROFILE["id"]: "docs_code",
}
SUITE_PROFILES = {
    "tempo": (DOCS_PROFILE["id"], MCP_PROFILE["id"], "all"),
    "tempo-mcp": (MCP_DIRECT_PROFILE["id"], MCP_CODE_PROFILE["id"], "mcp-both"),
    "mpp": (DOCS_PROFILE["id"],),
    "checkout": (DOCS_PROFILE["id"], *CHECKOUT_PROFILES, "all"),
    "all": (DOCS_PROFILE["id"],),
}
_IMAGE_BUILD_LOCK = Lock()
_images_built = False


def usage() -> None:
    print("""Usage: npm run <script> -- [options]

Direct: uv run python scripts/run_benchmark.py <variant> [options]

Variants:
  local-oracle       Oracle validation on local Docker
  local-oracle-dev   Fast oracle iteration on local Docker
  local-agent        Claude Code matrix on local Docker
  local-agent-dev    One-attempt Claude Code smoke run on local Docker
  local-codex-agent  Codex matrix on local Docker
  local-codex-agent-dev
                     One-attempt Codex smoke run on local Docker
  model              One local harness/model run over tasks
  daytona-oracle     Oracle validation on Daytona
  daytona-agent      Claude Code matrix on Daytona
  daytona-agent-dev  One-attempt Claude Code smoke run on Daytona
  production-daytona Production Daytona run over configured models
  sync               Sync shared MPP assets and compiled job configs
  dataset            Sync shared assets and Harbor dataset digests
  build-images       Build the agent and verifier images locally
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
                          (default: model config value, otherwise 16)
  --agent-concurrency N   Override per-profile agent concurrency pools
  --max-retries N         Retry transient trial/setup failures
                          (0 disables; default: 4 for production, 2 otherwise)
  --agent NAME            Agent for the model variant (default: claude-code)
  --model NAME            Model for the model variant (default: haiku)
  --task-filter GLOB      Include matching task names for model and config variants
  --task-suite SUITE      Task family: tempo, tempo-mcp, mpp, checkout, or all
                          (default: tempo; use all explicitly for full matrix)
  --n-tasks N             Limit task count for the model variant
  --tasks PATH            Task dataset path for dataset/model variants
                          (default: tasks/tempo-v1)
  --docs-sha SHA          Override the pinned documentation revision for a run
  --profile PROFILE       Access profile: docs, mcp, mcp-direct, mcp-code,
                          mcp-both, local, browserbase, kernel, or all
                          (default: docs; checkout: local)
  --agent-image REF       Immutable Daytona agent image tag or digest (required)
  --verifier-image REF    Immutable Daytona verifier image tag or digest (required)
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


def read_nonnegative_integer(value: str, option: str) -> str:
    if not value.isdecimal():
        msg = f"{option} must be a nonnegative integer"
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
        type=lambda value: read_nonnegative_integer(value, "--max-retries"),
    )
    parser.add_argument("--agent")
    parser.add_argument("--model")
    parser.add_argument("--task-filter")
    parser.add_argument(
        "--task-suite", choices=["tempo", "tempo-mcp", "mpp", "checkout", "all"]
    )
    parser.add_argument(
        "--n-tasks", type=lambda value: read_positive_integer(value, "--n-tasks")
    )
    parser.add_argument("--tasks")
    parser.add_argument("--docs-sha")
    parser.add_argument(
        "--mpp-docs-source",
        help="Local MPP docs checkout to stage at https://mpp.dev for MPP tasks",
    )
    parser.add_argument(
        "--profile",
        choices=(*PROFILE_IDS, *CHECKOUT_PROFILES, "mcp-both", "all"),
        default=DOCS_PROFILE["id"],
    )
    parser.add_argument("--agent-image")
    parser.add_argument("--verifier-image")
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
    with path.open() as stream:
        bindings = list(parse_stream(stream))
    for binding in bindings:
        if binding.error:
            raise RuntimeError(
                f"Invalid env syntax in {path} at line {binding.original.line}"
            )
    for binding in bindings:
        if (
            binding.key is not None
            and binding.key.isidentifier()
            and binding.value is not None
        ):
            os.environ.setdefault(binding.key, binding.value)


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
FULL_GIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
PINNED_JUDGE_MODEL = "anthropic/claude-haiku-4-5-20251001"
DEFAULT_JUDGE_MODEL = f"${{REWARDKIT_JUDGE:-{PINNED_JUDGE_MODEL}}}"
# Codex hosted web search resolves pages outside the task sandbox, so Codex
# must read documentation through the sandbox like every other agent.
CODEX_WEB_SEARCH = "disabled"
DOCS_ACCESS_LOG = "/var/log/tempo-docs/access.log"
DOCS_TLS_DIR = "docs-tls"
DOCS_CA_FILE = "ca.crt"
DOCS_CA_DESTINATION = "/usr/local/share/ca-certificates/stable-bench-docs.crt"
MCP_UPSTREAM_PLACEHOLDER = "${TEMPO_MCP_EVAL_URL:-https://api.tempo.xyz/mcp}"
DOCS_TLS_VALIDITY_DAYS = "30"
MPP_DOCS_ACCESS_LOG = "/var/log/mpp-docs/access.log"
MPP_DOCS_TLS_DIR = "mpp-docs-tls"
MPP_DOCS_BUNDLE_PATH = Path(".cache") / "mpp-docs" / "local" / "public"
DOCS_PROXY_SOURCE = "shared/docs/static-docs-proxy"


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


def is_mpp_tasks_path(path: str) -> bool:
    try:
        return Path(path).resolve() == Path("tasks/mpp").resolve()
    except OSError:
        return path == "tasks/mpp"


def is_tempo_tasks_path(path: str) -> bool:
    try:
        return Path(path).resolve() == Path("tasks/tempo-v1").resolve()
    except OSError:
        return path == "tasks/tempo-v1"


def is_checkout_tasks_path(path: str) -> bool:
    return Path(path).resolve().is_relative_to(Path("tasks/checkout-v1").resolve())


def has_checkout_tasks() -> bool:
    return any(
        task_file.is_file()
        for task_file in Path("tasks/checkout-v1").glob("*/task.toml")
    )


def selected_checkout_tasks(options: dict[str, Any]) -> set[str]:
    names = {
        task_file.parent.name
        for task_file in Path("tasks/checkout-v1").glob("*/task.toml")
    }
    requested_path = options.get("tasks")
    if requested_path and is_checkout_tasks_path(requested_path):
        path = Path(requested_path).resolve()
        if path != Path("tasks/checkout-v1").resolve():
            names &= {path.name}
    task_filter = options.get("task_filter")
    if task_filter:
        names = {
            name
            for name in names
            if fnmatch.fnmatchcase(name, task_filter)
            or fnmatch.fnmatchcase(f"checkout-v1/{name}", task_filter)
        }
    return names


def ensure_mpp_docs_bundle(options: dict[str, Any]) -> str | None:
    source = options.get("mpp_docs_source")
    if not source:
        return None
    targets_mpp = options.get("task_suite") in {"mpp", "all"} or any(
        is_mpp_tasks_path(path) for path in task_paths(options)
    )
    if not targets_mpp:
        raise RuntimeError("--mpp-docs-source is only valid for MPP task suites")
    bundle_path = MPP_DOCS_BUNDLE_PATH.resolve()
    run_python(
        "scripts/prepare_mpp_docs_bundle.py",
        ["--source", source, "--output", str(bundle_path), "--force"],
    )
    if not (bundle_path / "llms-full.txt").exists():
        raise RuntimeError(f"MPP docs bundle was not created at {bundle_path}")
    return str(bundle_path)


def preflight(variant: dict[str, Any], options: dict[str, Any]) -> None:
    if (
        options.get("tasks")
        and is_checkout_tasks_path(options["tasks"])
        and options.get("task_suite") != "checkout"
    ):
        raise RuntimeError("Checkout task paths require --task-suite checkout")
    if options.get("task_suite") == "checkout":
        profiles = (
            CHECKOUT_PROFILES
            if options.get("profile") == "all"
            else (checkout_profile(options),)
        )
        for profile in profiles:
            for key in CHECKOUT_PROFILES[profile]["credentials"]:
                if not os.environ.get(key):
                    raise RuntimeError(f"{profile} checkout requires {key}")
        if not has_checkout_tasks():
            raise RuntimeError("Checkout has no authored task yet")
        selected = set()
        for name in selected_checkout_tasks(options):
            metadata = tomlkit.parse(
                (Path("tasks/checkout-v1") / name / "task.toml").read_text()
            )["metadata"]
            # Cart tasks need their source payment method's credentials.
            selected.add(
                metadata.get("source_task")
                or metadata.get("scenario_id", f"checkout-v1/{name}").rsplit("/", 1)[-1]
            )
        if not os.environ.get("STRIPE_TEST_SECRET_KEY", "").startswith("sk_test_"):
            raise RuntimeError("Stripe checkout requires STRIPE_TEST_SECRET_KEY")
        if "stripe-link-discover" in selected and not os.environ.get(
            "STRIPE_TEST_PUBLISHABLE_KEY", ""
        ).startswith("pk_test_"):
            raise RuntimeError(
                "Stripe Link checkout requires STRIPE_TEST_PUBLISHABLE_KEY"
            )
        if selected:
            required = ("PAYPAL_SANDBOX_BUYER_EMAIL", "PAYPAL_SANDBOX_BUYER_PASSWORD")
            missing = [name for name in required if not os.environ.get(name)]
            if missing:
                raise RuntimeError(
                    f"Checkout wallet setup requires {', '.join(missing)}"
                )
        if "paypal-discover" in selected:
            required = ("PAYPAL_SANDBOX_CLIENT_ID", "PAYPAL_SANDBOX_CLIENT_SECRET")
            missing = [name for name in required if not os.environ.get(name)]
            if missing:
                raise RuntimeError(f"PayPal checkout runs require {', '.join(missing)}")
        if "braintree-card-discover" in selected:
            required = (
                "BRAINTREE_MERCHANT_ID",
                "BRAINTREE_PUBLIC_KEY",
                "BRAINTREE_PRIVATE_KEY",
            )
            missing = [name for name in required if not os.environ.get(name)]
            if missing:
                raise RuntimeError(
                    f"Braintree checkout runs require {', '.join(missing)}"
                )
        if "x402-usdc-discover" in selected and not re.fullmatch(
            r"0x[0-9a-fA-F]{64}", os.environ.get("X402_FUNDING_PRIVATE_KEY", "")
        ):
            raise RuntimeError("x402 checkout requires X402_FUNDING_PRIVATE_KEY")
        if "shopify-card-discover" in selected:
            required = (
                "SHOPIFY_SHOP",
                "SHOPIFY_CLIENT_ID",
                "SHOPIFY_CLIENT_SECRET",
                "SHOPIFY_VARIANT_ID",
                "SHOPIFY_STOREFRONT_PASSWORD",
            )
            missing = [name for name in required if not os.environ.get(name)]
            if missing:
                raise RuntimeError(
                    f"Shopify checkout runs require {', '.join(missing)}"
                )
    effective_agents = effective_agent_names(variant, options)
    needs_agent_auth = variant.get("needs_agent_auth") and effective_agents
    if needs_agent_auth and "claude-code" in effective_agents and not has_claude_auth():
        raise RuntimeError(
            "Missing Claude Code auth: set ANTHROPIC_API_KEY, or set both "
            "ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN."
        )
    if needs_agent_auth and "codex" in effective_agents and not has_codex_auth():
        raise RuntimeError(
            "Missing Codex auth: set OPENAI_API_KEY, or set CODEX_AUTH_JSON_PATH "
            "to an existing Codex auth.json file."
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


def effective_agent_names(variant: dict[str, Any], options: dict[str, Any]) -> set[str]:
    if agent_name := options.get("agent"):
        return {agent_name}
    job_agents = variant.get("job", {}).get("agents", [])
    names = {
        agent["name"]
        for agent in job_agents
        if agent.get("name") and agent.get("name") != "oracle"
    }
    if names:
        return names
    if default_agent := variant.get("default_agent"):
        return {default_agent}
    return set()


def has_claude_auth() -> bool:
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or (
            os.environ.get("ANTHROPIC_BASE_URL")
            and os.environ.get("ANTHROPIC_AUTH_TOKEN")
        )
    )


def has_codex_auth() -> bool:
    if os.environ.get("OPENAI_API_KEY"):
        return True
    if auth_json_path := os.environ.get("CODEX_AUTH_JSON_PATH"):
        return Path(auth_json_path).is_file()
    if os.environ.get("CODEX_FORCE_AUTH_JSON"):
        return (Path.home() / ".codex" / "auth.json").is_file()
    return False


def preflight_mcp_target(options: dict[str, Any]) -> None:
    if options["profile"] not in {MCP_DIRECT_PROFILE["id"], MCP_CODE_PROFILE["id"]}:
        return
    run_python(
        "scripts/verify_tempo_mcp.py",
        ["--url", os.environ.get("TEMPO_MCP_EVAL_URL", "https://api.tempo.xyz/mcp")],
    )


def preflight_production_agents(model_config: dict[str, Any]) -> None:
    if (
        any(model["agent"] == "claude-code" for model in model_config["models"])
        and not has_claude_auth()
    ):
        raise RuntimeError(
            "Missing Claude Code auth: set ANTHROPIC_API_KEY, or set both "
            "ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN."
        )
    if any(model["agent"] == "codex" for model in model_config["models"]) and not (
        has_codex_auth()
    ):
        raise RuntimeError("Missing Codex auth: set OPENAI_API_KEY.")


def task_paths(options: dict[str, Any]) -> list[str]:
    if options.get("tasks"):
        return [options["tasks"]]
    paths = {
        "tempo": "tasks/tempo-v1",
        "tempo-mcp": "tasks/tempo-mcp-v1",
        "mpp": "tasks/mpp",
        "checkout": "tasks/checkout-v1",
    }
    suite = options.get("task_suite") or "tempo"
    return (
        [paths[key] for key in ("tempo", "tempo-mcp", "mpp")]
        if suite == "all"
        else [paths[suite]]
    )


def validate_run_options(variant_name: str, options: dict[str, Any]) -> dict[str, Any]:
    variant = VARIANTS.get(variant_name)
    if not variant:
        raise RuntimeError(f"Unknown variant: {variant_name}")

    suite = options.get("task_suite") or "tempo"
    profile = options["profile"]
    profiles = SUITE_PROFILES[suite]
    if profile not in profiles:
        choices = ", ".join(profiles)
        raise RuntimeError(
            f"--profile {profile} is not valid for --task-suite {suite}; use {choices}"
        )

    job_agents = variant.get("job", {}).get("agents", [])
    if suite == "all" and (
        not job_agents or any(agent.get("name") != "oracle" for agent in job_agents)
    ):
        raise RuntimeError("--task-suite all requires an oracle variant")

    if (
        not variant.get("job")
        and not variant.get("production")
        and profile != DOCS_PROFILE["id"]
        and suite != "checkout"
    ):
        raise RuntimeError("Non-Docs profiles require a job-backed variant")
    if variant.get("job") and options.get("agent"):
        raise RuntimeError(
            "--agent is only supported by the model variant; use an agent-specific "
            "job variant for generated configs"
        )
    return variant


def sync_generated() -> None:
    run_python("scripts/sync_shared.py")
    compile_job_configs()


def image_ref(image: str) -> str:
    return str(TASKS_CONFIG["images"][image])


def build_images() -> None:
    """Build the paired local images once, including concurrent profile runs."""
    global _images_built
    with _IMAGE_BUILD_LOCK:
        if _images_built:
            return
        agent = image_ref("agent")
        run(
            "docker",
            [
                "build",
                "-t",
                agent,
                "-f",
                "shared/global/docker/agent/Dockerfile",
                ".",
            ],
        )
        run(
            "docker",
            [
                "build",
                "--build-arg",
                f"AGENT_IMAGE={agent}",
                "-t",
                image_ref("verifier"),
                "-f",
                "shared/global/docker/verifier/Dockerfile",
                ".",
            ],
        )
        run(
            "bash",
            ["ci_checks/check-image-boundary.sh", agent, image_ref("verifier")],
        )
        _images_built = True


def daytona_images(options: dict[str, Any]) -> dict[str, str]:
    images = {image: options.get(f"{image}_image") for image in ("agent", "verifier")}
    missing = [f"--{image}-image" for image, ref in images.items() if not ref]
    if missing:
        raise RuntimeError(
            f"Daytona requires {' and '.join(missing)}. Use the paired main source "
            "refs after validating image changes locally."
        )
    return {image: str(ref) for image, ref in images.items()}


def sync_dataset(options: dict[str, Any]) -> None:
    sync_generated()
    for path in task_paths(options):
        run("uv", ["run", "harbor", "sync", path])


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
    judge_model = parsed.get("judge_model", PINNED_JUDGE_MODEL)
    if not isinstance(judge_model, str) or not judge_model:
        raise RuntimeError(f"Invalid judge_model in {file_path}")
    n_concurrent_trials = validate_optional_positive_integer(
        string_field(parsed, "n_concurrent_trials"), "n_concurrent_trials"
    )
    return {
        "judge_model": judge_model,
        "n_concurrent_trials": n_concurrent_trials,
        "models": models,
    }


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
        "version": string_field(value, "version"),
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


def git_output(args: list[str]) -> str:
    result = subprocess.run(["git", *args], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def production_revision_env(options: dict[str, Any]) -> dict[str, str]:
    if git_output(["status", "--porcelain", "--untracked-files=all"]):
        raise RuntimeError("Production runs require a clean tempo-evals checkout")
    repository_sha = git_output(["rev-parse", "HEAD"]).lower()
    if not FULL_GIT_SHA_PATTERN.fullmatch(repository_sha):
        raise RuntimeError(f"Invalid tempo-evals Git SHA: {repository_sha!r}")

    revisions = {"TEMPO_EVALS_SHA": repository_sha}
    if options.get("task_suite") in {None, "tempo", "all"}:
        source = docs_source(options)
        docs_sha = source.get("sha", "").lower()
        if source["mode"] != "pinned" or not FULL_GIT_SHA_PATTERN.fullmatch(docs_sha):
            raise RuntimeError("Production Tempo runs require a full docs Git SHA")
        revisions["TEMPO_DOCS_SHA"] = docs_sha
    return revisions


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
        judge_model=job.get("judge_model", DEFAULT_JUDGE_MODEL),
        dind_image=RUN_CONFIG["daytona"]["dind_image"],
        codex_web_search=CODEX_WEB_SEARCH,
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
    if model.get("version"):
        agent["kwargs"] = {"version": model["version"]}
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
        "n_concurrent_trials": int(
            options.get("concurrency")
            or model_config.get("n_concurrent_trials")
            or "16"
        ),
        "environment_type": "daytona",
        "force_build": False,
        "judge_model": model_config["judge_model"],
        "agents": [production_agent(model) for model in model_config["models"]],
        "datasets": datasets_for_suite(options.get("task_suite") or "tempo"),
    }


def harbor_flags(options: dict[str, Any]) -> list[str]:
    names = (
        "no_force_build",
        "no_delete",
        "disable_verification",
        "install_only",
        "debug",
    )
    return [f"--{name.replace('_', '-')}" for name in names if options.get(name)]


def run_production_variant(
    run_id: str,
    options: dict[str, Any],
    docs_bundle: str | None,
    mpp_docs_bundle: str | None,
) -> None:
    models_config_path = options.get("models_config") or "config/models.production.yaml"
    model_config = parse_model_config(
        models_config_path, options.get("agent_concurrency")
    )
    preflight_production_agents(model_config)
    job = production_job(run_id, model_config, options)
    rendered = render_job_config(job, benchmark=None)
    rendered["verifier"]["env"].update(production_revision_env(options))
    config = stage_daytona_config(
        rendered, run_id, docs_bundle, mpp_docs_bundle, options
    )
    max_retries = options.get("max_retries") or "4"
    args = ["run", "harbor", "run", "-c", config]
    if options.get("env_file"):
        args.extend(["--env-file", options["env_file"]])
    args.extend(harbor_flags(options))
    args.extend(["--max-retries", max_retries])
    os.environ["TEMPO_DOCS_BUNDLE_PATH"] = ""
    os.environ["MPP_DOCS_BUNDLE_PATH"] = ""
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
    source = (
        {"mode": "live"}
        if uses_live_mcp_eval(options) or options.get("task_suite") == "checkout"
        else docs_source(options)
    )
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
    if task_suite == "checkout":
        return [{"path": "tasks/checkout-v1"}]
    return copy.deepcopy(read_yaml("config/datasets.yaml").get("datasets", []))


def apply_task_suite(
    config: dict[str, Any],
    task_suite: str | None,
) -> dict[str, Any]:
    config["datasets"] = datasets_for_suite(task_suite or "tempo")
    if task_suite == "checkout":
        verifier_env = config.setdefault("verifier", {}).setdefault("env", {})
        for name in (
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "REWARDKIT_JUDGE",
        ):
            verifier_env.pop(name, None)
    return config


def apply_task_filter(
    config: dict[str, Any],
    task_filter: str | None,
) -> dict[str, Any]:
    if not task_filter:
        return config

    if any(
        dataset.get("path") == "tasks/checkout-v1"
        for dataset in config.get("datasets", [])
    ):
        config["datasets"] = [
            {
                "path": "tasks/checkout-v1",
                "task_names": [task_filter.removeprefix("checkout-v1/")],
            }
        ]
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


def checkout_profile(options: dict[str, Any]) -> str:
    profile = options.get("profile", "docs")
    return "local" if profile == "docs" else profile


def codex_web_search(options: dict[str, Any]) -> str:
    return "live" if options.get("task_suite") == "checkout" else CODEX_WEB_SEARCH


def apply_profile(config: dict[str, Any], profile_id: str) -> dict[str, Any]:
    if profile_id in CHECKOUT_PROFILES:
        for agent in config.get("agents", []):
            agent.setdefault("env", {})["CHECKOUT_BROWSER_PROFILE"] = profile_id
        return config
    if profile_id == DOCS_PROFILE["id"]:
        return config

    profile = tempo_profile(profile_id)
    for agent in config.get("agents", []):
        if agent.get("name") == "oracle":
            if docs_tool := MCP_ORACLE_DOCS_TOOLS.get(profile_id):
                agent.setdefault("env", {}).update(
                    {
                        "TEMPO_MCP_ORACLE_URL": profile["mcp_servers"][0]["url"],
                        "TEMPO_MCP_ORACLE_DOCS_TOOL": docs_tool,
                    }
                )
        else:
            agent["mcp_servers"] = copy.deepcopy(profile["mcp_servers"])
    return config


def apply_pair_id(config: dict[str, Any], pair_id: str | None) -> dict[str, Any]:
    if not pair_id:
        return config
    for agent in config.get("agents", []):
        if agent.get("name") != "oracle":
            agent.setdefault("env", {})["STABLE_BENCH_PAIR_ID"] = pair_id
    return config


def redirect_dataset_paths(config: dict[str, Any], staging_root: Path) -> None:
    path_map = {
        "tasks/mpp": str(staging_root / "tasks" / "mpp"),
        "tasks/tempo-v1": str(staging_root / "tasks" / "tempo-v1"),
        "tasks/tempo-mcp-v1": str(staging_root / "tasks" / "tempo-mcp-v1"),
        "tasks/checkout-v1": str(staging_root / "tasks" / "checkout-v1"),
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


def generate_docs_tls_assets(
    environment_dir: Path,
    *,
    hostname: str = "docs.tempo.xyz",
    tls_dir_name: str = DOCS_TLS_DIR,
) -> Path:
    """Create an ephemeral CA and docs leaf certificate for one run."""
    tls_dir = environment_dir / tls_dir_name
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
            "/CN=Stable Bench Ephemeral Docs CA",
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
            f"/CN={hostname}",
        ]
    )
    extensions.write_text(
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\n"
        f"subjectAltName=DNS:{hostname}\n"
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
    dockerignore = environment_dir / ".dockerignore"
    ignore_entry = f"{tls_dir.name}/*\n!{tls_dir.name}/{DOCS_CA_FILE}\n"
    existing_ignore = dockerignore.read_text() if dockerignore.exists() else ""
    if existing_ignore and not existing_ignore.endswith("\n"):
        existing_ignore = f"{existing_ignore}\n"
    content = dockerfile.read_text().rstrip()
    dockerfile.write_text(
        f"{content}\n\n"
        f"COPY {ca_path.as_posix()} {DOCS_CA_DESTINATION}\n"
        "RUN update-ca-certificates\n"
        f"ENV NODE_EXTRA_CA_CERTS={DOCS_CA_DESTINATION}\n"
    )
    dockerignore.write_text(f"{existing_ignore}{ignore_entry}")


def stage_docs_proxy_task(
    task_dir: Path,
    *,
    docs_bundle: str,
    compose_source: str,
    bundle_dir_name: str,
    access_log_path: str,
    service: str,
    hostname: str,
    tls_dir_name: str,
) -> None:
    task_config_path = task_dir / "task.toml"
    config = tomlkit.parse(task_config_path.read_text())
    artifacts = config.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError(f"Missing artifacts array in staged task: {task_dir}")
    access_log = tomlkit.inline_table()
    access_log["source"] = access_log_path
    access_log["service"] = service
    artifacts.append(access_log)
    task_config_path.write_text(tomlkit.dumps(config))

    environment_dir = task_dir / "environment"
    shutil.copyfile(compose_source, environment_dir / "docker-compose.yaml")
    shutil.copytree(
        DOCS_PROXY_SOURCE,
        environment_dir / "docs-proxy",
        dirs_exist_ok=True,
    )
    shutil.copytree(docs_bundle, environment_dir / bundle_dir_name, dirs_exist_ok=True)
    tls_dir = generate_docs_tls_assets(
        environment_dir,
        hostname=hostname,
        tls_dir_name=tls_dir_name,
    )
    trust_docs_ca(environment_dir, tls_dir)


def stage_pinned_docs_task(task_dir: Path, docs_bundle: str) -> None:
    stage_docs_proxy_task(
        task_dir,
        docs_bundle=docs_bundle,
        compose_source="shared/tempo/docker/compose/tempo-docs.yaml",
        bundle_dir_name="tempo-docs-bundle",
        access_log_path=DOCS_ACCESS_LOG,
        service="tempo-docs",
        hostname="docs.tempo.xyz",
        tls_dir_name=DOCS_TLS_DIR,
    )


def stage_mpp_docs_task(task_dir: Path, mpp_docs_bundle: str) -> None:
    stage_docs_proxy_task(
        task_dir,
        docs_bundle=mpp_docs_bundle,
        compose_source="shared/mpp/docker/compose/mpp-docs.yaml",
        bundle_dir_name="mpp-docs-bundle",
        access_log_path=MPP_DOCS_ACCESS_LOG,
        service="mpp-docs",
        hostname="mpp.dev",
        tls_dir_name=MPP_DOCS_TLS_DIR,
    )


def override_staged_images(staging_root: Path, images: dict[str, str]) -> None:
    dockerfiles = {"agent": "environment", "verifier": "tests"}
    for task_config in staging_root.glob("tasks/*/*/task.toml"):
        for image, directory in dockerfiles.items():
            dockerfile = task_config.parent / directory / "Dockerfile"
            if not dockerfile.exists():
                raise RuntimeError(f"Missing staged {image} Dockerfile: {dockerfile}")
            expected = f"FROM {image_ref(image)}"
            content = dockerfile.read_text()
            if expected not in content:
                raise RuntimeError(f"Unexpected {image} image in {dockerfile}")
            dockerfile.write_text(
                content.replace(expected, f"FROM {images[image]}", count=1)
            )


def stage_browser_profile(task_dir: Path, profile: str) -> None:
    if profile not in CHECKOUT_PROFILES:
        raise ValueError(f"Unknown checkout browser profile: {profile}")
    environment = task_dir / "environment"
    shutil.copytree(
        "shared/checkout/browser",
        environment / "browser",
        ignore=shutil.ignore_patterns("node_modules", "package-lock.json"),
    )
    compose_file = environment / "docker-compose.yaml"
    compose = yaml.safe_load(compose_file.read_text())
    browser = compose["services"]["browser"]
    # Extend the exact task-pinned MCP image; tool schemas stay identical.
    image = browser.pop("image")
    browser["build"] = {"context": "./browser", "args": {"MCP_IMAGE": image}}
    browser["entrypoint"] = "/opt/checkout/node_modules/.bin/tsx"
    output_dir = "/tmp/.playwright-mcp"
    output_volume = f"checkout-browser-output:{output_dir}"
    compose["volumes"]["checkout-browser-output"] = None
    browser.setdefault("volumes", []).append(output_volume)
    compose["services"]["main"]["volumes"].append(f"{output_volume}:ro")
    browser["command"] += [
        "--no-webmcp",
        "--output-dir",
        output_dir,
        "--file-paths",
        "absolute",
        "--config",
        "/opt/checkout/browser.json",
        "--init-page",
        "/opt/checkout/merchant-route.ts",
    ]
    compose["services"]["browser-ready"] = {
        "build": browser["build"],
        "entrypoint": "/opt/checkout/node_modules/.bin/tsx",
        "command": ["/opt/checkout/ready.ts"],
        "depends_on": {"link": {"condition": "service_completed_successfully"}},
        "restart": "no",
    }
    compose["services"]["main"]["depends_on"]["browser-ready"] = {
        "condition": "service_completed_successfully"
    }
    if profile != "local":
        browser["command"] += ["--cdp-endpoint", "ws://browser-session:9222"]
        browser["depends_on"] = {"browser-session": {"condition": "service_healthy"}}
        compose["services"]["browser-session"] = {
            "build": browser["build"],
            "entrypoint": "/opt/checkout/node_modules/.bin/tsx",
            "command": ["/opt/checkout/session.ts"],
            "environment": {
                "CHECKOUT_BROWSER_PROFILE": profile,
                **{
                    key: "${" + key + "}"
                    for key in CHECKOUT_PROFILES[profile]["credentials"]
                },
            },
            "healthcheck": {
                "test": [
                    "CMD",
                    "node",
                    "-e",
                    "fetch('http://localhost:9222/health')"
                    ".then(r => process.exit(r.ok ? 0 : 1))"
                    ".catch(() => process.exit(1))",
                ],
                "interval": "2s",
                "timeout": "5s",
                "retries": 60,
            },
            "stop_grace_period": "30s",
        }
    compose_file.write_text(yaml.safe_dump(compose, sort_keys=False))
    task_file = task_dir / "task.toml"
    task = tomlkit.parse(task_file.read_text())
    task["metadata"]["browser_profile"] = profile
    env = task["environment"]["env"]
    for key in CHECKOUT_PROFILES[profile]["credentials"]:
        env[key] = "${" + key + "}"
    task_file.write_text(tomlkit.dumps(task))


def stage_task_datasets(
    staging_root: Path,
    docs_bundle: str | None,
    mpp_docs_bundle: str | None = None,
    images: dict[str, str] | None = None,
    checkout: bool = False,
    browser_profile: str = "local",
) -> None:
    if checkout:
        staged_checkout = staging_root / "tasks" / "checkout-v1"
        staged_checkout.parent.mkdir(parents=True, exist_ok=True)
        copy_tasks(Path("tasks/checkout-v1"), staged_checkout)
        for task_file in staged_checkout.glob("*/task.toml"):
            stage_browser_profile(task_file.parent, browser_profile)
        if images is not None:
            override_staged_images(staging_root, images)
        return

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
        mpp_tasks = staging_root / "tasks" / "mpp"
        copy_tasks(Path("tasks/mpp"), mpp_tasks)
        if mpp_docs_bundle is not None:
            for task_dir in mpp_tasks.iterdir():
                if task_dir.is_dir() and (task_dir / "task.toml").exists():
                    stage_mpp_docs_task(task_dir, mpp_docs_bundle)
    if images is not None:
        override_staged_images(staging_root, images)
    if docs_bundle is not None:
        for task_dir in staged_tasks.iterdir():
            if task_dir.is_dir() and (task_dir / "task.toml").exists():
                stage_pinned_docs_task(task_dir, docs_bundle)


def finalize_config(config: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    result = apply_model_override(
        apply_task_filter(
            apply_task_suite(config, options.get("task_suite")),
            options.get("task_filter"),
        ),
        options.get("model"),
    )
    if options.get("task_suite") == "checkout":
        for agent in result.get("agents", []):
            if agent.get("name") == "codex":
                agent.setdefault("kwargs", {})["web_search"] = codex_web_search(options)
        method = os.environ.get("CHECKOUT_ORACLE_PAYMENT_METHOD")
        if method:
            for agent in result.get("agents", []):
                if agent.get("name") == "oracle":
                    agent.setdefault("env", {})["CHECKOUT_ORACLE_PAYMENT_METHOD"] = (
                        method
                    )
    return result


def stage_daytona_config(
    config: dict[str, Any],
    run_id: str,
    docs_bundle: str | None,
    mpp_docs_bundle: str | None,
    options: dict[str, Any],
) -> str:
    staging_root = Path(".cache") / "harbor-daytona" / run_id
    staged_config = staging_root / "job.yaml"

    shutil.rmtree(staging_root, ignore_errors=True)
    stage_task_datasets(
        staging_root,
        docs_bundle,
        mpp_docs_bundle,
        daytona_images(options),
        checkout=options.get("task_suite") == "checkout",
        browser_profile=checkout_profile(options),
    )

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
    mpp_docs_bundle: str | None,
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
        or mpp_docs_bundle is not None
        or options["profile"] in {MCP_DIRECT_PROFILE["id"], MCP_CODE_PROFILE["id"]}
        or options.get("task_suite") in {"tempo-mcp", "checkout", "all"}
    ):
        stage_task_datasets(
            staging_root,
            docs_bundle,
            mpp_docs_bundle,
            checkout=options.get("task_suite") == "checkout",
            browser_profile=checkout_profile(options),
        )
        redirect_dataset_paths(config, staging_root)
    staged_config.write_text(dump_yaml(config))
    return str(staged_config)


def stage_direct_task_path(
    run_id: str,
    task_path: str,
    docs_bundle: str | None,
    mpp_docs_bundle: str | None,
    browser_profile: str = "local",
) -> str:
    if is_checkout_tasks_path(task_path):
        staging_root = Path(".cache") / "harbor-model" / run_id
        shutil.rmtree(staging_root, ignore_errors=True)
        stage_task_datasets(
            staging_root, None, checkout=True, browser_profile=browser_profile
        )
        return str(
            staging_root
            / "tasks/checkout-v1"
            / Path(task_path).resolve().relative_to(Path("tasks/checkout-v1").resolve())
        )
    if docs_bundle is None and mpp_docs_bundle is None:
        return task_path

    if is_mpp_tasks_path(task_path):
        staged_path = "tasks/mpp"
    elif is_tempo_tasks_path(task_path):
        staged_path = "tasks/tempo-v1"
    else:
        return task_path

    staging_root = Path(".cache") / "harbor-model" / run_id
    shutil.rmtree(staging_root, ignore_errors=True)
    stage_task_datasets(staging_root, docs_bundle, mpp_docs_bundle)
    return str(staging_root / staged_path)


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
    if variant_name == "build-images":
        build_images()
        return
    if variant_name == "check-dataset":
        sync_dataset(options)
        for path in task_paths(options):
            run("git", ["diff", "--exit-code", f"{path}/dataset.toml"])
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
        variant = validate_run_options(variant_name, options)
        if options.get("task_suite") == "checkout" and not variant.get("production"):
            load_env_file(options.get("env_file"))
            preflight(variant, options)
        if variant.get("production"):
            prepare_production_profiles(variant, options)
        elif options["sync"]:
            sync_dataset(options)
        benchmark = run_benchmark_key(variant, options.get("task_suite"))
        prefix = versioned_name(benchmark, variant["prefix"])
        pair_id = options.get("job_name") or (
            f"{prefix}-{production_timestamp()}"
            if variant.get("production")
            else f"{prefix}-mcp-pair-{timestamp()}"
        )
        mcp_target_preflight_done = False
        if (
            options["profile"] == "mcp-both"
            and uses_live_mcp_eval(options)
            and variant.get("needs_daytona_auth")
        ):
            load_env_file(options.get("env_file"))
            preflight_mcp_target(options | {"profile": MCP_DIRECT_PROFILE["id"]})
            mcp_target_preflight_done = True
        profile_options = [
            options
            | {
                "profile": profile_id,
                "job_name": (
                    pair_id if variant.get("production") else f"{pair_id}-{profile_id}"
                ),
                "pair_id": pair_id,
                "sync": False,
                "mcp_target_preflight_done": mcp_target_preflight_done,
            }
            for index, profile_id in enumerate(
                (MCP_DIRECT_PROFILE["id"], MCP_CODE_PROFILE["id"])
                if options["profile"] == "mcp-both"
                else tuple(CHECKOUT_PROFILES)
                if options.get("task_suite") == "checkout"
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
    variant = validate_run_options(variant_name, options)
    if options.get("task_suite") == "checkout":
        options = options | {"profile": checkout_profile(options)}
    source = (
        {"mode": "live"}
        if uses_live_mcp_eval(options) or options.get("task_suite") == "checkout"
        else docs_source(options)
    )
    load_env_file(options.get("env_file"))
    preflight(variant, options)
    if not options.get("mcp_target_preflight_done"):
        preflight_mcp_target(options)
    if options.get("sync"):
        sync_dataset(options)
    if not variant.get("needs_daytona_auth"):
        build_images()
    docs_bundle = None if source["mode"] == "live" else ensure_docs_bundle(source)
    mpp_docs_bundle = ensure_mpp_docs_bundle(options)

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
        run_production_variant(run_id, options, docs_bundle, mpp_docs_bundle)
        return

    if variant.get("job"):
        job_config = load_compiled_config(variant_name)
        config = (
            stage_daytona_config(
                job_config, run_id, docs_bundle, mpp_docs_bundle, options
            )
            if variant.get("needs_daytona_auth")
            else stage_filtered_config(
                job_config, run_id, options, docs_bundle, mpp_docs_bundle
            )
        )
        args.extend(["-c", config])
    else:
        task_path = stage_direct_task_path(
            run_id,
            task_paths(options)[0],
            docs_bundle,
            mpp_docs_bundle,
            browser_profile=checkout_profile(options),
        )
        args.extend(
            [
                "--path",
                task_path,
            ]
        )
        agent = options.get("agent") or variant.get("default_agent") or "claude-code"
        args.extend(["--agent", agent])
        if agent == "codex":
            args.extend(["--agent-kwarg", f"web_search={codex_web_search(options)}"])
        if options.get("task_suite") == "checkout":
            args.extend(
                ["--agent-env", f"CHECKOUT_BROWSER_PROFILE={options['profile']}"]
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
    args.extend(harbor_flags(options))
    max_retries = options.get("max_retries") or (
        "2" if variant.get("needs_daytona_auth") else None
    )
    if max_retries:
        args.extend(["--max-retries", max_retries])
    os.environ["TEMPO_DOCS_BUNDLE_PATH"] = (
        "" if variant.get("needs_daytona_auth") or docs_bundle is None else docs_bundle
    )
    os.environ["MPP_DOCS_BUNDLE_PATH"] = (
        ""
        if variant.get("needs_daytona_auth") or mpp_docs_bundle is None
        else mpp_docs_bundle
    )
    args.append("-y")
    run("uv", args)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except RuntimeError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error
