"""Harbor-compatible task file collection and content hashing."""

import hashlib
from pathlib import Path

import pathspec

DEFAULT_IGNORES = (
    "__pycache__/",
    "*.pyc",
    ".DS_Store",
    "*.swp",
    "*.swo",
    "*~",
)


def collect_files(task_dir: Path) -> list[Path]:
    """Return Harbor's publishable files in Harbor's stable order."""
    task_dir = task_dir.resolve()
    files = [
        path
        for path in (
            task_dir / "task.toml",
            task_dir / "instruction.md",
            task_dir / "README.md",
        )
        if path.exists()
    ]
    for relative in ("environment", "tests", "solution", "steps"):
        directory = task_dir / relative
        if directory.exists():
            files.extend(path for path in directory.rglob("*") if path.is_file())

    gitignore = task_dir / ".gitignore"
    patterns = (
        gitignore.read_text().splitlines() if gitignore.exists() else DEFAULT_IGNORES
    )
    ignores = pathspec.PathSpec.from_lines("gitignore", patterns)
    files = [
        path
        for path in files
        if not ignores.match_file(path.relative_to(task_dir).as_posix())
    ]
    return sorted(files, key=lambda path: path.relative_to(task_dir).as_posix())


def file_hash(path: Path) -> str:
    """Return the lowercase SHA-256 for the exact bytes in ``path``."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_hash(task_dir: Path) -> str:
    """Compute the same content hash as Harbor's package builder."""
    task_dir = task_dir.resolve()
    digest = hashlib.sha256()
    for path in collect_files(task_dir):
        relative_path = path.relative_to(task_dir).as_posix()
        digest.update(f"{relative_path}\0{file_hash(path)}\n".encode())
    return digest.hexdigest()
