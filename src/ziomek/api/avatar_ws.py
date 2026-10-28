"""ziomek avatar WebSocket endpoint for pushing expression state changes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ziomek.event_loop import call_on_event_loop

logger = logging.getLogger(__name__)

router = APIRouter()

# Track connected WebSocket clients
_connected_clients: list[WebSocket] = []


async def _broadcast(message: dict[str, Any]) -> None:
    """Send message to all connected WebSocket clients."""
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


async def _state_message(websocket: WebSocket) -> None:
    """Send the current expression state to a single client."""
    from ziomek.server import _state_machine

    state = _state_machine.getCurrentState()
    await websocket.send_json(
        {
            "type": "state",
            "expression": state.expressionName,
            "cycleIndex": state.cycleIndex,
        }
    )


def register_client(websocket: WebSocket) -> None:
    """Register a WebSocket connection."""
    _connected_clients.append(websocket)
    logger.info("Avatar WebSocket client connected (total: %d)", len(_connected_clients))


def remove_client(websocket: WebSocket) -> None:
    """Unregister a WebSocket connection."""
    if websocket in _connected_clients:
        _connected_clients.remove(websocket)
    logger.info("Avatar WebSocket client disconnected (total: %d)", len(_connected_clients))


def state_message(expression: str, cycle_index: int) -> dict[str, Any]:
    """Build the state message the page renders."""
    return {"type": "state", "expression": expression, "cycleIndex": cycle_index}


def notify_change(expression: str, cycle_index: int) -> None:
    """Push an expression change to every connected client.

    Called from the state machine, which can fire from the gamepad polling
    thread, so the broadcast is scheduled on the server's event loop.
    """
    if not _connected_clients:
        return

    async def _push() -> None:
        await _broadcast(state_message(expression, cycle_index))

    call_on_event_loop(_push)


@router.websocket("/api/avatar/ws")
async def avatar_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint for pushing avatar expression state changes.

    Server pushes:
        { "type": "state", "expression": "...", "cycleIndex": 0 }

    The page draws the sprite row for `expression` and the cycle column, and the
    first message is the current state so a freshly opened page draws at once.
    """
    await websocket.accept()
    register_client(websocket)

    try:
        await _state_message(websocket)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        remove_client(websocket)
