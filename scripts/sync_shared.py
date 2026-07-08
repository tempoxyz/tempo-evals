#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import tomllib
from pathlib import Path
from typing import Any

import tomlkit
import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "tasks" / "tempo"
MPP_TASKS_DIR = ROOT / "tasks" / "mpp"
MPP_SHARED_DIR = ROOT / "shared" / "mpp"

# All task matrix data (base task slugs, generated profiles, MPP shared file
# lists, ...) lives in config/tasks.yaml.
TASKS_CONFIG: dict[str, Any] = yaml.safe_load(
    (ROOT / "config" / "tasks.yaml").read_text()
)
BASE_TASK_SLUGS: list[str] = TASKS_CONFIG["base_task_slugs"]
GENERATED_PROFILES: list[dict[str, Any]] = TASKS_CONFIG["profiles"]
PROFILES_BY_ID: dict[str, dict[str, Any]] = {
    profile["id"]: profile for profile in GENERATED_PROFILES
}
QUALITY_ENV: dict[str, str] = TASKS_CONFIG["quality_env"]
EXECUTION_CONSTRAINTS: str = TASKS_CONFIG["execution_constraints"]
MPP_SHARED_FILES: list[dict[str, Any]] = TASKS_CONFIG["mpp"]["shared_files"]
MPP_TASK_LOCAL_OVERRIDES: dict[str, list[str]] = TASKS_CONFIG["mpp"][
    "task_local_overrides"
]
BASE_SUFFIX = "-base"


def remove_path(target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink(missing_ok=True)
    elif target.is_dir():
        shutil.rmtree(target)


def skip_node_artifacts(source_path: Path) -> bool:
    parts = source_path.parts
    return "node_modules" in parts or source_path.name == "package-lock.json"


def copy_dir(source: Path, destination: Path) -> None:
    remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        destination,
        ignore=lambda directory, names: [
            name for name in names if skip_node_artifacts(Path(directory) / name)
        ],
    )


def copy_generated_task(source: Path, destination: Path) -> None:
    exclusions = [
        Path("environment/Dockerfile"),
        Path("environment/docker-compose.yaml"),
        Path("environment/tempo-localnet"),
        Path("environment/tempo-docs"),
        Path("environment/tempo-docs-bundle"),
        Path("environment/rewardkit-package"),
        Path("tests/tempo-bench-verifier"),
        Path("tests/e2e/verify-tempo.sh"),
        Path("tests/correctness/verify-tempo.sh"),
        Path("tests/quality"),
        Path("tests/test.sh"),
    ]

    def ignore(directory: str, names: list[str]) -> list[str]:
        ignored = []
        for name in names:
            source_path = Path(directory) / name
            relative = source_path.relative_to(source)
            if skip_node_artifacts(source_path):
                ignored.append(name)
                continue
            if any(
                relative == excluded or excluded in relative.parents
                for excluded in exclusions
            ):
                ignored.append(name)
        return ignored

    remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, ignore=ignore, symlinks=True)


def copy_file(source: Path, destination: Path) -> None:
    remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def write_file(destination: Path, content: str) -> None:
    remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content)


def toml_string(value: str) -> str:
    return json.dumps(value)


def update_task_toml(task_dir: Path, source_slug: str, profile: dict[str, Any]) -> None:
    task_config_path = task_dir / "task.toml"
    task_name = f"tempo/{source_slug}{profile['suffix']}"
    doc = tomlkit.parse(task_config_path.read_text())

    task = doc["task"]
    task["name"] = task_name
    description = str(task.get("description", task_name))
    task["description"] = f"{description} ({profile['label']} profile)."
    keywords = task.get("keywords")
    if keywords is not None and profile["id"] not in keywords:
        keywords.append(profile["id"])

    if "metadata" in doc:
        doc["metadata"]["profile"] = profile["id"]

    environment = doc["environment"]
    environment.pop("mcp_servers", None)
    environment.pop("network_mode", None)
    environment.pop("allowed_hosts", None)
    for other_profile in GENERATED_PROFILES:
        for key in other_profile.get("env", {}):
            environment["env"].pop(key, None)

    for key, value in profile.get("env", {}).items():
        environment["env"][key] = value
    if server_configs := profile.get("mcp_servers"):
        servers = tomlkit.aot()
        for server_config in server_configs:
            server = tomlkit.table()
            for key, value in server_config.items():
                server[key] = value
            servers.append(server)
        environment["mcp_servers"] = servers

    write_file(task_config_path, tomlkit.dumps(doc))


def append_profile_instruction(task_dir: Path, profile: dict[str, Any]) -> None:
    instruction_path = task_dir / "instruction.md"
    content = re.sub(
        r"\nTempo integration docs are available through the configured MCP "
        r"server named[\s\S]*?Use it if your agent runtime exposes MCP tools\.\n",
        "\n",
        instruction_path.read_text(),
    )
    content = re.sub(
        r"\n## Tempo Access Profile[\s\S]*?(?=\n## |\nRequirements:|$)", "\n", content
    )
    content = re.sub(
        r"\n## Execution Constraints[\s\S]*?(?=\n## |\nRequirements:|$)", "\n", content
    )

    if instruction := profile.get("instruction"):
        content = content.replace("\nRequirements:", f"\n{instruction}\nRequirements:")
    content = content.replace(
        "\nRequirements:", f"\n{EXECUTION_CONSTRAINTS}\nRequirements:"
    )
    write_file(instruction_path, f"{content.rstrip()}\n")


def update_profile_quality(task_dir: Path) -> None:
    profile_id = read_string_value(task_dir / "task.toml", "metadata.profile")
    profile = PROFILES_BY_ID.get(profile_id or "", {})
    check = profile.get("quality_check")
    if not check:
        return
    check_path = task_dir / "tests" / "quality" / "check.py"
    content = check_path.read_text()
    write_file(check_path, f"{content.rstrip()}\n\n{check}")


def materialize_task_matrix() -> None:
    generated_slugs: set[str] = set()
    for base_slug in BASE_TASK_SLUGS:
        source_dir = TASKS_DIR / base_slug
        if not (source_dir / "task.toml").exists():
            msg = f"Missing source task: {source_dir}"
            raise RuntimeError(msg)
        source_slug = base_slug[: -len(BASE_SUFFIX)]
        for profile in GENERATED_PROFILES:
            slug = f"{source_slug}{profile['suffix']}"
            task_dir = TASKS_DIR / slug
            copy_generated_task(source_dir, task_dir)
            generated_slugs.add(slug)
            update_task_toml(task_dir, source_slug, profile)
            append_profile_instruction(task_dir, profile)

    remove_path(TASKS_DIR / "transfer-with-memo-docs-mcp")
    legacy_suffixes = ["-docs-url", "-tempo-mcp", "-docs-mcp"]
    generated_suffixes = [
        profile["suffix"] for profile in GENERATED_PROFILES
    ] + legacy_suffixes
    for entry in TASKS_DIR.iterdir():
        if not entry.is_dir():
            continue
        slug = entry.name
        is_generated_profile = any(
            slug.endswith(suffix) for suffix in generated_suffixes
        )
        if is_generated_profile and slug not in generated_slugs:
            remove_path(entry)


def read_dataset_digests() -> dict[str, str]:
    dataset_path = TASKS_DIR / "dataset.toml"
    if not dataset_path.exists():
        return {}

    data = tomllib.loads(dataset_path.read_text())
    return {
        task["name"]: task["digest"]
        for task in data.get("tasks", [])
        if isinstance(task.get("name"), str) and isinstance(task.get("digest"), str)
    }


def matrix_task_names() -> list[str]:
    names: list[str] = []
    for base_slug in BASE_TASK_SLUGS:
        names.append(f"tempo/{base_slug}")
        source_slug = base_slug[: -len(BASE_SUFFIX)]
        names.extend(
            f"tempo/{source_slug}{profile['suffix']}" for profile in GENERATED_PROFILES
        )
    return names


def write_dataset_manifest() -> None:
    digests = read_dataset_digests()
    placeholder_digest = "sha256:" + "0" * 64
    task_entries = "\n".join(
        f"[[tasks]]\nname = {toml_string(name)}\n"
        f"digest = {toml_string(digests.get(name, placeholder_digest))}\n"
        for name in matrix_task_names()
    )
    write_file(
        TASKS_DIR / "dataset.toml",
        "# Dataset manifest for tempo/tempo-bench-v1\n"
        "# Generated by scripts/sync_shared.py. Run `harbor sync tasks/tempo` "
        "to refresh digests.\n\n"
        "[dataset]\n"
        'name = "tempo/tempo-bench-v1"\n'
        'description = "Tempo integration benchmark"\n'
        'keywords = [ "stablecoins", "docs", "tempo",]\n'
        "[[dataset.authors]]\n"
        'name = "Tempo"\n\n\n'
        f"{task_entries}\n",
    )


def copy_verifier(source: Path, destination: Path, case_id: str) -> None:
    shutil.rmtree(destination, ignore_errors=True)
    copy_file(source / "package.json", destination / "package.json")
    copy_dir(source / "bin", destination / "bin")

    source_src = source / "src"
    destination_src = destination / "src"
    for entry in source_src.iterdir():
        if entry.is_file():
            copy_file(entry, destination_src / entry.name)
    copy_file(
        source_src / "cases" / f"{case_id}.js",
        destination_src / "cases" / f"{case_id}.js",
    )
    write_file(
        destination_src / "cases" / "index.js",
        f"module.exports = {{\n"
        f'  {toml_string(case_id)}: require("./{case_id}"),\n'
        f"}};\n",
    )


def assert_task_rewardkit(task_dir: Path) -> None:
    if not (task_dir / "tests" / "reward.toml").exists():
        msg = f"Missing task-local RewardKit file: {task_dir / 'tests' / 'reward.toml'}"
        raise RuntimeError(msg)
    criteria_candidates = [
        "tests/correctness/criteria.py",
        "tests/criteria/check.py",
    ]
    if not any(
        (task_dir / relative_path).exists() for relative_path in criteria_candidates
    ):
        msg = (
            "Missing task-local RewardKit file: "
            f"{' or '.join(criteria_candidates)} in {task_dir}"
        )
        raise RuntimeError(msg)


def read_first_existing(task_dir: Path, relative_paths: list[str]) -> str:
    for relative_path in relative_paths:
        absolute_path = task_dir / relative_path
        if absolute_path.exists():
            return absolute_path.read_text()
    msg = f"Missing required file in {task_dir}: {' or '.join(relative_paths)}"
    raise RuntimeError(msg)


def sync_rewardkit(task_dir: Path) -> None:
    assert_task_rewardkit(task_dir)
    criteria_content = read_first_existing(
        task_dir,
        ["tests/correctness/criteria.py", "tests/criteria/check.py"],
    ).replace("/tests/e2e/verify-tempo.sh", "/tests/correctness/verify-tempo.sh")

    for relative_path in [
        "tests/turns",
        "tests/tokens",
        "tests/reward",
        "tests/criteria",
        "tests/criteria.py",
        "tests/e2e",
        "tests/correctness",
        "tests/quality",
    ]:
        remove_path(task_dir / relative_path)
    write_file(
        task_dir / "tests" / "reward.toml",
        '[[reward]]\nname = "reward"\naggregation = "weighted_mean"\n',
    )
    write_file(task_dir / "tests" / "correctness" / "criteria.py", criteria_content)
    copy_dir(ROOT / "shared" / "rewardkit" / "quality", task_dir / "tests" / "quality")
    update_profile_quality(task_dir)
    verify_path = task_dir / "tests" / "correctness" / "verify-tempo.sh"
    copy_file(ROOT / "shared" / "rewardkit" / "verify-tempo.sh", verify_path)
    verify_path.chmod(0o755)


def ensure_quality_env(task_dir: Path) -> None:
    task_config_path = task_dir / "task.toml"
    doc = tomlkit.parse(task_config_path.read_text())
    env = doc["environment"]["env"]
    changed = False
    for key, value in QUALITY_ENV.items():
        if key not in env:
            env[key] = value
            changed = True
    if changed:
        write_file(task_config_path, tomlkit.dumps(doc))


def relative_symlink_target(destination: Path, source: Path) -> str:
    return os.path.relpath(source, destination.parent)


def link_dir(source: Path, destination: Path) -> None:
    remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(
        relative_symlink_target(destination, source), target_is_directory=True
    )


def link_file(source: Path, destination: Path) -> None:
    remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(relative_symlink_target(destination, source))


def read_toml(file_path: Path) -> dict[str, Any]:
    return tomllib.loads(file_path.read_text())


def nested_value(data: dict[str, Any], dotted_key: str) -> Any:
    value: Any = data
    for part in dotted_key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def read_string_table(file_path: Path, table_name: str) -> dict[str, str]:
    table = nested_value(read_toml(file_path), table_name)
    if not isinstance(table, dict):
        return {}
    return {key: value for key, value in table.items() if isinstance(value, str)}


def read_string_value(file_path: Path, dotted_key: str) -> str | None:
    value = nested_value(read_toml(file_path), dotted_key)
    return value if isinstance(value, str) else None


def assert_verifier_env_allowed(task_dir: Path) -> None:
    task_config_path = task_dir / "task.toml"
    verifier_env = read_string_table(task_config_path, "verifier.env")
    environment_mode = read_string_value(task_config_path, "verifier.environment_mode")
    if environment_mode != "separate" and verifier_env:
        msg = (
            "[verifier.env] must be absent unless [verifier].environment_mode = "
            f'"separate" in {task_config_path}'
        )
        raise RuntimeError(msg)


def read_task_case_id(task_dir: Path) -> str | None:
    return read_string_table(task_dir / "task.toml", "environment.env").get(
        "TEMPO_BENCH_CASE"
    )


def task_uses_local_tempo_docs(task_dir: Path) -> bool:
    task_config_path = task_dir / "task.toml"
    compose_path = task_dir / "environment" / "docker-compose.yaml"
    task_config = task_config_path.read_text() if task_config_path.exists() else ""
    compose = compose_path.read_text() if compose_path.exists() else ""
    return (
        'profile = "docs"' in task_config
        or "TEMPO_DOCS_URL" in task_config
        or "tempo-docs:" in compose
    )


def assert_compose_build_contexts(task_dir: Path) -> None:
    compose_path = task_dir / "environment" / "docker-compose.yaml"
    compose = compose_path.read_text()
    for match in re.finditer(r"^\s*context:\s*(.+?)\s*$", compose, re.MULTILINE):
        context_path = match.group(1).strip("\"'")
        absolute_context_path = (compose_path.parent / context_path).resolve()
        if not absolute_context_path.exists():
            msg = f"Missing Docker Compose build context: {absolute_context_path}"
            raise RuntimeError(msg)


def task_dirs() -> list[Path]:
    return sorted(
        entry
        for entry in TASKS_DIR.iterdir()
        if entry.is_dir() and (entry / "task.toml").exists()
    )


def mpp_task_dirs() -> list[Path]:
    if not MPP_TASKS_DIR.exists():
        return []
    return sorted(
        entry
        for entry in MPP_TASKS_DIR.iterdir()
        if entry.is_dir() and (entry / "task.toml").exists()
    )


def sync_mpp_tasks() -> int:
    tasks = mpp_task_dirs()
    for task_dir in tasks:
        overrides = set(MPP_TASK_LOCAL_OVERRIDES.get(task_dir.name, []))
        for shared_file in MPP_SHARED_FILES:
            source = shared_file["path"]
            if source in overrides:
                continue
            destination = task_dir / source
            copy_file(MPP_SHARED_DIR / source, destination)
            if shared_file.get("executable"):
                destination.chmod(0o755)
        copy_dir(
            ROOT / "shared" / "rewardkit-package",
            task_dir / "environment" / "rewardkit-package",
        )
    return len(tasks)


def main() -> None:
    materialize_task_matrix()
    write_dataset_manifest()
    tasks = task_dirs()

    for task_dir in tasks:
        ensure_quality_env(task_dir)
        assert_verifier_env_allowed(task_dir)
        case_id = read_task_case_id(task_dir)
        if not case_id:
            msg = f"TEMPO_BENCH_CASE is missing in {task_dir / 'task.toml'}"
            raise RuntimeError(msg)

        copy_verifier(
            ROOT / "shared" / "verifier",
            task_dir / "tests" / "tempo-bench-verifier",
            case_id,
        )
        sync_rewardkit(task_dir)
        remove_path(task_dir / "tests" / "check.py")
        test_path = task_dir / "tests" / "test.sh"
        copy_file(ROOT / "shared" / "rewardkit" / "test.sh", test_path)
        test_path.chmod(0o755)

        copy_file(
            ROOT / "shared" / "docker" / "main-node" / "Dockerfile",
            task_dir / "environment" / "Dockerfile",
        )
        copy_dir(
            ROOT / "shared" / "rewardkit-package",
            task_dir / "environment" / "rewardkit-package",
        )
        link_dir(
            ROOT / "shared" / "docker" / "tempo-localnet",
            task_dir / "environment" / "tempo-localnet",
        )

        if task_uses_local_tempo_docs(task_dir):
            link_file(
                ROOT / "shared" / "docker" / "compose" / "tempo-localnet-docs.yaml",
                task_dir / "environment" / "docker-compose.yaml",
            )
            link_dir(
                ROOT / "shared" / "docs" / "tempo-docs",
                task_dir / "environment" / "tempo-docs",
            )
        else:
            link_file(
                ROOT / "shared" / "docker" / "compose" / "tempo-localnet.yaml",
                task_dir / "environment" / "docker-compose.yaml",
            )

        assert_compose_build_contexts(task_dir)

    mpp_task_count = sync_mpp_tasks()
    print(
        "Synced verifier and linked localnet assets into "
        f"{len(tasks)} task(s); synced MPP harness into {mpp_task_count} task(s).",
    )


if __name__ == "__main__":
    main()
