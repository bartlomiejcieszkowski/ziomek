# MCP Server Implementation Plan

**Date:** 2026-10-20
**Status:** Draft
**Package:** `ziomek/mcp/` (subpackage)

---

## Overview

Embedded MCP server alongside ziomek HTTP server. Same process, direct imports from `ziomek.tts`, `ziomek.stt`, `ziomek.avatar`. Enabled via `--mcp` CLI flag.

## Tools

| Tool | Description | Args | Returns |
|------|-------------|------|---------|
| `speak` | Play speech through ziomek audio player | `text`, `voice` (optional) | `{"status": "playing", "duration_s": ...}` |
| `transcribe` | One-shot transcription (audio_b64 → text) | `audio_b64`, `sample_rate` (optional) | `{"text": "...", "is_final": true}` |
| `start_listening` | Start continuous mic recording (hands-free) | `engine` (optional), `model` (optional) | `{"status": "listening", "message": "..."}` |
| `get_transcription` | Poll for latest transcription result | none | `{"text": "...", "is_final": true/false, "state": "listening"}` |
| `stop_listening` | Stop continuous recording | none | `{"status": "stopped", "state": "idle"}` |
| `set_expression` | Set avatar expression | `expression`, `duration_ms` (optional) | `{"ok": true}` |
| `get_expression` | Get current avatar expression | none | `{"expression": "happy", "cycleIndex": 0}` |
| `status` | Server status (TTS, STT, uptime, audio) | none | `{"tts_ready": true, "stt_state": "listening", ...}` |

## Resources

| Resource | Description | Read-only | With `--mcp-config` |
|----------|-------------|-----------|---------------------|
| `voices://` | Available voices | ✅ | — |
| `models://` | Available STT models | ✅ | — |
| `expressions://` | Available avatar expressions | ✅ | — |
| `config://` | Server config | ✅ (sensitive fields redacted) | ✅ (full config) |

## Architecture

```
ziomek (main process)
├── server.py          # HTTP server (FastAPI)
├── mcp/
│   ├── __init__.py    # MCP server entry point
│   ├── tools.py       # Tool implementations (speak, transcribe, etc.)
│   ├── resources.py   # Resource implementations (voices, models, config)
│   └── listening.py   # Continuous listening state management
└── cli.py             # --mcp flag
```

## Tasks

### Task 1: Create MCP package scaffold

**Files to create:**
- `src/ziomek/mcp/__init__.py` — MCP server factory function
- `src/ziomek/mcp/tools.py` — Tool implementations
- `src/ziomek/mcp/resources.py` — Resource implementations
- `src/ziomek/mcp/listening.py` — Continuous listening session manager

**Changes to existing files:**
- `pyproject.toml` — add `mcp` as optional dependency, add `mcp` to extras
- `src/ziomek/cli.py` — add `--mcp` flag

**Implementation:**
- Create `ziomek/mcp/` directory with `__init__.py`
- Add `mcp` optional dependency: `mcp>=1.0.0` in pyproject.toml
- Add `--mcp` flag to CLI (enables MCP server alongside HTTP)
- Add `--mcp-config` flag (exposes full config resource)

### Task 2: Implement listening session manager

**File:** `src/ziomek/mcp/listening.py`

**Class: `ListeningSession`**
- `start(engine, model)` — create STTEngine, start recording
- `stop()` — stop recording, shut down engine
- `get_result()` — return latest transcription result
- `is_active` — property, True if recording

**Implementation:**
- Wraps existing `STTEngine` class from `ziomek.stt`
- Thread-safe: uses `threading.Lock` for state access
- Stores latest `STTResult` from callback
- `get_result()` returns `{text, is_final, state}` dict

**Dependencies:**
- Uses existing `ziomek.stt.STTEngine`, `STTResult`, `STTState`
- No new dependencies

### Task 3: Implement tools

**File:** `src/ziomek/mcp/tools.py`

**Tools (using MCP Python SDK):**

```python
from mcp.server.lowlevel import Server
from mcp.types import Tool

def register_tools(server: Server) -> None:
    @server.tool()
    async def speak(text: str, voice: str = "default") -> str:
        """Synthesize speech and play through ziomek audio player.
        
        Args:
            text: Text to speak.
            voice: Voice name (default: cosette).
        """
        ...

    @server.tool()
    async def transcribe(audio_b64: str, sample_rate: int = 16000) -> str:
        """Transcribe audio (base64 WAV) to text.
        
        Args:
            audio_b64: Base64-encoded WAV audio.
            sample_rate: Sample rate (default: 16000).
        """
        ...

    @server.tool()
    async def start_listening(engine: str = "faster_whisper", model: str = "tiny") -> str:
        """Start continuous listening from the microphone (hands-free mode).
        
        The server will capture audio from the default microphone and
        transcribe in real-time. Call get_transcription() every ~2 seconds
        to retrieve new results. Call stop_listening() when done.
        
        Args:
            engine: STT engine (default: faster_whisper).
            model: STT model (default: tiny).
        """
        ...

    @server.tool()
    async def get_transcription() -> str:
        """Get the latest transcription result from continuous listening.
        
        Call this every ~2 seconds after start_listening() to get new results.
        Returns the latest text and whether it is a final transcription.
        
        Returns:
            JSON string with text, is_final, and state fields.
        """
        ...

    @server.tool()
    async def stop_listening() -> str:
        """Stop continuous listening mode.
        
        Shuts down the microphone recording thread.
        """
        ...

    @server.tool()
    async def set_expression(expression: str, duration_ms: int | None = None) -> str:
        """Set the avatar expression.
        
        Args:
            expression: Expression name (e.g. happy, sad, neutral).
            duration_ms: Duration in ms (optional, permanent if omitted).
        """
        ...

    @server.tool()
    async def get_expression() -> str:
        """Get the current avatar expression and state."""
        ...

    @server.tool()
    async def status() -> str:
        """Get server status including TTS readiness, STT state, uptime, and audio backend."""
        ...
```

**Implementation details:**
- Each tool calls existing ziomek modules directly (no HTTP)
- `speak()` → `ziomek.tts.generate.generate_wav()` + `ziomek.server._audio_player.play()`
- `transcribe()` → `ziomek.stt.STTEngine.transcribe_chunk()`
- `start_listening()` → creates `ListeningSession`, starts recording
- `get_transcription()` → returns latest result from session
- `stop_listening()` → stops session, shuts down recorder
- `set_expression()` → `ziomek.server._state_machine.setExpression()`
- `get_expression()` → `ziomek.server._state_machine.tick()`
- `status()` → combines TTS status, STT status, uptime, audio backend info

**Return format:** All tools return JSON strings (MCP convention).

### Task 4: Implement resources

**File:** `src/ziomek/mcp/resources.py`

**Resources:**

```python
def register_resources(server: Server, expose_full_config: bool = False) -> None:
    @server.resource("voices://")
    async def get_voices() -> str:
        """List available PocketTTS voices."""
        ...

    @server.resource("models://")
    async def get_models() -> str:
        """List available faster-whisper STT models."""
        ...

    @server.resource("expressions://")
    async def get_expressions() -> str:
        """List available avatar expressions."""
        ...

    @server.resource("config://")
    async def get_config() -> str:
        """Server configuration.
        
        Read-only by default. Use --mcp-config to expose full config.
        """
        ...
```

**Implementation details:**
- `voices://` → returns list of voices from `ziomek.server._tts_model` or hardcoded list
- `models://` → returns `AVAILABLE_MODELS` from `ziomek.api.stt`
- `expressions://` → returns expressions from `ziomek.avatar.state_machine`
- `config://` → returns sanitized config (redact sensitive fields by default)

### Task 5: Wire MCP into server.py

**File:** `src/ziomek/server.py`

**Changes:**
- Add `mcp_enabled: bool = False` parameter to `create_app()`
- Add `mcp_config_exposed: bool = False` parameter
- When `mcp_enabled`, start MCP server alongside HTTP server
- MCP server runs in its own thread
- Graceful shutdown: stop MCP server on exit

**Implementation:**
```python
def create_app(mcp_enabled: bool = False, mcp_config_exposed: bool = False) -> FastAPI:
    ...
    if mcp_enabled:
        from ziomek.mcp import start_mcp_server
        threading.Thread(
            target=start_mcp_server,
            args=(mcp_config_exposed,),
            daemon=True,
        ).start()
    ...
```

**CLI:**
```python
# cli.py
parser.add_argument("--mcp", action="store_true", help="Enable MCP server alongside HTTP server")
parser.add_argument("--mcp-config", action="store_true", help="Expose full config via MCP (default: read-only)")
```

### Task 6: Create MCP server factory

**File:** `src/ziomek/mcp/__init__.py`

```python
"""ziomek MCP server — embedded alongside FastAPI HTTP server."""

from __future__ import annotations

import threading
from mcp.server.lowlevel import Server

from .tools import register_tools
from .resources import register_resources


def start_mcp_server(expose_full_config: bool = False) -> None:
    """Start the MCP server (runs in a separate thread)."""
    mcp_server = Server("ziomek-mcp")
    
    register_tools(mcp_server)
    register_resources(mcp_server, expose_full_config)
    
    # Start MCP server via stdio
    from mcp.server import ServerTransport
    # MCP uses stdio transport by default
    import asyncio
    asyncio.run(mcp_server.serve())


def get_mcp_server(expose_full_config: bool = False):
    """Get the MCP server instance (for testing)."""
    mcp_server = Server("ziomek-mcp")
    register_tools(mcp_server)
    register_resources(mcp_server, expose_full_config)
    return mcp_server
```

### Task 7: Tests

**File:** `tests/test_mcp_tools.py` — Tool tests
**File:** `tests/test_mcp_resources.py` — Resource tests
**File:** `tests/test_mcp_listening.py` — Listening session tests

**Tool tests:**
- `test_speak_calls_generate_wav_and_play` — mock TTS model, verify audio_player.play called
- `test_transcribe_calls_stt_engine` — mock STTEngine, verify transcribe_chunk called
- `test_set_expression_calls_state_machine` — mock state machine, verify setExpression called
- `test_get_expression_returns_current_state` — verify state machine tick called
- `test_status_returns_combined_info` — verify TTS + STT + uptime info

**Resource tests:**
- `test_voices_returns_voice_list` — verify voices list
- `test_models_returns_model_list` — verify models list
- `test_expressions_returns_expression_list` — verify expressions list
- `test_config_returns_readonly_by_default` — verify sensitive fields redacted
- `test_config_returns_full_with_flag` — verify full config exposed

**Listening tests:**
- `test_listening_session_start` — verify recorder starts
- `test_listening_session_stop` — verify recorder stops
- `test_listening_session_get_result` — verify latest result returned
- `test_listening_session_is_active` — verify active state tracking

### Task 8: Documentation

- Update README.md with MCP section
- Add MCP usage examples
- Update TODO.md

---

## Dependencies

- `mcp>=1.0.0` — Python MCP SDK by Anthropic (optional extra)
- No other new dependencies

## CLI Usage

```bash
# Enable MCP alongside HTTP server
uv run ziomek --mcp

# Enable MCP with full config exposure
uv run ziomek --mcp --mcp-config
```

## Verification

- All existing tests pass (162+)
- New MCP tests pass (10+)
- Full suite: 175+ tests
