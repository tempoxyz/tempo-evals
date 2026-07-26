"""Typed declaration for the exact-parity representative Tempo task."""

from evalkit.api import Task
from evalkit.compiler.build import ROOT

TASK = Task(
    name="tempo-v1/faucet-funded-transfer",
    source=ROOT / "tasks" / "tempo-v1" / "faucet-funded-transfer",
)
