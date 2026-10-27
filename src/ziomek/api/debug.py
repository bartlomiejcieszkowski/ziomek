"""ziomek debug API — endpoints exposed only in --dev mode."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ziomek.logging import get_log_buffer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Debug"])


def _get_server_globals() -> dict[str, Any]:
    """Collect global server state from ziomek.server module."""
    from ziomek.server import (
        _audio_player,
        _gamepad_manager,
        _state_machine,
        _stt_engine,
        _tts_model,
        _voice_cache,
        get_uptime,
    )

    state: dict[str, Any] = {
        "uptime_seconds": round(get_uptime(), 2),
        "tts_model_ready": _tts_model is not None and _tts_model.ready,
        "voice_cache_dir": _voice_cache.cache_dir if _voice_cache else None,
        "audio_backend": _audio_player.backend_name if _audio_player else None,
        "audio_device": _audio_player.device_name if _audio_player else None,
        "state_machine_initialized": _state_machine is not None,
        "stt_engine_initialized": _stt_engine is not None,
        "stt_engine_state": _stt_engine.state.value if _stt_engine else None,
        "stt_stats": {
            "state": _stt_engine.stats.state.value if _stt_engine else None,
            "engine_name": _stt_engine.stats.engine_name if _stt_engine else None,
            "model_name": _stt_engine.stats.model_name if _stt_engine else None,
            "transcription_count": _stt_engine.stats.transcription_count if _stt_engine else 0,
        }
        if _stt_engine
        else None,
        "gamepad_manager_initialized": _gamepad_manager is not None,
    }
    return state


def _get_cache_stats() -> dict[str, Any]:
    """Get cache directory statistics."""
    from ziomek.server import _voice_cache

    if _voice_cache is None or _voice_cache.cache_dir is None:
        return {"size_mb": 0, "files": 0, "cache_dir": None}

    cache_path = Path(_voice_cache.cache_dir)
    if not cache_path.exists():
        return {"size_mb": 0, "files": 0, "cache_dir": str(cache_path)}

    total_size = sum(f.stat().st_size for f in cache_path.rglob("*") if f.is_file())
    file_count = sum(1 for f in cache_path.rglob("*") if f.is_file())

    return {
        "size_mb": round(total_size / (1024 * 1024), 2),
        "files": file_count,
        "cache_dir": str(cache_path),
        "files_list": [str(f) for f in sorted(cache_path.rglob("*")) if f.is_file()],
    }


@router.get("/api/debug/state")
async def debug_state() -> JSONResponse:
    """Return current state of all server components."""
    return JSONResponse(content=_get_server_globals())


@router.get("/api/debug/cache")
async def debug_cache() -> JSONResponse:
    """Return cache directory statistics and file list."""
    return JSONResponse(content=_get_cache_stats())


@router.get("/api/debug/config")
async def debug_config() -> JSONResponse:
    """Return effective server configuration."""
    from ziomek.config import Settings

    settings = Settings.load()
    return JSONResponse(content=settings.model_dump())


@router.get("/api/debug/logs")
async def debug_logs(limit: int = 50) -> JSONResponse:
    """Return recent log entries from the ring buffer."""
    buf = get_log_buffer()
    entries = buf.get_entries()
    return JSONResponse(content={"entries": entries[-limit:]})


@router.post("/api/debug/logs/clear")
async def debug_logs_clear() -> JSONResponse:
    """Clear the log ring buffer."""
    buf = get_log_buffer()
    buf.clear()
    return JSONResponse(content={"status": "cleared"})


@router.post("/api/debug/config/reload")
async def debug_config_reload() -> JSONResponse:
    """Reload configuration from disk."""
    from ziomek.config import Settings

    try:
        settings = Settings.load()
        return JSONResponse(
            content={
                "status": "reloaded",
                "config_path": "ziomek_config.yaml or ~/.ziomek/ziomek_config.yaml",
                "settings": settings.model_dump(),
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )
