import os
from enum import IntEnum, StrEnum
from pathlib import Path

WORKSPACE_PATH = Path(os.environ.get("TEMPO_BENCH_WORKSPACE", "/app"))


class WorkspaceFile(StrEnum):
    """Workspace-relative files used by shared RewardKit checks."""

    PACKAGE_JSON = "package.json"
    TSCONFIG_JSON = "tsconfig.json"
    SOURCE_INDEX = "src/index.ts"
    OUT_JSON = "out.json"
    SCORES_JSON = "scores.json"


class HttpStatus(IntEnum):
    """HTTP statuses asserted by MPP verifier criteria."""

    OK = 200
    PAYMENT_REQUIRED = 402


class SourcePattern(StrEnum):
    """Regex patterns for lightweight source and contract checks."""

    BUILD_SCRIPT = r'"build"\s*:'
    SERVE_SCRIPT = r'"serve"\s*:'
    MPPX_DEPENDENCY = r'"mppx"\s*:'
    MPPX_IMPORT = r'from\s+["\']mppx'
    MPPX_CREATE = r"Mppx\.create\s*\("
    MPPX_CHARGE = r"mppx\.charge\s*\("
    FREE = r"free"
    PAID = r"paid"
    FREE_URL_KEY = r'"freeUrl"\s*:'
    PAID_URL_KEY = r'"paidUrl"\s*:'
