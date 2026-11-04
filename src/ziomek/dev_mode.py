"""The mode a server runs in, read by the parts that answer only in it."""

from __future__ import annotations

_dev_mode: bool = False


def set_dev_mode(dev: bool) -> None:
    """Set whether the server runs in dev mode, which is what opens the debug paths and the debug page."""
    global _dev_mode
    _dev_mode = dev


def get_dev_mode() -> bool:
    """Get the current dev mode."""
    return _dev_mode
