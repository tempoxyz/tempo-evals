"""Deterministic LOAD → VALIDATE → LOWER → RENDER → HASH → EMIT pipeline."""

from __future__ import annotations

import ast
import filecmp
import hashlib
import importlib
import json
import shutil
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath

import tomlkit

from evalkit.api import Environment, ImageRef, Policy, Suite, Task
from evalkit.harbor_compat import content_hash
from evalkit.ir import (
    Asset,
    Provenance,
    ResolvedImage,
    RuntimeDocsSpec,
    ServiceSpec,
    SourceRef,
    SuiteIR,
    TaskIR,
)
from evalkit.lock import load as load_locks
from evalkit.lock import resolve as resolve_image

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / "evalkit.lock"
MANIFEST = ".evalkit-manifest.json"
SUITE_MODULES = {
    "mpp": "evalkit.suites.mpp",
    "tempo-mcp-v1": "evalkit.suites.tempo_mcp_v1",
    "tempo-v1": "evalkit.suites.tempo_v1",
}


def suite_names() -> tuple[str, ...]:
    """Return registered suite names in stable command-line order."""
    return tuple(sorted(SUITE_MODULES))


def load_suite(name: str) -> Suite:
    """LOAD a registered suite without executing arbitrary user input."""
    try:
        module_name = SUITE_MODULES[name]
    except KeyError as error:
        choices = ", ".join(sorted(SUITE_MODULES))
        raise ValueError(f"Unknown suite {name!r}; choose one of: {choices}") from error
    suite = importlib.import_module(module_name).SUITE
    if not isinstance(suite, Suite):
        raise TypeError(f"{module_name}.SUITE must be an evalkit.api.Suite")
    return suite


def task_slug(task: Task) -> str:
    """Extract the output-directory slug from a suite-qualified task name."""
    prefix, separator, slug = task.name.rpartition("/")
    if not separator or not prefix or not slug:
        raise ValueError(f"Task names must be suite-qualified: {task.name!r}")
    return task.source.name if task.source is not None else slug


def _suite_component(name: str) -> str:
    """Return one safe output-directory component for a suite name."""
    candidate = PurePosixPath(name)
    if candidate.is_absolute() or len(candidate.parts) != 1 or name in {".", ".."}:
        raise ValueError(f"Suite names must be one relative path component: {name!r}")
    return name


def _existing_files(source: Path) -> Iterable[Path]:
    """Yield regular source files in deterministic path order."""
    return (path for path in sorted(source.rglob("*")) if path.is_file())


def _adapter_symbols(path: Path) -> set[str]:
    """Read top-level adapter symbols with AST parsing and without importing code."""
    tree = ast.parse(path.read_text(), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    } | {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }


def _validate_adapter_contract(task: Task) -> None:
    """Reject verifier adapters that do not provide their declared symbols."""
    for use in task.verifiers:
        contract = use.verifier.contract
        if contract is None:
            continue
        adapter = use.adapter or (task.source / contract.path if task.source else None)
        if adapter is None or not adapter.is_file():
            raise ValueError(
                f"{task.name}: missing verifier adapter for {use.verifier.name}"
            )
        missing = set(contract.symbols) - _adapter_symbols(adapter)
        if missing:
            symbols = ", ".join(sorted(missing))
            raise ValueError(f"{task.name}: adapter {adapter} lacks {symbols}")


def _validate_environment(task: Task) -> None:
    """Reject ambiguous service and environment variable declarations."""
    environment = task.environment
    service_names = [service.name for service in environment.services]
    if len(service_names) != len(set(service_names)):
        raise ValueError(f"{task.name}: runtime service names must be unique")
    variable_names = [variable.name for variable in environment.variables]
    if len(variable_names) != len(set(variable_names)):
        raise ValueError(
            f"{task.name}: environment variable declarations must be unique"
        )


def _validate_asset_source(task: Task, source: Path, label: str) -> None:
    """Reject any declared asset whose source does not exist."""
    if not source.exists():
        raise ValueError(f"{task.name}: missing {label} asset {source}")


def _validate_asset_destination(task: Task, destination: PurePosixPath) -> None:
    """Reject output paths that would escape the emitted task directory."""
    if destination.is_absolute() or ".." in destination.parts:
        raise ValueError(
            f"{task.name}: task asset destination must be relative: {destination}"
        )


def _validate_complete_task(task: Task, policy: Policy) -> None:
    """Require runnable Harbor inputs for a fully declared task by default."""
    if task.source is not None or policy.allow_incomplete_tasks:
        return
    missing = []
    if task.instruction is None:
        missing.append("instruction")
    if task.environment.agent is None:
        missing.append("agent environment")
    if task.environment.verifier is None:
        missing.append("verifier environment")
    if not task.verifiers:
        missing.append("verifier")
    if task.solution is None:
        missing.append("solution")
    if missing:
        raise ValueError(
            f"{task.name}: fully declared tasks require {', '.join(missing)}"
        )


def validate(suite: Suite) -> None:
    """VALIDATE task names, source inputs, policies, and adapter contracts."""
    _suite_component(suite.name)
    if not suite.tasks:
        raise ValueError(f"Suite {suite.name!r} has no tasks")
    if suite.dataset_source is not None and not suite.dataset_source.is_file():
        raise ValueError(f"Missing dataset manifest: {suite.dataset_source}")
    names = [name for task in suite.tasks for name in (task.name, *task.aliases)]
    if len(names) != len(set(names)):
        raise ValueError(f"Suite {suite.name!r} has duplicate task names or aliases")
    slugs = [task_slug(task) for task in suite.tasks]
    if len(slugs) != len(set(slugs)):
        raise ValueError(f"Suite {suite.name!r} has duplicate task output slugs")
    for task in suite.tasks:
        for alias in task.aliases:
            task_slug(Task(alias))
        if task.source is not None:
            if not suite.policy.allow_legacy_sources:
                raise ValueError(f"{task.name}: legacy sources are disabled by policy")
            if not task.source.is_dir():
                raise ValueError(f"Missing task source: {task.source}")
            if not (task.source / "task.toml").is_file():
                raise ValueError(f"Missing task.toml: {task.source}")
        for copied in task.copies:
            _validate_asset_source(task, copied.source, "copied")
            _validate_asset_destination(task, copied.destination)
        for build in (task.environment.agent, task.environment.verifier):
            if build is not None:
                for baked in build.assets:
                    _validate_asset_source(task, baked.source, "baked")
                    if baked.into not in {"agent", "verifier"}:
                        raise ValueError(f"{task.name}: invalid bake role {baked.into}")
        for case in task.cases:
            for fixture in case.fixtures:
                _validate_asset_source(task, fixture.source, "fixture")
                _validate_asset_destination(
                    task, PurePosixPath("tests") / "fixtures" / fixture.name
                )
        if task.solution is not None:
            for copied in task.solution.assets:
                _validate_asset_source(task, copied.source, "solution")
                _validate_asset_destination(task, copied.destination)
            if task.solution.entrypoint is not None:
                _validate_asset_destination(task, task.solution.entrypoint)
        for use in task.verifiers:
            _validate_asset_source(task, use.verifier.source, "verifier")
            if use.adapter is not None:
                _validate_asset_source(task, use.adapter, "verifier adapter")
            if use.verifier.contract is not None:
                _validate_asset_destination(task, use.verifier.contract.path)
        if task.instruction is not None:
            _validate_asset_destination(task, task.instruction.destination)
        if docs := task.runtime.docs:
            _validate_asset_source(task, docs.compose_source, "runtime compose")
            _validate_asset_source(task, docs.proxy_source, "runtime proxy")
            _validate_asset_destination(task, docs.bundle_destination)
            _validate_asset_destination(task, docs.tls_destination)
        case_environments = {
            tuple(sorted(case.environment.items())) for case in task.cases
        }
        if len(case_environments) > 1:
            raise ValueError(
                f"{task.name}: cases with different environments require separate tasks"
            )
        _validate_complete_task(task, suite.policy)
        _validate_environment(task)
        _validate_adapter_contract(task)


def _lifecycle(destination: PurePosixPath) -> str:
    """Classify an output path according to the Harbor phase that consumes it."""
    if destination.parts[0] == "environment":
        return "build"
    if destination.parts[0] == "tests":
        return "verifier"
    if destination.parts[0] == "solution":
        return "solution"
    return "runtime"


def _asset(
    path: Path, destination: PurePosixPath, declaration: str, mode: int | None = None
) -> Asset:
    """Convert one source file to an IR asset with inferred lifecycle metadata."""
    return Asset(
        SourceRef(path=path),
        destination,
        _lifecycle(destination),
        Provenance(declaration),
        mode,
    )


def _add_copy(
    assets: list[Asset],
    source: Path,
    destination: PurePosixPath,
    label: str,
    mode: int | None = None,
) -> None:
    """Append one file or recursively append a directory of IR assets."""
    if source.is_file():
        assets.append(_asset(source, destination, label, mode))
        return
    for path in _existing_files(source):
        relative = PurePosixPath(path.relative_to(source).as_posix())
        assets.append(_asset(path, destination / relative, label, mode))


def _merge_assets(task: Task, assets: list[Asset]) -> tuple[Asset, ...]:
    """Sort output assets and require explicit rationale for every collision."""
    allowed_overrides = {entry.destination: entry.reason for entry in task.overrides}
    merged: dict[PurePosixPath, Asset] = {}
    for asset in assets:
        _validate_asset_destination(task, asset.destination)
        previous = merged.get(asset.destination)
        if previous is None:
            merged[asset.destination] = asset
            continue
        reason = allowed_overrides.get(asset.destination)
        if reason is None:
            raise ValueError(
                f"{task.name}: destination collision at {asset.destination}; "
                "use override(..., reason=...)"
            )
        merged[asset.destination] = Asset(
            asset.source,
            asset.destination,
            asset.lifecycle,
            Provenance(asset.provenance.declaration, reason),
            asset.mode,
        )
    return tuple(
        sorted(merged.values(), key=lambda asset: asset.destination.as_posix())
    )


def _environment_values(environment: Environment) -> dict[str, str]:
    """Build the stable union of declared variable names and default values."""
    values: dict[str, str] = {}
    for variable in sorted(environment.variables, key=lambda value: value.name):
        if variable.default is not None:
            values[variable.name] = variable.default
        elif variable.required:
            values[variable.name] = ""
    return values


def _images(
    task: Task, locks: dict[str, str], require_locks: bool
) -> tuple[ResolvedImage, ...]:
    """Resolve all declared build and service images through the suite lock policy."""
    images: list[ImageRef] = []
    if task.environment.agent:
        images.append(task.environment.agent.image)
    if task.environment.verifier:
        images.append(task.environment.verifier.image)
    images.extend(service.image for service in task.environment.services)
    if not images:
        return ()
    if not require_locks:
        return tuple(ResolvedImage(image.reference, "") for image in images)
    return tuple(
        ResolvedImage(image.reference, resolve_image(image, locks)) for image in images
    )


def _services(task: Task) -> tuple[ServiceSpec, ...]:
    """Lower public runtime-service declarations to IR service specifications."""
    return tuple(
        ServiceSpec(
            service.name,
            service.image.reference,
            service.ports,
            service.env,
            service.command,
            service.healthcheck,
            service.depends_on,
        )
        for service in task.environment.services
    )


def _render_environment(
    task: Task, assets: list[Asset], images: tuple[ResolvedImage, ...]
) -> None:
    """Render Docker build contexts and runtime service configuration assets."""
    builds = (
        ("agent", task.environment.agent),
        ("verifier", task.environment.verifier),
    )
    image_digests = {image.reference: image.digest for image in images}
    for role, build in builds:
        if build is None:
            continue
        if (
            task.source is not None
            and not build.assets
            and build.header is None
            and not build.instructions
        ):
            continue
        context = PurePosixPath("environment" if role == "agent" else "tests")
        digest = image_digests[build.image.reference]
        image = f"{build.image.reference}@{digest}" if digest else build.image.reference
        lines = [line for line in (build.header, f"FROM {image}") if line is not None]
        for baked in build.assets:
            if baked.into != role:
                raise ValueError(
                    f"{task.name}: {baked.into} bake cannot be used by {role} build"
                )
            relative_destination = (
                PurePosixPath(*baked.destination.parts[1:])
                if baked.destination.is_absolute()
                else baked.destination
            )
            baked_destination = context / "baked" / role / relative_destination
            _add_copy(
                assets, baked.source, baked_destination, f"bake:{role}", baked.mode
            )
            lines.append(
                f"COPY baked/{role}/{relative_destination} {baked.destination}"
            )
        lines.extend(build.instructions)
        assets.append(
            Asset(
                SourceRef(content=("\n".join(lines) + "\n").encode()),
                context / "Dockerfile",
                "build",
                Provenance(f"docker build:{role}"),
            )
        )
    if not task.environment.services:
        return
    services = {}
    for service in task.environment.services:
        digest = image_digests[service.image.reference]
        service_image = (
            f"{service.image.reference}@{digest}" if digest else service.image.reference
        )
        services[service.name] = {
            "command": list(service.command),
            "depends_on": list(service.depends_on),
            "environment": dict(service.env),
            "healthcheck": service.healthcheck,
            "image": service_image,
            "ports": list(service.ports),
        }
    assets.append(
        Asset(
            SourceRef(
                content=(json.dumps({"services": services}, indent=2) + "\n").encode()
            ),
            PurePosixPath("environment") / "compose.yaml",
            "build",
            Provenance("runtime services"),
        )
    )


def _render_task_toml(task: Task, environment: Mapping[str, str]) -> Asset:
    """Render minimal task metadata when a declaration has no source task TOML."""
    document = tomlkit.document()
    document["schema_version"] = "1.3"
    document["task"] = {"name": task.name}
    for key, value in task.extra_config.items():
        if isinstance(value, Mapping) and isinstance(document.get(key), Mapping):
            document[key].update(
                {
                    item_key: item_value
                    for item_key, item_value in value.items()
                    if not (key == "task" and item_key == "name")
                }
            )
        else:
            document[key] = value
    if environment:
        document.setdefault("environment", tomlkit.table())["env"] = dict(environment)
    return Asset(
        SourceRef(content=tomlkit.dumps(document).encode()),
        PurePosixPath("task.toml"),
        "runtime",
        Provenance("generated task.toml"),
    )


def _apply_environment(
    task: Task, assets: list[Asset], environment: Mapping[str, str]
) -> None:
    """Merge declared values into a source task TOML or create one if necessary."""
    if not environment:
        return
    destination = PurePosixPath("task.toml")
    for index, asset in enumerate(assets):
        if asset.destination != destination:
            continue
        document = tomlkit.parse(asset.source.read_bytes().decode())
        environment_table = document.setdefault("environment", tomlkit.table())
        environment_table["env"] = {
            **dict(environment_table.get("env", {})),
            **environment,
        }
        assets[index] = Asset(
            SourceRef(content=tomlkit.dumps(document).encode()),
            destination,
            "runtime",
            Provenance("environment env union"),
        )
        return
    assets.append(_render_task_toml(task, environment))


def _lower_task(task: Task, locks: dict[str, str], require_locks: bool) -> TaskIR:
    """Lower one validated public declaration into an immutable task IR."""
    environment = _environment_values(task.environment)
    images = _images(task, locks, require_locks)
    assets: list[Asset] = []
    if task.source is not None:
        for source in _existing_files(task.source):
            if source.name == MANIFEST:
                continue
            destination = PurePosixPath(source.relative_to(task.source).as_posix())
            assets.append(_asset(source, destination, "legacy source"))
    for copy in task.copies:
        _add_copy(assets, copy.source, copy.destination, "copy", copy.mode)
    for case in task.cases:
        for fixture in case.fixtures:
            _add_copy(
                assets,
                fixture.source,
                PurePosixPath("tests") / "fixtures" / fixture.name,
                f"fixture:{case.name}",
            )
        environment.update(case.environment)
    if task.instruction is not None:
        assets.append(
            Asset(
                SourceRef(content=task.instruction.content.encode()),
                task.instruction.destination,
                "runtime",
                Provenance("instruction"),
            )
        )
    if task.solution is not None:
        for copy in task.solution.assets:
            _add_copy(
                assets,
                copy.source,
                PurePosixPath("solution") / copy.destination,
                "solution",
            )
        if task.solution.entrypoint is not None:
            entrypoint = next(
                (
                    copy
                    for copy in task.solution.assets
                    if copy.destination == task.solution.entrypoint
                ),
                None,
            )
            if entrypoint is None:
                raise ValueError(
                    f"{task.name}: solution entrypoint must name a solution asset"
                )
            if task.solution.entrypoint != PurePosixPath("solve.sh"):
                _add_copy(
                    assets,
                    entrypoint.source,
                    PurePosixPath("solution") / "solve.sh",
                    "solution entrypoint",
                )
    for use in task.verifiers:
        _add_copy(
            assets,
            use.verifier.source,
            PurePosixPath("tests"),
            f"verifier:{use.verifier.name}",
        )
        if use.adapter is not None:
            contract = use.verifier.contract
            adapter_destination = (
                PurePosixPath("tests") / contract.path
                if contract is not None
                else PurePosixPath("tests") / use.adapter.name
            )
            _add_copy(
                assets,
                use.adapter,
                adapter_destination,
                "adapter",
            )
    _render_environment(task, assets, images)
    _apply_environment(task, assets, environment)
    if not any(asset.destination == PurePosixPath("task.toml") for asset in assets):
        assets.append(_render_task_toml(task, environment))
    builds = {
        role: build.image.reference
        for role, build in (
            ("agent", task.environment.agent),
            ("verifier", task.environment.verifier),
        )
        if build is not None
    }
    runtime_docs = (
        RuntimeDocsSpec(
            docs.input_name,
            docs.compose_source,
            docs.proxy_source,
            docs.bundle_destination,
            docs.tls_destination,
            docs.hostname,
            docs.access_log_source,
            docs.service,
        )
        if (docs := task.runtime.docs) is not None
        else None
    )
    return TaskIR(
        task.name,
        task_slug(task),
        task.aliases,
        _merge_assets(task, assets),
        environment,
        _services(task),
        images,
        builds,
        runtime_docs,
        task.source,
    )


def lower_suite(suite: Suite, lock_path: Path = LOCK_PATH) -> SuiteIR:
    """LOWER validated declarations into immutable compiler IR."""
    validate(suite)
    locks = load_locks(lock_path)
    return SuiteIR(
        suite.name,
        tuple(
            _lower_task(task, locks, suite.policy.require_image_locks)
            for task in suite.tasks
        ),
        suite.dataset_source,
    )


def destination(output_root: Path, suite: SuiteIR, task: TaskIR) -> Path:
    """Return a checked task output path that cannot escape its suite directory."""
    root = output_root.resolve()
    suite_root = (root / _suite_component(suite.name)).resolve()
    path = (suite_root / task.slug).resolve()
    if not path.is_relative_to(root) or not path.is_relative_to(suite_root):
        raise ValueError(f"Task destination escapes output root: {path}")
    return path


def _source_name(asset: Asset) -> str | None:
    """Return a reproducible repository-relative asset source path when possible."""
    if asset.source.path is None:
        return None
    try:
        return asset.source.path.relative_to(ROOT).as_posix()
    except ValueError:
        return asset.source.path.as_posix()


def manifest(task: TaskIR) -> str:
    """Render stable provenance JSON excluded from Harbor content hashes."""
    runtime: dict[str, object] = {"images": dict(task.image_roles)}
    if task.runtime_docs is not None:
        runtime["docs"] = {
            "access_log_source": task.runtime_docs.access_log_source,
            "bundle_destination": task.runtime_docs.bundle_destination.as_posix(),
            "compose_source": _repository_path(task.runtime_docs.compose_source),
            "hostname": task.runtime_docs.hostname,
            "input": task.runtime_docs.input_name,
            "proxy_source": _repository_path(task.runtime_docs.proxy_source),
            "service": task.runtime_docs.service,
            "tls_destination": task.runtime_docs.tls_destination.as_posix(),
        }
    return (
        json.dumps(
            {
                "assets": {
                    asset.destination.as_posix(): {
                        "provenance": asset.provenance.declaration,
                        "override_reason": asset.provenance.override_reason,
                        "sha256": hashlib.sha256(asset.source.read_bytes()).hexdigest(),
                        "source": _source_name(asset),
                    }
                    for asset in task.assets
                },
                "images": {
                    image.reference: image.digest
                    for image in task.resolved_images
                    if image.digest
                },
                "aliases": list(task.aliases),
                "runtime": runtime,
                "task": task.name,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _repository_path(path: Path) -> str:
    """Return a repository-relative path required by runtime materialization."""
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as error:
        raise ValueError(
            f"Runtime source must be inside the repository: {path}"
        ) from error


def _write_asset(asset: Asset, target: Path) -> None:
    """Write an IR asset while preserving source modes or applying declared modes."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if asset.source.path is not None and asset.source.content is None:
        shutil.copy2(asset.source.path, target)
    else:
        target.write_bytes(asset.source.read_bytes())
    if asset.mode is not None:
        target.chmod(asset.mode)


def _materialize_asset(asset: Asset) -> Asset:
    """Read an asset before an in-place build can overwrite its source."""
    mode = asset.mode
    if mode is None and asset.source.path is not None:
        mode = asset.source.path.stat().st_mode & 0o777
    return Asset(
        SourceRef(content=asset.source.read_bytes()),
        asset.destination,
        asset.lifecycle,
        asset.provenance,
        mode,
    )


def _remove_stale_assets(task_destination: Path, expected: set[PurePosixPath]) -> None:
    """Remove files absent from the lowered task before rewriting it in place."""
    for existing in _existing_files(task_destination):
        relative = PurePosixPath(existing.relative_to(task_destination).as_posix())
        if relative not in expected:
            existing.unlink()
    for directory in sorted(
        (path for path in task_destination.rglob("*") if path.is_dir()),
        reverse=True,
    ):
        if not any(directory.iterdir()):
            directory.rmdir()


def _emit_in_place(task: TaskIR, task_destination: Path) -> None:
    """Overwrite one canonical task after materializing all source assets."""
    rendered_manifest = manifest(task)
    assets = tuple(_materialize_asset(asset) for asset in task.assets)
    expected = {asset.destination for asset in assets}
    expected.add(PurePosixPath(MANIFEST))
    _remove_stale_assets(task_destination, expected)
    for asset in assets:
        _write_asset(asset, task_destination / asset.destination)
    (task_destination / MANIFEST).write_text(rendered_manifest)


def _write_dataset(suite: SuiteIR, emitted: list[Path], output_root: Path) -> None:
    """Refresh emitted task digests in the generated Harbor dataset manifest."""
    if suite.dataset_source is None:
        return
    document = tomlkit.parse(suite.dataset_source.read_text())
    entries = document.get("tasks")
    if entries is None:
        entries = tomlkit.aot()
        document["tasks"] = entries
    for task, task_path in zip(suite.tasks, emitted, strict=True):
        entry = next(
            (candidate for candidate in entries if candidate.get("name") == task.name),
            None,
        )
        if entry is None:
            entry = tomlkit.table()
            entry["name"] = task.name
            entries.append(entry)
        entry["digest"] = f"sha256:{content_hash(task_path)}"
    suite_destination = (output_root / suite.name).resolve()
    suite_destination.mkdir(parents=True, exist_ok=True)
    (suite_destination / "dataset.toml").write_text(tomlkit.dumps(document))


def emit(suite: SuiteIR, output_root: Path) -> list[Path]:
    """RENDER, HASH, and EMIT self-contained Harbor task directories."""
    emitted = []
    for task in suite.tasks:
        task_destination = destination(output_root, suite, task)
        in_place = (
            task.source is not None
            and task.source.resolve() == task_destination.resolve()
        )
        if task_destination.exists():
            if in_place:
                _emit_in_place(task, task_destination)
                emitted.append(task_destination)
                continue
            if not (task_destination / MANIFEST).is_file():
                raise ValueError(
                    f"Refusing to replace unmanaged output: {task_destination}"
                )
            shutil.rmtree(task_destination)
        for asset in task.assets:
            _write_asset(asset, task_destination / asset.destination)
        (task_destination / MANIFEST).write_text(manifest(task))
        emitted.append(task_destination)

    _write_dataset(suite, emitted, output_root)
    return emitted


def build(
    name: str,
    output_root: Path = ROOT / "tasks",
    lock_path: Path = LOCK_PATH,
) -> list[Path]:
    """Build a suite into plain Harbor task directories."""
    return emit(lower_suite(load_suite(name), lock_path), output_root)


def task_differences(source: Path, rendered: Path) -> list[str]:
    """List definition paths that differ while ignoring evalkit provenance metadata."""
    comparison = filecmp.dircmp(source, rendered, ignore=[MANIFEST])
    differences = [
        *comparison.left_only,
        *comparison.right_only,
        *comparison.diff_files,
    ]
    for subdirectory in comparison.common_dirs:
        differences.extend(
            f"{subdirectory}/{path}"
            for path in task_differences(source / subdirectory, rendered / subdirectory)
        )
    return sorted(differences)


def _rendered_differences(task: TaskIR, rendered: Path) -> list[str]:
    """Compare fully declared output to the assets currently lowered from it."""
    expected = {
        **{
            asset.destination.as_posix(): asset.source.read_bytes()
            for asset in task.assets
        },
        MANIFEST: manifest(task).encode(),
    }
    actual = {
        path.relative_to(rendered).as_posix(): path.read_bytes()
        for path in _existing_files(rendered)
    }
    differences = set(expected) ^ set(actual)
    differences.update(
        path for path in set(expected) & set(actual) if expected[path] != actual[path]
    )
    return sorted(differences)


def diff(
    name: str,
    output_root: Path = ROOT / "tasks",
    lock_path: Path = LOCK_PATH,
) -> dict[str, list[str]]:
    """Report Harbor-definition diffs between source and rendered output."""
    suite = lower_suite(load_suite(name), lock_path)
    return {
        task.name: (
            _rendered_differences(task, destination(output_root, suite, task))
            if task.source is None
            or task.source.resolve() == destination(output_root, suite, task).resolve()
            else task_differences(task.source, destination(output_root, suite, task))
        )
        for task in suite.tasks
        if destination(output_root, suite, task).is_dir()
    }


def check(
    name: str,
    output_root: Path = ROOT / "tasks",
    lock_path: Path = LOCK_PATH,
) -> dict[str, list[str]]:
    """Validate declarations and fail if generated definitions are stale."""
    suite = lower_suite(load_suite(name), lock_path)
    differences = diff(name, output_root, lock_path)
    missing = [
        task.name
        for task in suite.tasks
        if not destination(output_root, suite, task).is_dir()
    ]
    if missing:
        raise ValueError(f"Missing generated tasks: {', '.join(missing)}")
    changed = {task: paths for task, paths in differences.items() if paths}
    if changed:
        rendered = "; ".join(
            f"{task}: {', '.join(paths)}" for task, paths in changed.items()
        )
        raise ValueError(f"Generated task definitions differ: {rendered}")
    return differences
