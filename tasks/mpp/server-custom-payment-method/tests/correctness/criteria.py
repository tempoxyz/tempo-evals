import json

import rewardkit as rk
from tempo_bench_rewardkit.common.constants import (
    WORKSPACE_PATH,
    HttpStatus,
    SourcePattern,
    WorkspaceFile,
)

out_path = WORKSPACE_PATH / WorkspaceFile.OUT_JSON

# App correctness and structure
rk.file_exists(WorkspaceFile.PACKAGE_JSON)
rk.file_exists(WorkspaceFile.TSCONFIG_JSON)
rk.file_exists(WorkspaceFile.SOURCE_INDEX)
rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.BUILD_SCRIPT)
rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.SERVE_SCRIPT)
rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.MPPX_DEPENDENCY)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.MPPX_IMPORT)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.MPPX_CREATE)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.MPPX_CHARGE)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.METHOD_FROM)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.METHOD_TO_SERVER)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.FREE)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.PAID)
rk.file_exists(WorkspaceFile.OUT_JSON)
rk.file_contains_regex(WorkspaceFile.OUT_JSON, SourcePattern.FREE_URL_KEY)
rk.file_contains_regex(WorkspaceFile.OUT_JSON, SourcePattern.PAID_URL_KEY)

if out_path.exists():
    try:
        out = json.loads(out_path.read_text(encoding="utf-8"))
    except ValueError:
        out = {}
    free_url = out.get("freeUrl")
    paid_url = out.get("paidUrl")
    if isinstance(free_url, str):
        rk.http_status_equals(free_url, HttpStatus.OK)
        rk.http_response_contains(free_url, "{")
    if isinstance(paid_url, str):
        rk.http_status_equals(paid_url, HttpStatus.PAYMENT_REQUIRED)

# Check MPP Results
rk.file_exists(WorkspaceFile.SCORES_JSON)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "reward", 1)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON, "offer.status", HttpStatus.PAYMENT_REQUIRED
)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "offer.method", "bench-key")
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "offer.intent", "charge")
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "offer.resource", "paid-json")
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "wrong.rejected", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "paid.status", HttpStatus.OK)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "paid.json", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "paid.hasReceipt", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "paid.receipt.method", "bench-key")
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "paid.receipt.status", "success")
