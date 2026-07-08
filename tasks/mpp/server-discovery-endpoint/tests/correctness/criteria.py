import json

import rewardkit as rk
from tempo_bench_rewardkit.common.constants import (
    WORKSPACE_PATH,
    HttpStatus,
    OutKey,
    ScorePath,
    SourcePattern,
    WorkspaceFile,
)

OUT_PATH = WORKSPACE_PATH / WorkspaceFile.OUT_JSON


# Shared checks stay local so each Harbor task is self-contained.
def check_common_project() -> None:
    rk.file_exists(WorkspaceFile.PACKAGE_JSON)
    rk.file_exists(WorkspaceFile.TSCONFIG_JSON)
    rk.file_exists(WorkspaceFile.SOURCE_INDEX)
    rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.BUILD_SCRIPT)
    rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.SERVE_SCRIPT)
    rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.MPPX_DEPENDENCY)
    rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.MPPX_IMPORT)
    rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.MPPX_CREATE)
    rk.file_exists(WorkspaceFile.OUT_JSON)
    rk.file_exists(WorkspaceFile.SCORES_JSON)
    rk.json_path_equals(WorkspaceFile.SCORES_JSON, ScorePath.REWARD, 1)


def check_paid_score(path_prefix: str = "paid") -> None:
    rk.json_path_equals(
        WorkspaceFile.SCORES_JSON, f"{path_prefix}.status", HttpStatus.OK
    )
    rk.json_path_equals(WorkspaceFile.SCORES_JSON, f"{path_prefix}.json", True)
    rk.json_path_equals(WorkspaceFile.SCORES_JSON, f"{path_prefix}.hasReceipt", True)
    rk.json_path_equals(
        WorkspaceFile.SCORES_JSON, f"{path_prefix}.receipt.methodIsTempo", True
    )
    rk.json_path_equals(
        WorkspaceFile.SCORES_JSON, f"{path_prefix}.receipt.statusIsSuccess", True
    )
    rk.json_path_equals(
        WorkspaceFile.SCORES_JSON,
        f"{path_prefix}.receipt.referenceMatchesTransaction",
        True,
    )


def check_out_urls(keys: list[OutKey]) -> None:
    if not OUT_PATH.exists():
        return
    try:
        out = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except ValueError:
        return
    for key in keys:
        value = out.get(key)
        if isinstance(value, str):
            rk.http_status_equals(
                value,
                HttpStatus.OK
                if key == OutKey.FREE_URL
                else HttpStatus.PAYMENT_REQUIRED,
            )


# Common project and verifier score contract.
check_common_project()

# Task-specific source and URL contract checks.
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.MPPX_CHARGE)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.DISCOVERY_IMPORT)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.DISCOVERY)
rk.file_contains_regex(WorkspaceFile.OUT_JSON, SourcePattern.PAID_URL_KEY)
rk.file_contains_regex(WorkspaceFile.OUT_JSON, SourcePattern.OPENAPI_URL_KEY)
check_out_urls([OutKey.PAID_URL])

# Verifier-observed payment behavior.
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "discovery.status", HttpStatus.OK)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "discovery.openapi", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "discovery.hasPaidPath", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "discovery.hasPaymentInfo", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "discovery.mentionsTempo", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "discovery.mentionsCharge", True)
check_paid_score()
