import rewardkit as rk
from tempo_bench_rewardkit.common.constants import (
    HttpStatus,
    ScorePath,
    SourcePattern,
    WorkspaceFile,
)

rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.BUILD_SCRIPT)
rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.RUN_SCRIPT)
rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.MPPX_DEPENDENCY)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.MPPX_CLIENT_IMPORT)
rk.file_contains_regex(WorkspaceFile.OUT_JSON, SourcePattern.PAID_URL_KEY)
rk.file_contains_regex(WorkspaceFile.OUT_JSON, SourcePattern.STATUS_KEY)
rk.file_contains_regex(WorkspaceFile.OUT_JSON, SourcePattern.HAS_RECEIPT_KEY)
rk.file_exists(WorkspaceFile.SCORES_JSON)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, ScorePath.REWARD, 1)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "client.status", HttpStatus.OK)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "client.json", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "client.hasReceipt", True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "client.receiptMethod", "tempo")
rk.json_path_equals(WorkspaceFile.SCORES_JSON, "client.receiptStatus", "success")
