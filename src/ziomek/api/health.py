"""ziomek health endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from ziomek import __version__
from ziomek.server import _audio_player, _tts_model, _voice_cache, get_uptime

router = APIRouter(tags=["Health"])


@router.get(
    "/status",
    summary="Server health",
    description="Check overall server status, model readiness, and discover endpoints.",
)
async def status():
    """Get server health status."""
    ready = _tts_model is not None and _tts_model.ready
    model_loaded = ready

    # Audio backend info
    audio_backend = "unknown"
    audio_device = None
    if _audio_player is not None:
        audio_backend = _audio_player.backend_name
        audio_device = _audio_player.device_name

    # STT info
    stt_info: dict[str, object] = {"engine": None, "model": None, "state": None}
    from ziomek.server import _stt_engine

    if _stt_engine is not None:
        stats = _stt_engine.stats
        stt_info = {
            "engine": stats.engine_name,
            "model": stats.model_name,
            "state": stats.state.value,
        }

    # Cache stats
    cache_stats: dict[str, object] = {"size_mb": 0, "files": 0}
    if _voice_cache is not None and _voice_cache._cache_dir:
        cache_dir = Path(_voice_cache._cache_dir)
        if cache_dir.exists():
            files = list(cache_dir.glob("*.wav")) + list(cache_dir.glob("*.mp3"))
            cache_stats["files"] = len(files)
            total_bytes = sum(f.stat().st_size for f in files)
            cache_stats["size_mb"] = round(total_bytes / (1024 * 1024), 2)

    return {
        "uptime_seconds": round(get_uptime(), 2),
        "model_loaded": model_loaded,
        "ready": ready,
        "audio_backend": audio_backend,
        "audio_device": audio_device,
        "cache_dir": _voice_cache._cache_dir if _voice_cache else None,
        "cache_stats": cache_stats,
        "endpoints": {
            "tts": ["POST /api/tts/generate", "POST /api/tts/speak", "GET /api/tts/status", "GET /api/tts/voices"],
            "stt": ["GET /api/stt/status", "POST /api/stt/start", "POST /api/stt/stop", "POST /api/stt/transcribe", "WS /api/stt/stream"],
            "avatar": [
                "POST /api/avatar/input",
                "GET /api/avatar/state",
                "POST /api/avatar/expression",
                "GET /api/avatar/sprite",
                "POST /api/avatar/speak",
                "GET /api/avatar/view",
            ],
        },
        "stt": stt_info,
    }


@router.get(
    "/",
    summary="Server info",
    description="Returns basic server identification and key endpoint routes.",
)
async def root() -> dict:
    """Server root endpoint."""
    return {
        "name": "ziomek",
        "version": __version__,
        "endpoints": {
            "generate": "POST /api/tts/generate",
            "status": "GET /api/status",
        },
    }
