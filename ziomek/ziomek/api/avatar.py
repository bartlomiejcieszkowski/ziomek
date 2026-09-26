"""ziomek avatar API endpoints."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ziomek.avatar.state_machine import AvatarInput
from ziomek.avatar.sprites import sprite_to_base64


router = APIRouter()

# Path to the shared HTML renderer
_renderer_html = Path(__file__).parent.parent / "client" / "resources" / "renderer.html"


def _not_initialized(msg: str) -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": msg})


@router.get("/api/avatar/view")
async def get_avatar_view() -> HTMLResponse:
    """Serve the avatar renderer HTML (fetched by client from server)."""
    if not _renderer_html.exists():
        return HTMLResponse(
            content="<html><body><h1>Renderer not found</h1></body></html>",
            status_code=404,
        )
    return HTMLResponse(content=_renderer_html.read_text())


@router.get("/api/avatar/state")
async def get_state() -> Any:
    """Get current avatar state."""
    from ziomek.server import _state_machine
    if _state_machine is None:
        return JSONResponse(status_code=503, content={"error": "State machine not initialized"})
    state = _state_machine.tick(16)
    return {
        "expression": state.expressionName,
        "cycleIndex": state.cycleIndex,
        "message": state.message,
        "messageExpiry": state.messageExpiry,
    }


@router.post("/api/avatar/input")
async def set_input(request: Request) -> Any:
    """Feed gamepad/VSCode state to the state machine."""
    from ziomek.server import _state_machine
    if _state_machine is None:
        return JSONResponse(status_code=503, content={"error": "State machine not initialized"})
    body = await request.json()
    inp = AvatarInput(
        buttons=body.get("buttons", []),
        axes=body.get("axes", [0, 0, 0]),
        connected=body.get("connected", False),
        streaming=body.get("streaming", False),
        chatFocused=body.get("chatFocused", False),
        errorState=body.get("errorState", False),
    )
    _state_machine.update(inp)
    state = _state_machine.tick(16)
    return {"expression": state.expressionName, "cycleIndex": state.cycleIndex}


@router.post("/api/avatar/expression")
async def set_expression(request: Request) -> Any:
    """Force-set an expression."""
    from ziomek.server import _state_machine
    if _state_machine is None:
        return JSONResponse(status_code=503, content={"error": "State machine not initialized"})
    body = await request.json()
    name = body.get("name", "")
    duration_ms = body.get("duration_ms")
    ok = _state_machine.setExpression(name, duration_ms)
    return {"ok": ok}


@router.post("/api/avatar/speak")
async def speak(request: Request) -> Any:
    """Generate speech and optionally set an expression."""
    from ziomek.server import _tts_model, _voice_cache, _audio_player, _state_machine
    from ziomek.tts.generate import generate_wav

    body = await request.json()
    text = body.get("text", "")
    voice = body.get("voice", "default")
    expression = body.get("expression")

    if _tts_model is None or not _tts_model.ready:
        return JSONResponse(status_code=503, content={"error": "TTS not ready"})
    if _state_machine is None:
        return JSONResponse(status_code=503, content={"error": "State machine not initialized"})
    if _voice_cache is None:
        return JSONResponse(status_code=503, content={"error": "Voice cache not initialized"})
    if expression:
        _state_machine.setExpression(expression)
    audio_b64, duration, sample_rate = generate_wav(_tts_model, _voice_cache, text, voice)
    import base64
    wav_bytes = base64.b64decode(audio_b64)
    if _audio_player is not None:
        _audio_player.play(wav_bytes, sample_rate)
    return {
        "status": "playing",
        "duration": duration,
        "sample_rate": sample_rate,
        "channels": 1,
        "bit_depth": 16,
        "voice": voice,
    }


@router.get("/api/avatar/sprite")
async def get_sprite() -> Any:
    """Get sprite sheet for client rendering."""
    from ziomek.server import _skin_registry
    if _skin_registry is None:
        return JSONResponse(status_code=503, content={"error": "Skin registry not initialized"})
    skin = _skin_registry.get("single-frame")
    if skin is None:
        return JSONResponse(status_code=404, content={"error": "No default skin"})
    try:
        sprite_data = sprite_to_base64(skin.getSpriteBuffer())
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"error": "Sprite file not found"})
    return {
        "sprite_b64": sprite_data,
        "width": skin.spriteWidth,
        "height": skin.spriteHeight,
        "frameWidth": skin.frameWidth,
        "frameHeight": skin.frameHeight,
    }
