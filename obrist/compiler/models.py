from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CompileResult:
    """Metadata for a compiled Obrist workspace."""

    run_name: str
    root: Path
    manifest_path: Path
    job_config: Path
    dataset: Path
