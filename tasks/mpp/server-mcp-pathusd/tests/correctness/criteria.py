import rewardkit as rk
from tempo_bench_rewardkit.common.constants import (
    ScorePath,
    SourcePattern,
    WorkspaceFile,
)

rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.BUILD_SCRIPT)
rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.SERVE_SCRIPT)
rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.MCP_SDK_DEPENDENCY)
rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.MPPX_DEPENDENCY)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.MPPX_IMPORT)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.MPPX_MCP_IMPORT)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.MPPX_CREATE)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.MPPX_CHARGE)
rk.file_contains_regex(WorkspaceFile.OUT_JSON, SourcePattern.MCP_URL_KEY)
rk.file_contains_regex(WorkspaceFile.OUT_JSON, SourcePattern.FREE_TOOL_KEY)
rk.file_contains_regex(WorkspaceFile.OUT_JSON, SourcePattern.PAID_TOOL_KEY)
rk.file_exists(WorkspaceFile.SCORES_JSON)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, ScorePath.REWARD, 1)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "free.hasContent", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "unpaid.paymentRequired", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "unpaid.code", -32042)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "unpaid.method", "tempo")
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "unpaid.intent", "charge")
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "paid.hasContent", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "paid.hasReceipt", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "paid.receipt.method", "tempo")
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "paid.receipt.status", "success")
