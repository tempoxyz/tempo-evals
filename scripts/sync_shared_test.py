from __future__ import annotations

import re
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sync_shared


class SyncSharedTest(unittest.TestCase):
    def test_checkout_prompt_pairs_share_every_runtime_and_verifier_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            original_prompts = {}
            for slug in sync_shared.TASKS_CONFIG["checkout"]["directed"]:
                source = sync_shared.CHECKOUT_TASKS_DIR / slug
                shutil.copytree(source, checkout / slug)
                original_prompts[slug] = (source / "instruction.md").read_text()
            with patch.object(sync_shared, "CHECKOUT_TASKS_DIR", checkout):
                sync_shared.sync_checkout_prompt_variants()
                for slug, prompt in sync_shared.TASKS_CONFIG["checkout"][
                    "directed"
                ].items():
                    source = checkout / slug
                    directed_slug = prompt["task"]
                    directed = checkout / directed_slug
                    self.assertEqual(
                        (source / "instruction.md").read_text(), original_prompts[slug]
                    )
                    instruction = (directed / "instruction.md").read_text()
                    self.assertEqual(instruction.count(prompt["instruction"]), 1)

                    # Only the method sentence and unique benchmark marker differ.
                    def strip_marker(text: str) -> str:
                        return re.sub(
                            r"<!-- stable-bench-canary: [0-9a-f-]+ -->", "", text
                        )

                    self.assertEqual(
                        strip_marker(
                            instruction.replace(prompt["instruction"] + "\n", "")
                        ),
                        strip_marker(original_prompts[slug]),
                    )
                    config = tomllib.loads((directed / "task.toml").read_text())
                    original = tomllib.loads((source / "task.toml").read_text())
                    self.assertEqual(
                        config["task"]["name"], f"checkout-v1/{directed_slug}"
                    )
                    self.assertEqual(
                        config["metadata"]["scenario_id"], f"checkout-v1/{slug}"
                    )
                    self.assertEqual(config["metadata"]["prompt_condition"], "directed")
                    self.assertEqual(
                        config["metadata"]["required_method"], prompt["method"]
                    )
                    self.assertEqual(
                        original["metadata"]["prompt_condition"], "discover"
                    )
                    for name in ("agent", "environment", "verifier", "artifacts"):
                        self.assertEqual(config[name], original[name])
                    for part in ("environment", "solution", "tests"):
                        files = {
                            p.relative_to(source)
                            for p in (source / part).rglob("*")
                            if p.is_file() and "__pycache__" not in p.parts
                        }
                        self.assertEqual(
                            files,
                            {
                                p.relative_to(directed)
                                for p in (directed / part).rglob("*")
                                if p.is_file()
                            },
                        )
                        for relative in files:
                            self.assertEqual(
                                (source / relative).read_bytes(),
                                (directed / relative).read_bytes(),
                            )
                before = {
                    p.relative_to(checkout): p.read_bytes()
                    for p in checkout.rglob("*")
                    if p.is_file()
                }
                sync_shared.sync_checkout_prompt_variants()
                self.assertEqual(
                    before,
                    {
                        p.relative_to(checkout): p.read_bytes()
                        for p in checkout.rglob("*")
                        if p.is_file()
                    },
                )

    def test_checkout_grading_copies_only_to_checkout_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / "checkout"
            task = checkout / "merchant"
            task.mkdir(parents=True)
            (task / "task.toml").write_text('[task]\nname = "merchant"\n')
            with patch.object(sync_shared, "CHECKOUT_TASKS_DIR", checkout):
                sync_shared.sync_checkout_grading()
            for relative in (
                "tests/grade.py",
                "tests/observation.py",
                "tests/quality/check.py",
            ):
                self.assertEqual(
                    (task / relative).read_bytes(),
                    (sync_shared.CHECKOUT_SHARED_DIR / relative).read_bytes(),
                )

    def test_checkout_manifest_waits_for_an_authored_task(self) -> None:
        original_tasks_dir = sync_shared.CHECKOUT_TASKS_DIR
        with tempfile.TemporaryDirectory() as temporary_directory:
            tasks_dir = Path(temporary_directory)
            sync_shared.CHECKOUT_TASKS_DIR = tasks_dir
            try:
                sync_shared.write_checkout_dataset_manifest()
                self.assertFalse((tasks_dir / "dataset.toml").exists())

                task_dir = tasks_dir / "merchant-item"
                task_dir.mkdir()
                (task_dir / "task.toml").write_text(
                    '[task]\nname = "checkout-v1/merchant-item"\n'
                )
                sync_shared.write_checkout_dataset_manifest()
                manifest = tomllib.loads((tasks_dir / "dataset.toml").read_text())
                self.assertEqual(manifest["dataset"]["name"], "tempo/checkout-bench-v1")
                self.assertEqual(
                    manifest["tasks"][0]["name"], "checkout-v1/merchant-item"
                )
            finally:
                sync_shared.CHECKOUT_TASKS_DIR = original_tasks_dir

    def test_tempo_tasks_are_discovered_from_authored_directories(self) -> None:
        original_tasks_dir = sync_shared.TASKS_DIR
        with tempfile.TemporaryDirectory() as temporary_directory:
            tasks_dir = Path(temporary_directory)
            for directory, name in (
                ("alpha", "tempo-v1/alpha"),
                ("beta", "tempo-v1/beta"),
                ("_templates/ignored", "tempo-v1/ignored"),
            ):
                task_dir = tasks_dir / directory
                task_dir.mkdir(parents=True)
                (task_dir / "task.toml").write_text(f'[task]\nname = "{name}"\n')

            sync_shared.TASKS_DIR = tasks_dir
            try:
                self.assertEqual(
                    sync_shared.tempo_task_names(),
                    ["tempo-v1/alpha", "tempo-v1/beta"],
                )
            finally:
                sync_shared.TASKS_DIR = original_tasks_dir

    def test_syncs_both_dockerfiles_for_every_suite(self) -> None:
        original_dirs = (
            sync_shared.TASKS_DIR,
            sync_shared.MPP_TASKS_DIR,
            sync_shared.MCP_TASKS_DIR,
            sync_shared.CHECKOUT_TASKS_DIR,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            suite_dirs = tuple(
                root / name for name in ("tempo", "mpp", "mcp", "checkout")
            )
            for suite_dir in suite_dirs:
                task_dir = suite_dir / "example"
                task_dir.mkdir(parents=True)
                (task_dir / "task.toml").write_text('[task]\nname = "example"\n')

            (
                sync_shared.TASKS_DIR,
                sync_shared.MPP_TASKS_DIR,
                sync_shared.MCP_TASKS_DIR,
                sync_shared.CHECKOUT_TASKS_DIR,
            ) = suite_dirs
            try:
                self.assertEqual(sync_shared.sync_task_dockerfiles(), 4)
                for suite_dir in suite_dirs:
                    task_dir = suite_dir / "example"
                    canary = (
                        sync_shared.CHECKOUT_CANARY
                        if suite_dir == sync_shared.CHECKOUT_TASKS_DIR
                        else ""
                    )
                    self.assertEqual(
                        (task_dir / "environment" / "Dockerfile").read_text(),
                        sync_shared.ENVIRONMENT_DOCKERFILE.replace(
                            "FROM ", canary + "FROM ", 1
                        ),
                    )
                    self.assertEqual(
                        (task_dir / "tests" / "Dockerfile").read_text(),
                        sync_shared.VERIFIER_DOCKERFILE.replace(
                            "FROM ", canary + "FROM ", 1
                        ),
                    )
            finally:
                (
                    sync_shared.TASKS_DIR,
                    sync_shared.MPP_TASKS_DIR,
                    sync_shared.MCP_TASKS_DIR,
                    sync_shared.CHECKOUT_TASKS_DIR,
                ) = original_dirs


if __name__ == "__main__":
    unittest.main()
