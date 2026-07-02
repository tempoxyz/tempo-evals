from pathlib import Path

PROTECTED_OUTPUT_DIRS = (
    Path("obrist"),
    Path("datasets"),
    Path("tasks"),
    Path("shared"),
)


def _is_relative_to(path: Path, candidate_parent: Path) -> bool:
    try:
        path.relative_to(candidate_parent)
        return True
    except ValueError:
        return False


def assert_allowed_output_path(out: Path, repo_root: Path) -> None:
    """Raise if a generated output directory would overwrite protected source paths."""

    resolved = out.resolve()
    root = repo_root.resolve()
    for protected in PROTECTED_OUTPUT_DIRS:
        protected_path = (root / protected).resolve()
        if resolved == protected_path or _is_relative_to(resolved, protected_path):
            raise ValueError(f"Refusing to write generated output under protected source path: {out}")
