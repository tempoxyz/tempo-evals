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


class ScorePath(StrEnum):
    """JSON paths in verifier-authored scores.json."""

    REWARD = "reward"
    PAID_STATUS = "paid.status"
    PAID_JSON = "paid.json"
    PAID_HAS_RECEIPT = "paid.hasReceipt"
    PAID_RECEIPT_METHOD = "paid.receipt.method"
    PAID_RECEIPT_STATUS = "paid.receipt.status"
    PAID_RECEIPT_HAS_TIMESTAMP = "paid.receipt.hasTimestamp"
    PAID_RECEIPT_HAS_REFERENCE = "paid.receipt.hasReference"
    PAID_RECEIPT_EXTERNAL_ID = "paid.receipt.externalId"
    PAID_RECEIPT_EXTRA = "paid.receipt.extra"
    PAID_RECEIPT_METHOD_IS_TEMPO = "paid.receipt.methodIsTempo"
    PAID_RECEIPT_STATUS_IS_SUCCESS = "paid.receipt.statusIsSuccess"
    PAID_RECEIPT_REFERENCE_MATCHES_TRANSACTION = (
        "paid.receipt.referenceMatchesTransaction"
    )
    PAID_TRANSACTION_CHAIN_ID = "paid.transaction.chainId"
    PAID_TRANSACTION_CALL_TO = "paid.transaction.callTo"
    PAID_TRANSACTION_CALL_TO_MATCHES_TOKEN = "paid.transaction.callToMatchesToken"
    PAID_TRANSACTION_CHAIN_MATCHES = "paid.transaction.chainMatches"
    PAID_TRANSACTION_CONFIRMED = "paid.transaction.confirmed"
    PAID_TRANSACTION_FEE_TOKEN = "paid.transaction.feeToken"
    PAID_TRANSACTION_FEE_TOKEN_MATCHES = "paid.transaction.feeTokenMatches"
    PAID_TRANSACTION_FROM = "paid.transaction.from"
    PAID_TRANSACTION_FROM_MATCHES_PAYER = "paid.transaction.fromMatchesPayer"
    PAID_TRANSACTION_HAS_LOGS = "paid.transaction.hasLogs"
    PAID_TRANSACTION_RECEIPT_FEE_TOKEN = "paid.transaction.receiptFeeToken"
    PAID_TRANSACTION_RECEIPT_FEE_TOKEN_MATCHES = (
        "paid.transaction.receiptFeeTokenMatches"
    )
    PAID_TRANSACTION_RECEIPT_STATUS = "paid.transaction.receiptStatus"
    PAID_TRANSACTION_RECEIPT_STATUS_IS_SUCCESS = (
        "paid.transaction.receiptStatusIsSuccess"
    )
    PAID_TRANSACTION_RECEIPT_TO = "paid.transaction.receiptTo"
    PAID_TRANSACTION_RECEIPT_TO_MATCHES_TOKEN = "paid.transaction.receiptToMatchesToken"
    PAID_TRANSACTION_RECEIPT_TRANSACTION_HASH_MATCHES_REFERENCE = (
        "paid.transaction.receiptTransactionHashMatchesReference"
    )
    PAID_TRANSACTION_REFERENCE_MATCHES_HASH = "paid.transaction.referenceMatchesHash"
    PAID_TRANSACTION_SUCCESSFUL = "paid.transaction.successful"
    PAID_TRANSACTION_TRANSFER_AMOUNT = "paid.transaction.transfer.amount"
    PAID_TRANSACTION_TRANSFER_AMOUNT_MATCHES_CHARGE = (
        "paid.transaction.transfer.amountMatchesCharge"
    )
    PAID_TRANSACTION_TRANSFER_FOUND = "paid.transaction.transfer.found"
    PAID_TRANSACTION_TRANSFER_FROM_MATCHES_PAYER = (
        "paid.transaction.transfer.fromMatchesPayer"
    )
    PAID_TRANSACTION_TRANSFER_TO_MATCHES_RECIPIENT = (
        "paid.transaction.transfer.toMatchesRecipient"
    )
    PAID_TRANSACTION_TRANSFER_TOKEN = "paid.transaction.transfer.token"
    PAID_TRANSACTION_TRANSFER_TOKEN_MATCHES = "paid.transaction.transfer.tokenMatches"


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
