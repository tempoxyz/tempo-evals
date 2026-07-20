import rewardkit as rk
from stable_bench_rewardkit.common.checks import register_mpp_result
from stable_bench_rewardkit.common.constants import SourcePattern, WorkspaceFile

register_mpp_result()
rk.file_contains_regex(WorkspaceFile.PACKAGE_JSON, SourcePattern.HONO_DEPENDENCY)
rk.file_contains_regex(WorkspaceFile.SOURCE_INDEX, SourcePattern.MPPX_HONO_IMPORT)
