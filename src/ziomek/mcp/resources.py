"""ziomek MCP resources — voices, models, expressions, config."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.context import ServerRequestContext
from mcp.types import (
    ListResourcesResult,
    ReadResourceResult,
    Resource,
    TextResourceContents,
)

logger = logging.getLogger(__name__)

RESOURCES = [
    Resource(
        uri="voices://",
        name="Available Voices",
        description="List of available PocketTTS voices and the default.",
    ),
    Resource(
        uri="models://",
        name="STT Models",
        description="List of available faster-whisper STT models.",
    ),
    Resource(
        uri="expressions://",
        name="Avatar Expressions",
        description="List of valid expression names for the avatar state machine.",
    ),
    Resource(
        uri="config://",
        name="Server Configuration",
        description="Server configuration (read-only by default, sensitive fields redacted).",
    ),
]


async def _get_voices() -> ReadResourceResult:
    from ziomek.server import _tts_model

    voices = [
        "cosette",
        "marius",
        "javert",
        "alba",
        "jean",
        "anna",
        "vera",
        "fantine",
        "charles",
        "paul",
        "eponine",
        "azelma",
        "george",
        "mary",
        "jane",
        "michael",
        "eve",
        "bill_boerst",
        "peter_yearsley",
        "stuart_bell",
        "caro_davy",
        "giovanni",
        "lola",
        "juergen",
        "rafael",
        "estelle",
    ]
    default = "cosette"

    return ReadResourceResult(
        contents=[
            TextResourceContents(
                uri="voices://",
                text=json.dumps({"voices": voices, "default": default}),
            )
        ],
    )


async def _get_models() -> ReadResourceResult:
    from ziomek.api.stt import AVAILABLE_MODELS

    return ReadResourceResult(
        contents=[
            TextResourceContents(
                uri="models://",
                text=json.dumps(
                    {
                        "models": AVAILABLE_MODELS,
                        "default": "tiny.en",
                    }
                ),
            )
        ],
    )


async def _get_expressions() -> ReadResourceResult:
    from ziomek.avatar.state_machine import _EXPRESSIONS

    expressions = [
        {
            "name": e.name,
            "cycleCount": e.cycleCount,
            "durationMs": e.durationMs,
            "intensity": e.intensity,
            "triggers": [t.type for t in e.triggers],
        }
        for e in _EXPRESSIONS
    ]
    return ReadResourceResult(
        contents=[
            TextResourceContents(
                uri="expressions://",
                text=json.dumps({"expressions": expressions}),
            )
        ],
    )


async def _get_config() -> ReadResourceResult:
    from ziomek.server import _settings

    if _settings is None:
        return ReadResourceResult(
            contents=[
                TextResourceContents(
                    uri="config://",
                    text=json.dumps({"error": "Settings not initialized"}),
                )
            ],
        )

    # Import the config exposure flag from the __init__ module
    from . import get_expose_full_config

    expose_full = get_expose_full_config()

    config = {
        "host": _settings.host,
        "port": _settings.port,
        "voice": _settings.voice,
        "cache_dir": _settings.cache_dir,
        "log_level": _settings.log_level,
        "stt_engine": _settings.stt_engine,
        "stt_model": _settings.stt_model,
        "stt_model_dir": _settings.stt_model_dir,
        "model_path": _settings.model_path,
    }

    if expose_full:
        config["full_config"] = True

    return ReadResourceResult(
        contents=[
            TextResourceContents(
                uri="config://",
                text=json.dumps(config),
            )
        ],
    )


async def _on_list_resources(_ctx: ServerRequestContext, params: Any) -> ListResourcesResult:
    return ListResourcesResult(resources=RESOURCES)


async def _on_read_resource(_ctx: ServerRequestContext, params: Any) -> ReadResourceResult:
    uri = params.uri if hasattr(params, "uri") else str(params)

    if uri == "voices://":
        return await _get_voices()
    elif uri == "models://":
        return await _get_models()
    elif uri == "expressions://":
        return await _get_expressions()
    elif uri == "config://":
        return await _get_config()
    else:
        return ReadResourceResult(
            contents=[
                TextResourceContents(
                    uri=uri,
                    text=json.dumps({"error": f"Unknown resource: {uri}"}),
                )
            ],
        )
