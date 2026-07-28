"""Tests for manifest-driven ephemeral task materialization."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from evalkit.runtime import materialize_task_tree


class RuntimeMaterializationTest(unittest.TestCase):
    def test_materializes_declared_docs_and_image_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            tasks_root = root / "tasks"
            task = tasks_root / "example" / "task"
            environment = task / "environment"
            tests = task / "tests"
            environment.mkdir(parents=True)
            tests.mkdir()
            (task / "task.toml").write_text('artifacts = ["/app/output"]\n')
            (environment / "Dockerfile").write_text("FROM example/agent:v1\n")
            (tests / "Dockerfile").write_text("FROM example/verifier:v1\n")

            compose = repository / "compose.yaml"
            compose.parent.mkdir(parents=True)
            compose.write_text("services:\n  docs:\n    image: docs\n")
            proxy = repository / "proxy"
            proxy.mkdir()
            (proxy / "server.mjs").write_text("export {};\n")
            bundle = root / "bundle"
            bundle.mkdir()
            (bundle / "index.html").write_text("docs\n")
            (task / ".evalkit-manifest.json").write_text(
                json.dumps(
                    {
                        "runtime": {
                            "images": {
                                "agent": "example/agent:v1",
                                "verifier": "example/verifier:v1",
                            },
                            "docs": {
                                "access_log_source": "/logs/docs.log",
                                "bundle_destination": "environment/docs-bundle",
                                "compose_source": "compose.yaml",
                                "hostname": "docs.example",
                                "input": "docs",
                                "proxy_source": "proxy",
                                "service": "docs",
                                "tls_destination": "environment/docs-tls",
                            },
                        }
                    }
                )
            )

            materialize_task_tree(
                tasks_root,
                bundles={"docs": bundle},
                images={
                    "agent": "example/agent@sha256:abc",
                    "verifier": "example/verifier@sha256:def",
                },
                repository_root=repository,
            )

            self.assertIn(
                "FROM example/agent@sha256:abc",
                (environment / "Dockerfile").read_text(),
            )
            self.assertIn('source = "/logs/docs.log"', (task / "task.toml").read_text())
            self.assertTrue((environment / "docs-bundle/index.html").is_file())
            self.assertTrue((environment / "docs-proxy/server.mjs").is_file())
            self.assertEqual(
                (environment / "docker-compose.yaml").read_text(),
                compose.read_text(),
            )
            self.assertTrue((environment / "docs-tls/ca.crt").is_file())
            certificate = subprocess.run(
                [
                    "openssl",
                    "x509",
                    "-in",
                    str(environment / "docs-tls/docs.crt"),
                    "-noout",
                    "-text",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("DNS:docs.example", certificate.stdout)

    def test_requires_compiled_tasks(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(RuntimeError, "No compiled EvalKit tasks"),
        ):
            materialize_task_tree(Path(directory))


if __name__ == "__main__":
    unittest.main()
