"""ziomek MCP tools — say, play, transcribe, listening, avatar, status."""

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

from ziomek.roster import DuplicateNameError, Roster, get_roster

from .listening import ListeningSession

logger = logging.getLogger(__name__)

# Global listening session singleton
_listening_session: ListeningSession | None = None

# The participants taking part in one call.


def _get_roster(settings: Any = None) -> Roster:
    return get_roster(settings)


def _text_payload(data: dict) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(data))])


def _get_listening_session() -> ListeningSession:
    """Get or create the global listening session singleton."""
    global _listening_session
    if _listening_session is None:
        _listening_session = ListeningSession()
    return _listening_session


# ── Tool definitions ─────────────────────────────────────────────────────────

TOOLS = [
    Tool(
        name="say",
        description="Say text as a participant. The text is written to the record for that participant unless record is set to false.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Participant to say for."},
                "text": {"type": "string", "description": "Text to say."},
                "record": {"type": "boolean", "description": "Write the text to the record (default: true)."},
            },
            "required": ["name", "text"],
        },
    ),
    Tool(
        name="write",
        description="Record text for a participant without producing audio.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Participant who wrote the text."},
                "text": {"type": "string", "description": "Text to record."},
            },
            "required": ["name", "text"],
        },
    ),
    Tool(
        name="play",
        description="Play text with a voice without taking part in a call. Nothing is written to the record.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to play."},
                "voice": {"type": "string", "description": "Voice to use (default voice when not given)."},
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
                "name": {
                    "type": "string",
                    "description": "Participant this expression is for. Without it, the global avatar is used.",
                },
            },
            "required": ["expression"],
        },
    ),
    Tool(
        name="get_expression",
        description="Get the current avatar expression and state.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Participant to read. Without it, the global avatar is used.",
                },
            },
        },
    ),
    Tool(
        name="join",
        description="Take part in the current call. Name and voice are optional, taken from the configured pool when not given.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name for this participant."},
                "voice": {"type": "string", "description": "Voice to use for this participant."},
                "call_id": {"type": "string", "description": "Reserved, not used yet."},
            },
            "required": [],
        },
    ),
    Tool(
        name="hold",
        description="Go quiet for a while, so the inactivity timer does not drop the participant.",
        input_schema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    ),
    Tool(
        name="leave",
        description="Leave the current call and release the name and voice.",
        input_schema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    ),
    Tool(
        name="status",
        description="Get server status including TTS readiness, STT state, uptime, and audio backend. Returns comprehensive server health information.",
        input_schema={"type": "object", "properties": {}},
    ),
]


async def _handle_write(arguments: dict) -> CallToolResult:
    """Record text for a participant without producing audio."""
    from ziomek.server import _settings

    roster = _get_roster(_settings)
    name = arguments.get("name")
    participant = _find_participant(roster, name)
    if participant is None:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": f"Unknown participant: {name}"}))],
            is_error=True,
        )

    text = arguments.get("text", "")
    participant.add_text(text, author="agent")
    return _text_payload({"name": participant.name, "action": "text", "text": text})


async def _handle_say(arguments: dict) -> CallToolResult:
    """Say text as a participant, and write it down unless asked not to."""
    from ziomek.server import _settings

    roster = _get_roster(_settings)
    name = arguments.get("name")
    participant = _find_participant(roster, name)
    if participant is None:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": f"Unknown participant: {name}"}))],
            is_error=True,
        )

    text = arguments.get("text", "")
    if arguments.get("record", True):
        participant.add_text(text, author="agent")
    return await _handle_play({"text": text, "voice": participant.voice})


async def _handle_play(arguments: dict) -> CallToolResult:
    """Play text with a voice without taking part in a call."""
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
    # Play does not take part in a call, so no participant is looked up here.
    voice = arguments.get("voice") or "default"
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
    machine, participant = _resolve_machine(arguments.get("name"))

    if machine is None:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": "State machine not initialized"}))],
            is_error=True,
        )

    expression = arguments.get("expression", "")
    duration_ms = arguments.get("duration_ms")
    ok = machine.setExpression(expression, duration_ms)
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "ok": ok,
                        "expression": expression,
                        "name": participant.name if participant is not None else None,
                    }
                ),
            )
        ],
    )


async def _handle_get_expression(arguments: dict | None = None) -> CallToolResult:
    machine, participant = _resolve_machine((arguments or {}).get("name"))

    if machine is None:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": "State machine not initialized"}))],
            is_error=True,
        )

    state = machine.tick(16)
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
                        "name": participant.name if participant is not None else None,
                    }
                ),
            )
        ],
    )


async def _handle_join(arguments: dict) -> CallToolResult:
    from ziomek.api import avatar_ws
    from ziomek.server import _settings

    roster = _get_roster(_settings)
    try:
        participant = roster.join(arguments.get("name"), arguments.get("voice"))
    except DuplicateNameError as exc:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": str(exc)}))],
            is_error=True,
        )
    # The single view shows one participant, so the first one to join is shown.
    if avatar_ws._shown is None:
        avatar_ws.show(participant)
    return _text_payload(
        {
            "name": participant.name,
            "voice": participant.voice,
            "call_id": arguments.get("call_id"),
            "state": participant.state,
        }
    )


async def _handle_hold(arguments: dict) -> CallToolResult:
    from ziomek.server import _settings

    roster = _get_roster(_settings)
    participant = _find_participant(roster, arguments.get("name"))
    if participant is None:
        return CallToolResult(
            content=[
                TextContent(type="text", text=json.dumps({"error": f"Unknown participant: {arguments.get('name')}"}))
            ],
            is_error=True,
        )
    participant.hold()
    return _text_payload({"name": participant.name, "state": participant.state, "quiet_for": roster.quiet_for})


async def _handle_leave(arguments: dict) -> CallToolResult:
    from ziomek.server import _settings

    roster = _get_roster(_settings)
    participant = _find_participant(roster, arguments.get("name"))
    if participant is None:
        return CallToolResult(
            content=[
                TextContent(type="text", text=json.dumps({"error": f"Unknown participant: {arguments.get('name')}"}))
            ],
            is_error=True,
        )
    participant.leave()
    return _text_payload({"name": participant.name, "state": participant.state})


def _resolve_machine(name: str | None):
    """The machine for the named participant, falling back to the global avatar."""
    from ziomek.server import _settings, _state_machine

    participant = _find_participant(_get_roster(_settings), name) if name else None
    if participant is not None and getattr(participant, "state_machine", None) is not None:
        return participant.state_machine, participant
    return _state_machine, participant


def _find_participant(roster: Roster, name: str):
    return next((p for p in roster.participants if p.name == name), None)


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
        "say": _handle_say,
        "write": _handle_write,
        "play": _handle_play,
        "transcribe": _handle_transcribe,
        "start_listening": _handle_start_listening,
        "get_transcription": _handle_get_transcription,
        "stop_listening": _handle_stop_listening,
        "set_expression": _handle_set_expression,
        "get_expression": _handle_get_expression,
        "join": _handle_join,
        "hold": _handle_hold,
        "leave": _handle_leave,
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
