# SYNCED FROM shared/global/rewardkit-package/tempo_bench_rewardkit/common/checks.py
# BY npm run sync. DO NOT EDIT COPIES IN tasks/.
from dataclasses import dataclass

import rewardkit as rk

import tempo_bench_rewardkit  # noqa: F401
from tempo_bench_rewardkit.common.constants import SourcePattern, WorkspaceFile

type TokenThreshold = tuple[int | str, float]


@dataclass(frozen=True)
class TokenEfficiencyConfig:
    thresholds: list[TokenThreshold]
    thresholds_env: str = "TEMPO_BENCH_TOKENS_SCORE_CUTOFFS"
    weight: float = 1.0


def register_tempo_eval_contract() -> None:
    rk.file_contains_regex(
        WorkspaceFile.PACKAGE_JSON,
        SourcePattern.EVAL_SCRIPT,
        name="package_has_eval_script",
    )
    rk.file_contains_regex(
        WorkspaceFile.SOURCE_INDEX,
        r"process\.env",
        name="source_uses_environment_variables",
    )


def register_source_patterns(patterns: list[dict]) -> None:
    for pattern in patterns:
        rk.file_contains_regex(
            str(pattern.get("file", WorkspaceFile.SOURCE_INDEX)),
            str(pattern["pattern"]),
            name=str(pattern["name"]),
        )


def register_token_efficiency_check(config: TokenEfficiencyConfig) -> None:
    rk.agent_token_efficiency(
        cutoffs_env=config.thresholds_env,
        default_cutoffs=config.thresholds,
        weight=config.weight,
    )
