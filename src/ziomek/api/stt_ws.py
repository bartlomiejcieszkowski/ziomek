"""ziomek STT WebSocket endpoint for live transcription streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ziomek.stt import STTResult

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


async def _stt_callback(result: STTResult) -> None:
    """Callback invoked by STTEngine when transcription is available."""
    await _broadcast(
        {
            "type": "transcription",
            "text": result.text,
            "is_final": result.is_final,
        }
    )


def connect_ws() -> None:
    """Register a WebSocket connection."""
    logger.info("STT WebSocket client connected (total: %d)", len(_connected_clients) + 1)


def disconnect_ws(client: WebSocket) -> None:
    """Unregister a WebSocket connection."""
    if client in _connected_clients:
        _connected_clients.remove(client)
    logger.info("STT WebSocket client disconnected (total: %d)", len(_connected_clients))


@router.websocket("/api/stt/stream")
async def stt_stream(websocket: WebSocket) -> None:
    """WebSocket endpoint for live STT transcription streaming.

    Client sends commands:
        { "action": "start" }
        { "action": "stop" }
        { "action": "status" }
        { "action": "reconfigure", "engine": "faster_whisper", "model": "base.en" }

    Server pushes:
        { "type": "transcription", "text": "...", "is_final": true/false }
        { "type": "status", "state": "...", "engine": "...", "model": "..." }
        { "type": "error", "message": "..." }
    """
    from ziomek.server import _stt_engine

    await websocket.accept()
    _connected_clients.append(websocket)
    connect_ws()
    await websocket.send_json(
        {
            "type": "connected",
            "session_id": id(websocket),
        }
    )

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "start":
                if _stt_engine is None:
                    await websocket.send_json({"type": "error", "message": "STT engine not initialized"})
                    continue
                try:
                    _stt_engine.start_recording()
                    await websocket.send_json(
                        {
                            "type": "status",
                            "state": _stt_engine.state.value,
                        }
                    )
                except RuntimeError as e:
                    await websocket.send_json({"type": "error", "message": str(e)})

            elif action == "stop":
                if _stt_engine is None:
                    await websocket.send_json({"type": "error", "message": "STT engine not initialized"})
                    continue
                try:
                    _stt_engine.stop_recording()
                    await websocket.send_json(
                        {
                            "type": "status",
                            "state": _stt_engine.state.value,
                        }
                    )
                except RuntimeError as e:
                    await websocket.send_json({"type": "error", "message": str(e)})

            elif action == "status":
                if _stt_engine is None:
                    await websocket.send_json({"type": "error", "message": "STT engine not initialized"})
                    continue
                stats = _stt_engine.stats
                await websocket.send_json(
                    {
                        "type": "status",
                        "state": stats.state.value,
                        "engine": stats.engine_name,
                        "model": stats.model_name,
                        "transcription_count": stats.transcription_count,
                    }
                )

            elif action == "reconfigure":
                if _stt_engine is None:
                    await websocket.send_json({"type": "error", "message": "STT engine not initialized"})
                    continue
                engine = data.get("engine", "faster_whisper")
                model = data.get("model", "tiny")
                success, message = _stt_engine.reconfigure(engine, model)
                await websocket.send_json(
                    {
                        "type": "reconfigured",
                        "success": success,
                        "message": message,
                        "engine": engine,
                        "model": model,
                    }
                )

            else:
                await websocket.send_json({"type": "error", "message": f"Unknown action: {action}"})

    except WebSocketDisconnect:
        disconnect_ws(websocket)
    except Exception:
        logger.exception("STT WebSocket error")
        disconnect_ws(websocket)
