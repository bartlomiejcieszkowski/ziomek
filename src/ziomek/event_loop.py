"""Shared event loop capture for scheduling async work from non-async threads.

The server captures its running loop at startup so callbacks fired from worker
threads (RealtimeSTT's process, the gamepad polling thread) can be scheduled on
it instead of running on whichever thread called them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

_loop: asyncio.AbstractEventLoop | None = None


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Remember the loop the server runs on."""
    global _loop
    _loop = loop


def get_event_loop() -> asyncio.AbstractEventLoop | None:
    """Return the captured loop, or the loop running in the current thread."""
    if _loop is not None:
        return _loop
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def call_on_event_loop(
    callback: Callable,
    *args,
    loop: asyncio.AbstractEventLoop | None = None,
) -> bool:
    """Schedule a callback on the captured loop.

    Returns True when the callback was scheduled, False when no loop is available.
    """
    loop = loop or get_event_loop()
    if loop is None or not loop.is_running():
        return False

    if asyncio.iscoroutinefunction(callback):
        asyncio.run_coroutine_threadsafe(callback(*args), loop)
    else:
        loop.call_soon_threadsafe(callback, *args)
    return True
