"""ziomek health endpoints."""
from fastapi import APIRouter

from ziomek.server import _tts_model, _state_machine


router = APIRouter()


@router.get("/status")
async def status():
    """Get server health status."""
    ready = _tts_model is not None and _tts_model.ready
    model_loaded = _tts_model is not None and _tts_model.ready
    return {
        "ready": ready,
        "model_loaded": model_loaded,
        "endpoints": {
            "tts": ["POST /api/tts/generate", "POST /api/tts/speak", "GET /api/tts/status", "GET /api/tts/voices"],
            "avatar": ["POST /api/avatar/input", "GET /api/avatar/state", "POST /api/avatar/expression", "GET /api/avatar/sprite"],
        },
    }


@router.get("/")
async def root():
    """Server root endpoint."""
    return {
        "name": "ziomek",
        "version": "0.1.0",
        "endpoints": {"generate": "POST /api/tts/generate", "status": "GET /status"},
    }
