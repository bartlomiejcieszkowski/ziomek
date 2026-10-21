"""ziomek MCP tools — speak, transcribe, listening, avatar, status."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from mcp.server.context import ServerRequestContext
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
)

from .listening import ListeningSession

logger = logging.getLogger(__name__)

# Global listening session singleton
_listening_session: ListeningSession | None = None


def _get_listening_session() -> ListeningSession:
    """Get or create the global listening session singleton."""
    global _listening_session
    if _listening_session is None:
        _listening_session = ListeningSession()
    return _listening_session


# ── Tool definitions ─────────────────────────────────────────────────────────

TOOLS = [
    Tool(
        name="speak",
        description="Synthesize speech and play through ziomek audio player. Use this to make the AI speak to the user.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to speak."},
                "voice": {"type": "string", "description": "Voice name (default: cosette)."},
            },
            "required": ["text"],
        },
    ),
    Tool(
        name="transcribe",
        description="Transcribe audio (base64 WAV) to text. One-shot transcription: send audio, get back text.",
        input_schema={
            "type": "object",
            "properties": {
                "audio_b64": {"type": "string", "description": "Base64-encoded WAV audio."},
                "sample_rate": {"type": "integer", "description": "Sample rate (default: 16000)."},
            },
            "required": ["audio_b64"],
        },
    ),
    Tool(
        name="start_listening",
        description="Start continuous listening from the microphone (hands-free mode). The server will capture audio from the default microphone and transcribe in real-time. Call get_transcription() every ~2 seconds to retrieve new results. Call stop_listening() when done.",
        input_schema={
            "type": "object",
            "properties": {
                "engine": {"type": "string", "description": "STT engine (default: faster_whisper)."},
                "model": {"type": "string", "description": "STT model (default: tiny.en)."},
            },
        },
    ),
    Tool(
        name="get_transcription",
        description="Get the latest transcription result from continuous listening. Call this every ~2 seconds after start_listening() to get new results. Returns the latest text and whether it is a final transcription.",
        input_schema={"type": "object", "properties": {}},
    ),
    Tool(
        name="stop_listening",
        description="Stop continuous listening mode. Shuts down the microphone recording thread.",
        input_schema={"type": "object", "properties": {}},
    ),
    Tool(
        name="set_expression",
        description="Set the avatar expression.",
        input_schema={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Expression name (e.g. happy, sad, neutral)."},
                "duration_ms": {"type": "integer", "description": "Duration in ms (optional, permanent if omitted)."},
            },
            "required": ["expression"],
        },
    ),
    Tool(
        name="get_expression",
        description="Get the current avatar expression and state.",
        input_schema={"type": "object", "properties": {}},
    ),
    Tool(
        name="status",
        description="Get server status including TTS readiness, STT state, uptime, and audio backend. Returns comprehensive server health information.",
        input_schema={"type": "object", "properties": {}},
    ),
]


async def _handle_speak(arguments: dict) -> CallToolResult:
    from ziomek.server import _audio_player, _settings, _tts_model, _voice_cache

    if _tts_model is None or not _tts_model.ready:
        if _tts_model is not None:
            _tts_model.load(_settings.model_path if _settings else None)
    if _tts_model is None or not _tts_model.ready:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": "TTS model not loaded"}))],
            is_error=True,
        )

    from ziomek.tts.generate import generate_wav

    text = arguments.get("text", "")
    voice = arguments.get("voice", "default")
    if _voice_cache is None:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": "Voice cache not initialized"}))],
            is_error=True,
        )
    audio_b64, duration, sample_rate = generate_wav(_tts_model, _voice_cache, text, voice)
    wav_bytes = base64.b64decode(audio_b64)

    if _audio_player is not None:
        _audio_player.play(wav_bytes, sample_rate)

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "playing",
                        "duration_s": round(duration, 3),
                        "voice": voice,
                    }
                ),
            )
        ],
    )


async def _handle_transcribe(arguments: dict) -> CallToolResult:
    from ziomek.server import _stt_engine

    if _stt_engine is None:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": "STT engine not initialized"}))],
            is_error=True,
        )

    audio_b64 = arguments.get("audio_b64", "")
    sample_rate = arguments.get("sample_rate", 16000)

    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": "Invalid base64 audio data"}))],
            is_error=True,
        )

    result = _stt_engine.transcribe_chunk(audio_bytes, sample_rate)
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "text": result.text,
                        "is_final": result.is_final,
                    }
                ),
            )
        ],
    )


async def _handle_start_listening(arguments: dict) -> CallToolResult:
    session = _get_listening_session()
    engine = arguments.get("engine", "faster_whisper")
    model = arguments.get("model", "tiny.en")
    success = session.start(engine_name=engine, model_name=model)

    if success:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "status": "listening",
                            "message": "Continuous listening started",
                        }
                    ),
                )
            ],
        )
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "message": "Failed to start listening (already active or engine error)",
                    }
                ),
            )
        ],
        is_error=True,
    )


async def _handle_get_transcription() -> CallToolResult:
    session = _get_listening_session()
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(session.get_result()))],
    )


async def _handle_stop_listening() -> CallToolResult:
    session = _get_listening_session()
    success = session.stop()

    if success:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "status": "stopped",
                            "state": "idle",
                        }
                    ),
                )
            ],
        )
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "message": "No active listening session",
                    }
                ),
            )
        ],
        is_error=True,
    )


async def _handle_set_expression(arguments: dict) -> CallToolResult:
    from ziomek.server import _state_machine

    if _state_machine is None:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": "State machine not initialized"}))],
            is_error=True,
        )

    expression = arguments.get("expression", "")
    duration_ms = arguments.get("duration_ms")
    ok = _state_machine.setExpression(expression, duration_ms)
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "ok": ok,
                        "expression": expression,
                    }
                ),
            )
        ],
    )


async def _handle_get_expression() -> CallToolResult:
    from ziomek.server import _state_machine

    if _state_machine is None:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": "State machine not initialized"}))],
            is_error=True,
        )

    state = _state_machine.tick(16)
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "expression": state.expressionName,
                        "cycleIndex": state.cycleIndex,
                        "message": state.message,
                        "messageExpiry": state.messageExpiry,
                    }
                ),
            )
        ],
    )


async def _handle_status() -> CallToolResult:
    from ziomek.server import _audio_player, _stt_engine, _tts_model, get_uptime

    tts_ready = _tts_model is not None and _tts_model.ready

    stt_state = "uninitialized"
    stt_engine_name = "n/a"
    stt_model = "n/a"
    if _stt_engine is not None:
        stt_state = _stt_engine.stats.state.value
        stt_engine_name = _stt_engine.stats.engine_name
        stt_model = _stt_engine.stats.model_name

    audio_backend = "n/a"
    audio_device = "n/a"
    if _audio_player is not None:
        audio_backend = _audio_player.backend_name
        audio_device = _audio_player.device_name

    uptime_s = get_uptime()

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "tts_ready": tts_ready,
                        "stt_state": stt_state,
                        "stt_engine": stt_engine_name,
                        "stt_model": stt_model,
                        "audio_backend": audio_backend,
                        "audio_device": audio_device,
                        "uptime_seconds": round(uptime_s, 1),
                    }
                ),
            )
        ],
    )


async def _on_list_tools(_ctx: ServerRequestContext, params: Any) -> ListToolsResult:
    return ListToolsResult(tools=TOOLS)


async def _on_call_tool(ctx: ServerRequestContext, params: CallToolRequestParams) -> CallToolResult:
    name = params.name
    arguments = params.arguments or {}

    handlers = {
        "speak": _handle_speak,
        "transcribe": _handle_transcribe,
        "start_listening": _handle_start_listening,
        "get_transcription": _handle_get_transcription,
        "stop_listening": _handle_stop_listening,
        "set_expression": _handle_set_expression,
        "get_expression": _handle_get_expression,
        "status": _handle_status,
    }

    handler = handlers.get(name)
    if handler:
        return await handler(arguments)
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Unknown tool: {name}")],
            is_error=True,
        )
