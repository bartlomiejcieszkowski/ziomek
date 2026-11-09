"""The signal path that tells a page which part of the picture changed."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ziomek.event_loop import call_on_event_loop

logger = logging.getLogger(__name__)

router = APIRouter()

# The pages that are listening for a signal.
_connected_clients: list[WebSocket] = []


async def _broadcast(message: dict[str, Any]) -> None:
    """Send the signal to every page that is listening."""
    if not _connected_clients:
        return
    disconnected: list[WebSocket] = []
    for client in _connected_clients:
        try:
            await client.send_json(message)
        except (WebSocketDisconnect, RuntimeError, Exception):
            disconnected.append(client)
    for client in disconnected:
        if client in _connected_clients:
            _connected_clients.remove(client)


def tell_page(kind: str) -> None:
    """Tell every listening page that this part changed.

    The app can report a change from a worker thread (the gamepad polling thread, an MCP tool
    call), so the send is scheduled on the server's event loop instead of running on the thread
    that noticed the change. A change nobody is listening for is not kept; a page asks for the whole
    picture when its connection is open, which is also what a page that was away needs.
    """
    if not _connected_clients:
        return

    async def _push() -> None:
        await _broadcast({"kind": kind})

    call_on_event_loop(_push)


def register_client(websocket: WebSocket) -> None:
    """Register a page that is listening for a signal."""
    _connected_clients.append(websocket)
    logger.info("signal page connected (total: %d)", len(_connected_clients))


def remove_client(websocket: WebSocket) -> None:
    """Unregister a page."""
    if websocket in _connected_clients:
        _connected_clients.remove(websocket)
    logger.info("signal page disconnected (total: %d)", len(_connected_clients))


@router.websocket("/api/roster/ws")
async def roster_ws(websocket: WebSocket) -> None:
    """Signal path for pages that draw only what changed.

    The app sends:
        { "kind": "room" } or { "kind": "record" }

    Nothing is sent when the connection opens, because the page asks for the picture itself.
    """
    await websocket.accept()
    register_client(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        remove_client(websocket)
