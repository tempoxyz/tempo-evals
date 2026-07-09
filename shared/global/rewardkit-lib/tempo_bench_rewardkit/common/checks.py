# Baked into the tempo-bench base image as part of the tempo-bench-rewardkit
# package.
from dataclasses import dataclass

import rewardkit as rk

import tempo_bench_rewardkit  # noqa: F401
from tempo_bench_rewardkit.common.constants import (
    DEFAULT_TOKEN_EFFICIENCY_THRESHOLDS,
    SourcePattern,
    TokenEfficiencyThreshold,
    WorkspaceFile,
)


@dataclass(frozen=True)
class TokenEfficiencyConfig:
    thresholds: tuple[TokenEfficiencyThreshold, ...] = (
        DEFAULT_TOKEN_EFFICIENCY_THRESHOLDS
    )
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
