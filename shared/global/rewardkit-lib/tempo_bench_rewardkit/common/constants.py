# Installed in the verifier image as part of the tempo-bench-rewardkit
# package.
import os
from enum import IntEnum, StrEnum
from pathlib import Path

WORKSPACE_PATH = Path(os.environ.get("TEMPO_BENCH_WORKSPACE", "/app"))

type TokenEfficiencyThreshold = tuple[int | str, float]

DEFAULT_TOKEN_EFFICIENCY_THRESHOLDS: tuple[TokenEfficiencyThreshold, ...] = (
    (250000, 1.0),
    (500000, 0.8),
    (1000000, 0.5),
    (1500000, 0.2),
    ("*", 0.0),
)


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
    MCP_URL = "mcpUrl"
    FREE_TOOL = "freeTool"
    PAID_TOOL = "paidTool"
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
    EVAL_SCRIPT = r'"eval"\s*:'
    RUN_SCRIPT = r'"run"\s*:'
    SERVE_SCRIPT = r'"serve"\s*:'
    MCP_SDK_DEPENDENCY = r'"@modelcontextprotocol/sdk"\s*:'
    HONO_DEPENDENCY = r'"hono"\s*:'
    MPPX_DEPENDENCY = r'"mppx"\s*:'
    MPPX_IMPORT = r'from\s+["\']mppx'
    MPPX_CLIENT_IMPORT = r'from\s+["\']mppx/client["\']'
    MPPX_MCP_IMPORT = r'from\s+["\']mppx/mcp/server["\']'
    MPPX_HONO_IMPORT = r'from\s+["\']mppx/hono["\']'
    METHOD_FROM = r"Method\.from\s*\("
    METHOD_TO_CLIENT = r"Method\.toClient\s*\("
    METHOD_TO_SERVER = r"Method\.toServer\s*\("
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
    STATUS_KEY = r'"status"\s*:'
    HAS_RECEIPT_KEY = r'"hasReceipt"\s*:'
    CHARGE_URL_KEY = r'"chargeUrl"\s*:'
    SESSION_URL_KEY = r'"sessionUrl"\s*:'
    OPENAPI_URL_KEY = r'"openapiUrl"\s*:'
    MPP_PAID_URL_KEY = r'"mppPaidUrl"\s*:'
    MCP_URL_KEY = r'"mcpUrl"\s*:'
    FREE_TOOL_KEY = r'"freeTool"\s*:'
    PAID_TOOL_KEY = r'"paidTool"\s*:'
    X402_PAID_URL_KEY = r'"x402PaidUrl"\s*:'
