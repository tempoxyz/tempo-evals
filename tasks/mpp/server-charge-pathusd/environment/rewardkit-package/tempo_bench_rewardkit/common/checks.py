from dataclasses import dataclass

import rewardkit as rk

import tempo_bench_rewardkit  # noqa: F401


@dataclass(frozen=True)
class TokenEfficiencyConfig:
    thresholds: str
    thresholds_env: str = "TEMPO_BENCH_TOKENS_SCORE_CUTOFFS"
    weight: float = 1.0


def register_token_efficiency_check(config: TokenEfficiencyConfig) -> None:
    rk.agent_token_efficiency(
        cutoffs_env=config.thresholds_env,
        default_cutoffs=config.thresholds,
        weight=config.weight,
    )
