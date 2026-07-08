# SYNCED FROM shared/global/rewardkit-package/tempo_bench_rewardkit/common/checks.py
# BY npm run sync. DO NOT EDIT COPIES IN tasks/.
from dataclasses import dataclass

import rewardkit as rk

import tempo_bench_rewardkit  # noqa: F401
from tempo_bench_rewardkit.common.constants import SourcePattern, WorkspaceFile

type TokenThreshold = list[int | float | str]


@dataclass(frozen=True)
class TokenEfficiencyConfig:
    thresholds: str | list[TokenThreshold]
    thresholds_env: str = "TEMPO_BENCH_TOKENS_SCORE_CUTOFFS"
    weight: float = 1.0


def register_tempo_typescript_project() -> None:
    rk.file_exists(WorkspaceFile.PACKAGE_JSON, name="package_json_exists")
    rk.file_exists(WorkspaceFile.TSCONFIG_JSON, name="tsconfig_json_exists")
    rk.file_exists(WorkspaceFile.SOURCE_INDEX, name="src_index_ts_exists")
    rk.file_contains_regex(
        WorkspaceFile.PACKAGE_JSON,
        SourcePattern.BUILD_SCRIPT,
        name="package_has_build_script",
    )
    rk.file_contains_regex(
        WorkspaceFile.PACKAGE_JSON,
        SourcePattern.RUN_SCRIPT,
        name="package_has_run_script",
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
