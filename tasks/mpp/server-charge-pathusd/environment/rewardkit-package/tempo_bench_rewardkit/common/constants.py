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


class OutKey(StrEnum):
    """Keys in the task-authored /app/out.json endpoint contract."""

    FREE_URL = "freeUrl"
    PAID_URL = "paidUrl"
    CHARGE_URL = "chargeUrl"
    SESSION_URL = "sessionUrl"
    OPENAPI_URL = "openapiUrl"
    MPP_PAID_URL = "mppPaidUrl"
    X402_PAID_URL = "x402PaidUrl"


class ScorePath(StrEnum):
    """JSON paths in verifier-authored scores.json."""

    REWARD = "reward"


class HttpStatus(IntEnum):
    """HTTP statuses asserted by MPP verifier criteria."""

    OK = 200
    PAYMENT_REQUIRED = 402


class SourcePattern(StrEnum):
    """Regex patterns for lightweight source and contract checks."""

    BUILD_SCRIPT = r'"build"\s*:'
    SERVE_SCRIPT = r'"serve"\s*:'
    HONO_DEPENDENCY = r'"hono"\s*:'
    MPPX_DEPENDENCY = r'"mppx"\s*:'
    MPPX_IMPORT = r'from\s+["\']mppx'
    MPPX_HONO_IMPORT = r'from\s+["\']mppx/hono["\']'
    MPPX_CREATE = r"Mppx\.create\s*\("
    MPPX_CHARGE = r"mppx\.charge\s*\("
    MPPX_SESSION = r"mppx\.session\s*\("
    TEMPO_SESSION = r"tempo\.session\s*\("
    DISCOVERY_IMPORT = r'from\s+["\']mppx/(?:hono|discovery)["\']'
    DISCOVERY = r"\b(?:discovery|generate)\s*\("
    X402 = r"x402|evm\.charge"
    USDC = r"usdc|USDC|0x20C000000000000000000000b9537d11c60E8b50"
    FREE = r"free"
    PAID = r"paid"
    FREE_URL_KEY = r'"freeUrl"\s*:'
    PAID_URL_KEY = r'"paidUrl"\s*:'
    CHARGE_URL_KEY = r'"chargeUrl"\s*:'
    SESSION_URL_KEY = r'"sessionUrl"\s*:'
    OPENAPI_URL_KEY = r'"openapiUrl"\s*:'
    MPP_PAID_URL_KEY = r'"mppPaidUrl"\s*:'
    X402_PAID_URL_KEY = r'"x402PaidUrl"\s*:'
