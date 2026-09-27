"""ziomek TTS API endpoints."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/tts")


@router.get("/status")
async def tts_status() -> dict:
    """Get TTS server status."""
    from ziomek.server import _tts_model
    ready = _tts_model is not None and _tts_model.ready  # type: ignore[arg-type]
    return {"ready": ready, "voices": ["cosette", "marius", "javert", "alba"]}


@router.get("/voices")
async def list_voices() -> dict:
    """List available voices."""
    return {
        "voices": ["cosette", "marius", "javert", "alba", "jean", "anna", "vera", "fantine",
                   "charles", "paul", "eponine", "azelma", "george", "mary", "jane",
                   "michael", "eve", "bill_boerst", "peter_yearsley", "stuart_bell",
                   "caro_davy", "giovanni", "lola", "juergen", "rafael", "estelle"],
        "default": "cosette",
    }


@router.post("/generate")
async def tts_generate(request: Request) -> dict:
    """Generate WAV audio from text."""
    from ziomek.server import _tts_model, _voice_cache
    if _tts_model is None or not _tts_model.ready:
        return JSONResponse(status_code=503, content={"error": "TTS model not loaded"})
    body = await request.json()
    text = body.get("text", "")
    voice = body.get("voice", "default")
    from ziomek.tts.generate import generate_wav
    audio_b64, duration, sample_rate = generate_wav(_tts_model, _voice_cache, text, voice)
    return {
        "audio_b64": audio_b64,
        "duration": duration,
        "sample_rate": sample_rate,
        "channels": 1,
        "bit_depth": 16,
        "voice": voice,
    }


@router.post("/speak")
async def tts_speak(request: Request) -> dict:
    """Generate and play audio."""
    from ziomek.server import _tts_model, _voice_cache, _audio_player
    if _tts_model is None or not _tts_model.ready:
        return JSONResponse(status_code=503, content={"error": "TTS not ready"})
    body = await request.json()
    text = body.get("text", "")
    voice = body.get("voice", "default")
    from ziomek.tts.generate import generate_wav
    audio_b64, duration, sample_rate = generate_wav(_tts_model, _voice_cache, text, voice)
    import base64
    wav_bytes = base64.b64decode(audio_b64)
    if _audio_player is not None:  # type: ignore[arg-type]
        _audio_player.play(wav_bytes, sample_rate)
    return {
        "status": "playing",
        "duration": duration,
        "sample_rate": sample_rate,
        "channels": 1,
        "bit_depth": 16,
        "voice": voice,
    }
