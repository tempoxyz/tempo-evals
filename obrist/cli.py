import json
from pathlib import Path

import click

from obrist.compiler.models import CompileResult
from obrist.registry import load_collection


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option("0.1.0", prog_name="obrist")
def main() -> None:
    """Compile benchmark collections into Harbor workspaces."""


@main.command(name="compile")
@click.argument("collection")
@click.option("--suite", default=None, help="Suite name to compile. Defaults to the collection default.")
@click.option(
    "--out",
    "out",
    default=Path(".generated/obrist"),
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    show_default=True,
    help="Directory where Obrist writes generated Harbor workspaces.",
)
@click.option("--sync/--no-sync", default=True, show_default=True, help="Run `harbor sync tasks` after emission.")
def compile_command(collection: str, suite: str | None, out: Path, sync: bool) -> None:
    """Compile COLLECTION into a generated Harbor workspace."""

    compiled = _compile(collection=collection, suite=suite, out=out, sync=sync)
    click.echo(json.dumps({"root": str(compiled.root), "manifest": str(compiled.manifest_path)}, indent=2))


def _compile(*, collection: str, suite: str | None, out: Path, sync: bool) -> CompileResult:
    from obrist.backends.harbor.emit import compile_collection

    loaded_collection = load_collection(collection)
    return compile_collection(loaded_collection, suite, out, sync=sync)


if __name__ == "__main__":
    main()
