"""Compiler utilities shared by Obrist backend emitters.

This package exposes generated-file header helpers and output path guards used
while converting source benchmark packages into generated Harbor workspaces.
"""

from obrist.compiler.headers import add_generated_header, supports_generated_header
from obrist.compiler.paths import assert_allowed_output_path

__all__ = ["add_generated_header", "assert_allowed_output_path", "supports_generated_header"]
