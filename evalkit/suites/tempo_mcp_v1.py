"""Tempo MCP suite declarations."""

from evalkit.api import Policy, Suite
from evalkit.compiler.build import ROOT
from evalkit.suites.canonical import tempo_mcp_task
from evalkit.suites.legacy import suite_from_directory

LEGACY = suite_from_directory("tempo-mcp-v1", ROOT / "tasks" / "tempo-mcp-v1")
SUITE = Suite(
    LEGACY.name,
    tuple(tempo_mcp_task(task) for task in LEGACY.tasks),
    dataset_source=LEGACY.dataset_source,
    policy=Policy(require_image_locks=False),
)
