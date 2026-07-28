"""MPP suite declarations."""

from evalkit.api import Policy, Suite
from evalkit.compiler.build import ROOT
from evalkit.suites.canonical import mpp_task
from evalkit.suites.legacy import suite_from_directory

LEGACY = suite_from_directory("mpp", ROOT / "tasks" / "mpp")
SUITE = Suite(
    LEGACY.name,
    tuple(mpp_task(task) for task in LEGACY.tasks),
    dataset_source=LEGACY.dataset_source,
    policy=Policy(require_image_locks=False),
)
