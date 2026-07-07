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

out_path = WORKSPACE_PATH / WorkspaceFile.OUT_JSON

# Expected /app/out.json:
# {"freeUrl":"http://127.0.0.1:3000/free","paidUrl":"http://127.0.0.1:3000/paid"}

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
    free_url = out.get(OutKey.FREE_URL)
    paid_url = out.get(OutKey.PAID_URL)
    if isinstance(free_url, str):
        rk.http_status_equals(free_url, HttpStatus.OK)
        rk.http_response_contains(free_url, "{")
    if isinstance(paid_url, str):
        rk.http_status_equals(paid_url, HttpStatus.PAYMENT_REQUIRED)

# Check MPP Results
rk.file_exists(WorkspaceFile.SCORES_JSON)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, ScorePath.REWARD, 1)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, ScorePath.PAID_STATUS, HttpStatus.OK)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, ScorePath.PAID_JSON, True)
rk.json_path_equals(WorkspaceFile.SCORES_JSON, ScorePath.PAID_HAS_RECEIPT, True)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_RECEIPT_METHOD_IS_TEMPO,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_RECEIPT_STATUS_IS_SUCCESS,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_RECEIPT_HAS_TIMESTAMP,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_RECEIPT_HAS_REFERENCE,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_RECEIPT_EXTERNAL_ID,
    None,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_RECEIPT_EXTRA,
    None,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_RECEIPT_REFERENCE_MATCHES_TRANSACTION,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_CHAIN_MATCHES,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_CALL_TO_MATCHES_TOKEN,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_CONFIRMED,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_FEE_TOKEN_MATCHES,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_FROM_MATCHES_PAYER,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_HAS_LOGS,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_RECEIPT_FEE_TOKEN_MATCHES,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_RECEIPT_STATUS_IS_SUCCESS,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_RECEIPT_TO_MATCHES_TOKEN,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_RECEIPT_TRANSACTION_HASH_MATCHES_REFERENCE,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_REFERENCE_MATCHES_HASH,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_SUCCESSFUL,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_TRANSFER_AMOUNT_MATCHES_CHARGE,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_TRANSFER_FOUND,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_TRANSFER_FROM_MATCHES_PAYER,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_TRANSFER_TO_MATCHES_RECIPIENT,
    True,
)
rk.json_path_equals(
    WorkspaceFile.SCORES_JSON,
    ScorePath.PAID_TRANSACTION_TRANSFER_TOKEN_MATCHES,
    True,
)
