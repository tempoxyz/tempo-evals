"""Checkout suite declarations."""

from evalkit.compiler.build import ROOT
from evalkit.suites.legacy import suite_from_directory

SUITE = suite_from_directory("checkout-v2", ROOT / "tasks" / "checkout-v2")
