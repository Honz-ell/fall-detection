"""Small helpers for command-line behavior across Windows and Unix."""
from __future__ import annotations

import sys


def configure_console() -> None:
    """Use UTF-8 for CLI output so Vietnamese text works in Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
