"""ziomek avatar API endpoints."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ziomek.avatar.morda import fallback_target, resolve_reference
from ziomek.avatar.png import read_png_dimensions
from ziomek.avatar.skins import get_registry
from ziomek.avatar.state_machine import AvatarInput

router = APIRouter(tags=["Avatar"])

# Path to the shared HTML renderer
_renderer_html = Path(__file__).parent.parent / "resources" / "renderer.html"

# Path to the gamepad module (moved from client/ to root package)
_gamepad_module = None


def _import_gamepad():
    global _gamepad_module
    if _gamepad_module is None:
        from ziomek import gamepad as _gamepad_module
    return _gamepad_module


def _not_initialized(msg: str) -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": msg})


@router.get(
    "/avatar",
    summary="Render HTML",
    description="Serve the avatar renderer HTML page (used by the client to display the avatar in a browser).",
)
async def get_avatar_view() -> HTMLResponse:
    """Serve the avatar renderer HTML (fetched by client from server)."""
    if not _renderer_html.exists():
        return HTMLResponse(
            content="<html><body><h1>Renderer not found</h1></body></html>",
            status_code=404,
        )
    return HTMLResponse(content=_renderer_html.read_text())


@router.get(
    "/api/avatar/state",
    summary="Get avatar state",
    description="Return the current expression, sprite cycle, and displayed message.",
)
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


@router.post(
    "/api/avatar/input",
    summary="Feed gamepad input",
    description="Feed gamepad button/axis state into the avatar state machine. Returns the new expression.",
)
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


@router.post(
    "/api/avatar/expression",
    summary="Set expression",
    description="Force-set an avatar expression, optionally for a limited duration.",
)
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


@router.post(
    "/api/avatar/speak",
    summary="Speak with avatar",
    description="Synthesize speech (TTS), play it, and optionally show an expression on the avatar.",
)
async def speak(request: Request) -> Any:
    """Generate speech and optionally set an expression."""
    from ziomek.server import _audio_player, _state_machine, _tts_model, _voice_cache
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


@router.get(
    "/api/avatar/sprite",
    summary="Get a skin",
    description="Return the sheet a skin names and the mapping a page draws from, for the named skin or the configured default.",
)
async def get_sprite(request: Request) -> Any:
    """Answer for one skin, which is the only place the pages read a mapping from."""
    registry = get_registry()
    if registry is None:
        return JSONResponse(status_code=503, content={"error": "Skin registry not initialized"})
    from ziomek.server import _settings

    name = request.query_params.get("skin") or _settings.roster_avatar
    skin = registry.get(name)
    if skin is None:
        return JSONResponse(status_code=404, content={"error": "No such skin"})
    sheet = skin.sheet()
    dimensions = read_png_dimensions(sheet) if sheet else None
    frame = skin.definition.frame
    grid = skin.definition.grid
    return {
        "skin": skin.name,
        # A definition of type image names one image per frame, so there is no sheet to send whole.
        "sprite_b64": None if sheet is None else f"data:image/png;base64,{base64.b64encode(sheet).decode('utf-8')}",
        "width": None if dimensions is None else dimensions[0],
        "height": None if dimensions is None else dimensions[1],
        "frameWidth": None if frame is None else frame.width,
        "frameHeight": None if frame is None else frame.height,
        "grid": None if grid is None else {"rows": grid.rows, "columns": grid.columns},
        "expressions": _mapping(skin),
        "fallback": skin.frame_descriptor(fallback_target(skin.definition)),
    }


@router.get(
    "/api/avatar/image",
    summary="Get one image",
    description="Return one image a skin names, for a frame that is not cut from a sheet.",
)
async def get_image(request: Request) -> Any:
    """Answer for one file of one skin, which the page caches under that name."""
    registry = get_registry()
    if registry is None:
        return _not_initialized("Skin registry not initialized")
    from ziomek.server import _settings

    name = request.query_params.get("skin") or _settings.roster_avatar
    file = request.query_params.get("file") or ""
    skin = registry.get(name)
    if skin is None:
        return JSONResponse(status_code=404, content={"error": "No such skin"})
    buffer = skin.read_file(file)
    if buffer is None:
        return JSONResponse(status_code=404, content={"error": "This skin names no such file"})
    dimensions = read_png_dimensions(buffer)
    if dimensions is None:
        return JSONResponse(status_code=500, content={"error": "Image does not report its size"})
    return {
        "skin": skin.name,
        "file": file,
        "image_b64": f"data:image/png;base64,{base64.b64encode(buffer).decode('utf-8')}",
        "width": dimensions[0],
        "height": dimensions[1],
    }


def _entry(skin, reference) -> dict | None:
    """One expression as the page needs it: the frames it shows, in order, and its timing."""
    if reference is None:
        return None
    target = resolve_reference(skin.definition, reference)
    if target is None:
        return None
    frame = skin.frame_descriptor(target)
    if frame is None:
        return None
    return {"frames": [frame], "interval_ms": None, "loop": False}


def _mapping(skin) -> dict:
    """The frames an expression shows, in the order it declares them, each with how it is placed."""
    mapping = {}
    for expression_name in skin.expression_names():
        frames = [frame for frame in (skin.frame_descriptor(target) for target in skin.order(expression_name)) if frame]
        if not frames:
            continue
        mapping[expression_name] = {
            "frames": frames,
            "interval_ms": skin.interval_ms(expression_name),
            "loop": skin.loops(expression_name),
        }
    return mapping
