"""Tempo MCP suite declarations."""

from evalkit.compiler.build import ROOT
from evalkit.suites.legacy import suite_from_directory

SUITE = suite_from_directory("tempo-mcp-v1", ROOT / "tasks" / "tempo-mcp-v1")
