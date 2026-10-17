"""ziomek STT API endpoints."""

from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ziomek.stt import STTResult, STTState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stt", tags=["STT"])

# Available faster-whisper models
AVAILABLE_MODELS = [
    "tiny.en",
    "base.en",
    "small.en",
    "medium.en",
    "large-v3",
]


class TranscribeRequest(BaseModel):
    """Request body for one-shot transcription."""

    audio_b64: str  # base64-encoded WAV audio
    sample_rate: int = 16000


class ReconfigureRequest(BaseModel):
    """Request body for engine/model reconfiguration."""

    engine: str = "faster_whisper"
    model: str = "tiny.en"


@router.get(
    "/status",
    summary="Get STT status",
    description="Return STT engine stats (state, engine, model, transcription count).",
)
async def stt_status() -> dict:
    """Get STT engine status."""
    from ziomek.server import _stt_engine

    if _stt_engine is None:
        raise HTTPException(status_code=503, detail="STT engine not initialized")

    stats = _stt_engine.stats
    return {
        "state": stats.state.value,
        "engine": stats.engine_name,
        "model": stats.model_name,
        "last_text": stats.last_text,
        "last_is_final": stats.last_is_final,
        "transcription_count": stats.transcription_count,
    }


@router.post(
    "/start",
    summary="Start STT recording",
    description="Start audio recording for speech-to-text transcription.",
)
async def stt_start() -> dict:
    """Start STT recording."""
    from ziomek.server import _stt_engine

    if _stt_engine is None:
        raise HTTPException(status_code=503, detail="STT engine not initialized")

    try:
        _stt_engine.start_recording()
        return {"status": "started", "state": _stt_engine.state.value}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post(
    "/stop",
    summary="Stop STT recording",
    description="Stop audio recording. Engine remains ready for next start.",
)
async def stt_stop() -> dict:
    """Stop STT recording."""
    from ziomek.server import _stt_engine

    if _stt_engine is None:
        raise HTTPException(status_code=503, detail="STT engine not initialized")

    try:
        _stt_engine.stop_recording()
        return {"status": "stopped", "state": _stt_engine.state.value}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post(
    "/transcribe",
    summary="One-shot transcription",
    description="Transcribe a single audio blob (base64 WAV). Returns text result.",
)
async def stt_transcribe(request: TranscribeRequest) -> dict:
    """One-shot transcription from base64 audio."""
    from ziomek.server import _stt_engine

    if _stt_engine is None:
        raise HTTPException(status_code=503, detail="STT engine not initialized")

    try:
        audio_bytes = base64.b64decode(request.audio_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio data")

    result = _stt_engine.transcribe_chunk(audio_bytes, request.sample_rate)
    return {
        "text": result.text,
        "is_final": result.is_final,
    }


@router.post(
    "/reconfigure",
    summary="Reconfigure STT engine",
    description="Change engine/model at runtime. Stops recording, recreates engine, returns to idle.",
)
async def stt_reconfigure(request: ReconfigureRequest) -> dict:
    """Reconfigure STT engine with new engine/model."""
    from ziomek.server import _stt_engine

    if _stt_engine is None:
        raise HTTPException(status_code=503, detail="STT engine not initialized")

    if request.engine not in ("faster_whisper", "whisper_cpp"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported engine: {request.engine}. Use 'faster_whisper' or 'whisper_cpp'.",
        )

    if request.model not in AVAILABLE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model: {request.model}. Available: {', '.join(AVAILABLE_MODELS)}.",
        )

    success, message = _stt_engine.reconfigure(request.engine, request.model)

    if not success:
        raise HTTPException(status_code=500, detail=message)

    return {
        "status": "reconfigured",
        "engine": request.engine,
        "model": request.model,
        "message": message,
    }


@router.get(
    "/models",
    summary="List available STT models",
    description="Return list of available faster-whisper model identifiers.",
)
async def stt_models() -> dict:
    """List available faster-whisper models."""
    return {
        "models": AVAILABLE_MODELS,
        "default": "tiny.en",
    }
