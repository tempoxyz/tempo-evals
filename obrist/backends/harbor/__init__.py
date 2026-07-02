"""Harbor backend entry points for compiling Obrist collections.

The public surface is intentionally small: callers use `compile_collection` to
emit a generated Harbor workspace, while Harbor-specific templates and shelling
remain contained inside this package.
"""

from obrist.backends.harbor.emit import compile_collection

__all__ = ["compile_collection"]
