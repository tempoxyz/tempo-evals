# SYNCED FROM shared/rewardkit-package/tempo_bench_rewardkit/common/checks.py
# BY npm run sync. DO NOT EDIT COPIES IN tasks/.
from dataclasses import dataclass

import rewardkit as rk

import tempo_bench_rewardkit  # noqa: F401

type TokenThreshold = list[int | float | str]


@dataclass(frozen=True)
class TokenEfficiencyConfig:
    thresholds: str | list[TokenThreshold]
    thresholds_env: str = "TEMPO_BENCH_TOKENS_SCORE_CUTOFFS"
    weight: float = 1.0


def format_token_thresholds(thresholds: str | list[TokenThreshold]) -> str:
    if isinstance(thresholds, str):
        return thresholds
    formatted = []
    for threshold in thresholds:
        if len(threshold) != 2:
            raise ValueError(
                "token efficiency thresholds must be [cutoff, score] pairs"
            )
        cutoff, score = threshold
        formatted.append(f"{cutoff}={score}")
    return ",".join(formatted)


def register_token_efficiency_check(config: TokenEfficiencyConfig) -> None:
    rk.agent_token_efficiency(
        cutoffs_env=config.thresholds_env,
        default_cutoffs=format_token_thresholds(config.thresholds),
        weight=config.weight,
    )
