"""Generic materialization of ephemeral inputs declared by compiled tasks."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import tomlkit

from evalkit.compiler.build import MANIFEST, ROOT

CA_FILE = "ca.crt"
CA_DESTINATION = "/usr/local/share/ca-certificates/stable-bench-docs.crt"
TLS_VALIDITY_DAYS = "30"


def _run_openssl(args: list[str]) -> None:
    result = subprocess.run(
        ["openssl", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"openssl {' '.join(args)} failed: {output}")


def generate_docs_tls_assets(tls_dir: Path, hostname: str) -> None:
    """Create an ephemeral CA and leaf certificate for one staged task."""
    shutil.rmtree(tls_dir, ignore_errors=True)
    tls_dir.mkdir(parents=True)
    ca_key = tls_dir / "ca.key"
    ca_cert = tls_dir / CA_FILE
    leaf_csr = tls_dir / "docs.csr"
    extensions = tls_dir / "docs.ext"

    _run_openssl(
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
            TLS_VALIDITY_DAYS,
            "-subj",
            "/CN=Stable Bench Ephemeral Docs CA",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
        ]
    )
    _run_openssl(
        [
            "req",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(tls_dir / "docs.key"),
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
    _run_openssl(
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
            str(tls_dir / "docs.crt"),
            "-days",
            TLS_VALIDITY_DAYS,
            "-extfile",
            str(extensions),
        ]
    )
    ca_key.unlink()
    leaf_csr.unlink()
    extensions.unlink()
    (tls_dir / "ca.srl").unlink(missing_ok=True)


def _trust_docs_ca(environment_dir: Path, tls_dir: Path) -> None:
    dockerfile = environment_dir / "Dockerfile"
    ca_path = tls_dir.relative_to(environment_dir) / CA_FILE
    dockerignore = environment_dir / ".dockerignore"
    ignore_entry = f"{tls_dir.name}/*\n!{tls_dir.name}/{CA_FILE}\n"
    existing_ignore = dockerignore.read_text() if dockerignore.exists() else ""
    if existing_ignore and not existing_ignore.endswith("\n"):
        existing_ignore = f"{existing_ignore}\n"
    content = dockerfile.read_text().rstrip()
    dockerfile.write_text(
        f"{content}\n\n"
        f"COPY {ca_path.as_posix()} {CA_DESTINATION}\n"
        "RUN update-ca-certificates\n"
        f"ENV NODE_EXTRA_CA_CERTS={CA_DESTINATION}\n"
    )
    dockerignore.write_text(f"{existing_ignore}{ignore_entry}")


def _materialize_docs(
    task_dir: Path,
    recipe: Mapping[str, str],
    bundle: Path,
    repository_root: Path,
) -> None:
    task_config_path = task_dir / "task.toml"
    config = tomlkit.parse(task_config_path.read_text())
    artifacts = config.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError(f"Missing artifacts array in staged task: {task_dir}")
    access_log = tomlkit.inline_table()
    access_log["source"] = recipe["access_log_source"]
    access_log["service"] = recipe["service"]
    artifacts.append(access_log)
    task_config_path.write_text(tomlkit.dumps(config))

    environment_dir = task_dir / "environment"
    shutil.copyfile(
        repository_root / recipe["compose_source"],
        environment_dir / "docker-compose.yaml",
    )
    shutil.copytree(
        repository_root / recipe["proxy_source"],
        environment_dir / "docs-proxy",
        dirs_exist_ok=True,
    )
    bundle_destination = task_dir / recipe["bundle_destination"]
    shutil.copytree(bundle, bundle_destination, dirs_exist_ok=True)
    tls_dir = task_dir / recipe["tls_destination"]
    generate_docs_tls_assets(tls_dir, recipe["hostname"])
    _trust_docs_ca(environment_dir, tls_dir)


def _override_images(
    task_dir: Path,
    declared: Mapping[str, str],
    images: Mapping[str, str],
) -> None:
    directories = {"agent": "environment", "verifier": "tests"}
    for role, replacement in images.items():
        expected = declared.get(role)
        if expected is None:
            continue
        dockerfile = task_dir / directories[role] / "Dockerfile"
        content = dockerfile.read_text()
        marker = f"FROM {expected}"
        if marker not in content:
            raise RuntimeError(f"Unexpected {role} image in {dockerfile}")
        dockerfile.write_text(content.replace(marker, f"FROM {replacement}", 1))


def materialize_task_tree(
    tasks_root: Path,
    *,
    bundles: Mapping[str, Path] | None = None,
    images: Mapping[str, str] | None = None,
    repository_root: Path = ROOT,
) -> None:
    """Materialize declared runtime inputs into a copied canonical task tree."""
    bundle_inputs = bundles or {}
    image_inputs = images or {}
    manifests = sorted(tasks_root.glob(f"*/*/{MANIFEST}"))
    if not manifests:
        raise RuntimeError(f"No compiled EvalKit tasks found under {tasks_root}")
    for manifest_path in manifests:
        task_dir = manifest_path.parent
        manifest: dict[str, Any] = json.loads(manifest_path.read_text())
        runtime = manifest.get("runtime", {})
        if image_inputs:
            _override_images(task_dir, runtime.get("images", {}), image_inputs)
        docs = runtime.get("docs")
        if docs is not None and docs["input"] in bundle_inputs:
            _materialize_docs(
                task_dir,
                docs,
                bundle_inputs[docs["input"]],
                repository_root,
            )
