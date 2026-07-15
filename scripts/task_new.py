#!/usr/bin/env python3
"""Scaffold a new Tempo Bench task with suite-specific conventions."""

from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path

if __package__:
    from .sync_shared import ENVIRONMENT_DOCKERFILE, VERIFIER_DOCKERFILE
    from .task_lint import ROOT, SUITES, Suite
else:
    from sync_shared import ENVIRONMENT_DOCKERFILE, VERIFIER_DOCKERFILE
    from task_lint import ROOT, SUITES, Suite

SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*$")
SUITES_BY_ID = {
    "tempo": next(suite for suite in SUITES if suite.path == "tasks/tempo-v1"),
    "mpp": next(suite for suite in SUITES if suite.path == "tasks/mpp"),
    "tempo-mcp": next(suite for suite in SUITES if suite.path == "tasks/tempo-mcp-v1"),
}


def title(slug: str) -> str:
    return slug.replace("-", " ").title()


def task_toml(suite_id: str, suite: Suite, slug: str) -> str:
    benchmark = {
        "tempo": "tempo-bench-v1",
        "mpp": "mpp-bench-v1",
        "tempo-mcp": "tempo-mcp-bench-v1",
    }[suite_id]
    artifacts = [json.dumps(artifact) for artifact in suite.artifacts]
    artifacts.extend(
        f"{{ source = {json.dumps(source)}, service = {json.dumps(service)} }}"
        for source, service in suite.sidecar_artifacts
    )
    artifact_toml = "[\n  " + ",\n  ".join(artifacts) + ",\n]"
    return f'''schema_version = "1.3"

artifacts = {artifact_toml}

[task]
name = "{suite.task_name(slug)}"
description = "TODO: describe the capability this task evaluates."
keywords = ["tempo"]

[metadata]
category = "integration"
benchmark = "{benchmark}"

[agent]
timeout_sec = {300 if suite_id == "tempo-mcp" else 900}.0

[verifier]
timeout_sec = {90 if suite_id == "tempo-mcp" else 300}.0
environment_mode = "separate"

[environment]
cpus = {1 if suite_id == "tempo-mcp" else 2}
memory_mb = {1024 if suite_id == "tempo-mcp" else 4096}
storage_mb = {2048 if suite_id == "tempo-mcp" else 10240}
'''


def instruction(suite_id: str, slug: str, canary: str) -> str:
    output = "/app/answer.json" if suite_id == "tempo-mcp" else "/app/out.json"
    return f"""<!-- tempo-bench-canary: {canary} -->
# {title(slug)}

TODO: write the end-user task instruction.

Write the required result to `{output}`.
"""


def readme(suite_id: str, slug: str) -> str:
    return f"""# {title(slug)}

## Overview

TODO: describe what the agent must build.

## What the Task Tests

- TODO: capability under evaluation

## Verification

- TODO: observable behavior checked by the verifier
"""


def files_for(suite_id: str, suite: Suite, slug: str, canary: str) -> dict[str, str]:
    files = {
        "task.toml": task_toml(suite_id, suite, slug),
        "instruction.md": instruction(suite_id, slug, canary),
        "README.md": readme(suite_id, slug),
        "environment/Dockerfile": ENVIRONMENT_DOCKERFILE,
        "solution/solve.sh": (
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            "# TODO: implement the oracle solution.\nexit 1\n"
        ),
        "tests/test.sh": (
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            "# TODO: implement verifier entrypoint.\nexit 1\n"
        ),
        "tests/Dockerfile": VERIFIER_DOCKERFILE,
    }
    if suite_id == "tempo-mcp":
        files["tests/expected.json"] = (
            json.dumps(
                {
                    "required_terms": [],
                    "required_patterns": [],
                    "minimum_sources": 1,
                    "required_data_tools": [],
                },
                indent=2,
            )
            + "\n"
        )
    return files


def create_task(root: Path, suite_id: str, slug: str) -> Path:
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError("task slug must use lowercase letters, digits, and hyphens")
    suite = SUITES_BY_ID[suite_id]
    destination = root / suite.path / slug
    if destination.exists():
        raise FileExistsError(f"task already exists: {destination}")
    canary = str(uuid.uuid4())
    for relative_path, content in files_for(suite_id, suite, slug, canary).items():
        path = destination / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        if path.name == "solve.sh" or path.name == "test.sh":
            path.chmod(0o755)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, choices=sorted(SUITES_BY_ID))
    parser.add_argument("--name", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(create_task(args.root.resolve(), args.suite, args.name))


if __name__ == "__main__":
    main()
