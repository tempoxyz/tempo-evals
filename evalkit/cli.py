"""Command-line interface for authoring and compiling evalkit suites."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

from evalkit.compiler import build, check, diff, load_suite, suite_names
from evalkit.compiler.build import LOCK_PATH, ROOT, lower_suite, validate
from evalkit.lock import update as update_lock


def _suite_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach shared optional-suite and output-root arguments to a subcommand."""
    parser.add_argument("suite", nargs="*", choices=suite_names())
    parser.add_argument("--output-root", type=Path, default=Path("generated"))


def _print_differences(differences: dict[str, list[str]]) -> None:
    """Print only changed paths, preserving an explicit clean-output message."""
    changed = False
    for task, paths in differences.items():
        if paths:
            changed = True
            print(f"{task}: {', '.join(paths)}")
    if not changed:
        print("No task-definition differences.")


def _new_task(target: str) -> None:
    """Write a minimal declaration module without replacing an existing file."""
    suite, separator, slug = target.partition("/")
    parts = PurePosixPath(target).parts
    if (
        not separator
        or not suite
        or not slug
        or len(parts) != 2
        or any(part in {".", ".."} for part in parts)
        or any(not part.replace("-", "_").isidentifier() for part in parts)
    ):
        raise ValueError("Task target must be suite/name")
    module = (
        ROOT
        / "evalkit"
        / "suites"
        / f"{suite.replace('-', '_')}_{slug.replace('-', '_')}.py"
    )
    if module.exists():
        raise ValueError(f"Refusing to replace existing declaration: {module}")
    module.write_text(
        f'from evalkit.api import Task\n\n\nTASK = Task(name="{suite}/{slug}")\n'
    )
    print(module)


def main() -> None:
    """Parse CLI arguments and dispatch the requested authoring operation."""
    parser = argparse.ArgumentParser(prog="evalkit")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "check", "lint", "diff"):
        _suite_arguments(commands.add_parser(name))
    new = commands.add_parser("new")
    new.add_argument("target")
    lock = commands.add_parser("lock")
    lock.add_argument("--update", metavar="IMAGE")
    lock.add_argument("--digest")
    lock.add_argument("--path", type=Path, default=LOCK_PATH)
    explain = commands.add_parser("explain")
    explain.add_argument("path", type=Path)
    args = parser.parse_args()

    if args.command == "new":
        _new_task(args.target)
        return
    if args.command == "lock":
        if not args.update:
            parser.error("lock requires --update image=NAME:TAG")
        prefix = "image="
        if not args.update.startswith(prefix):
            parser.error("--update must use image=NAME:TAG")
        print(update_lock(args.path, args.update.removeprefix(prefix), args.digest))
        return
    if args.command == "explain":
        manifest = args.path / ".evalkit-manifest.json"
        if not manifest.is_file():
            parser.error(f"No evalkit manifest at {manifest}")
        print(json.dumps(json.loads(manifest.read_text()), indent=2, sort_keys=True))
        return

    for suite_name in args.suite or suite_names():
        if args.command == "build":
            for path in build(suite_name, args.output_root):
                print(path)
        elif args.command == "lint":
            validate(load_suite(suite_name))
            lower_suite(load_suite(suite_name))
            print(f"{suite_name}: valid")
        else:
            differences = (
                diff(suite_name, args.output_root)
                if args.command == "diff"
                else check(suite_name, args.output_root)
            )
            _print_differences(differences)


if __name__ == "__main__":
    main()
