"""
Ensure Playwright uses a stable browser install path (not ephemeral sandbox caches)
and that stdout/stderr can log Unicode on Windows consoles.
"""

import os
import sys


def _default_browsers_path() -> str:
    local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    return os.path.join(local, "ms-playwright")


def configure_playwright_environment() -> None:
    """Call before any Playwright import or browser launch."""
    if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _default_browsers_path()

    if sys.platform == "win32":
        for stream_name in ("stdout", "stderr"):
            stream = getattr(sys, stream_name, None)
            if stream is not None and hasattr(stream, "reconfigure"):
                try:
                    stream.reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass
