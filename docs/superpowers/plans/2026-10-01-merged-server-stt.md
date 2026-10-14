# Merged Server & STT Integration Plan

> **Goal:** Merge ziomek client into ziomek server (single process), add RealtimeSTT speech-to-text, rename config, merge CLI into one command.
> **Architecture:** One `ziomek` binary on port 5004 that does everything — TTS, STT, avatar, gamepad, HTML serving, WebSocket relay.
> **Tech Stack:** Python 3.10+, FastAPI, uvicorn, RealtimeSTT (whisper-cpp default), PocketTTS, pygame-ce.

## Global Constraints

- Commit after every task with Conventional Commits format and `--signoff`.
- Use `uv run` for all Python execution; never install packages globally.
- NEVER use `git add -f` for ignored files.
- NEVER kill `python.exe` (LLM runs inside it).
- Respect `.gitattributes` and line endings; do not "fix" valid ones.
- All new code must have tests; all tests must pass before committing.
- Default port: 5004 (client's port, not server's old 5003).
- New dependency: `RealtimeSTT[whisper-cpp]` (optional extra, installed only when STT features are needed).

## Review Focus

- **Merge safety:** All existing server + client functionality must be preserved after merge.
- **STT integration:** RealtimeSTT must start/stop cleanly, handle mic errors gracefully, and not block the main event loop.
- **Config migration:** `ziomek_server_config.yaml` → `ziomek_config.yaml` with backward compatibility (old name still works).
- **CLI merge:** All existing CLI args must still work; new args added at top level.

---

## Task 1: Add STT Module

**Files:**
- Create: `src/ziomek/stt.py` — STT engine wrapper
- Modify: `pyproject.toml` — add `RealtimeSTT[whisper-cpp]` as optional dependency

**Interfaces:**
- Produces: `ziomek.stt.STTEngine` class with `start()`, `stop()`, `transcribe_chunk()`, `get_state()` methods
- Produces: `ziomek.stt.download_model()` function for auto-downloading whisper.cpp models

- [ ] **Step 1: Add RealtimeSTT as optional dependency**

In `pyproject.toml`, add:
```toml
[project.optional-dependencies]
stt = ["RealtimeSTT[whisper-cpp]>=0.4"]
```

- [ ] **Step 2: Write STT engine test**

In `tests/test_stt.py`:
```python
import pytest
from ziomek.stt import STTEngine, STTState

def test_stt_engine_initialization():
    engine = STTEngine()
    assert engine.state == STTState.IDLE
    assert engine.engine_name == "whisper_cpp"
    assert engine.model_name == "tiny.en"

def test_stt_engine_start_stop():
    engine = STTEngine()
    engine.start()
    assert engine.state == STTState.LISTENING
    engine.stop()
    assert engine.state == STTState.IDLE
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_stt.py -v`
Expected: FAIL — module doesn't exist yet

- [ ] **Step 4: Implement STTEngine class**

Create `src/ziomek/stt.py`:
```python
"""ziomek STT — speech-to-text using RealtimeSTT."""

from __future__ import annotations

import enum
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class STTState(enum.Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"


@dataclass
class STTResult:
    """A transcription result."""
    text: str
    is_final: bool
    realtime: bool = False


@dataclass
class STTStats:
    """Runtime stats for the STT engine."""
    state: STTState = STTState.IDLE
    engine_name: str = "whisper_cpp"
    model_name: str = "tiny.en"
    last_text: str = ""
    last_is_final: bool = False
    transcription_count: int = 0


class STTEngine:
    """Wraps RealtimeSTT's AudioToTextRecorder for server-side speech recognition."""

    def __init__(
        self,
        engine_name: str = "whisper_cpp",
        model_name: str = "tiny.en",
        model_dir: str | None = None,
        on_transcription: Callable[[STTResult], None] | None = None,
    ) -> None:
        self._engine_name = engine_name
        self._model_name = model_name
        self._model_dir = model_dir
        self._on_transcription = on_transcription
        self._recorder = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._stats = STTStats(
            engine_name=engine_name,
            model_name=model_name,
        )
        self._lock = threading.Lock()

    @property
    def stats(self) -> STTStats:
        with self._lock:
            return STTStats(**self._stats.__dict__)

    @property
    def state(self) -> STTState:
        return self._stats.state

    def start(self) -> None:
        """Start the STT engine (blocking call — runs in background thread)."""
        try:
            from RealtimeSTT import AudioToTextRecorder
        except ImportError:
            logger.error("RealtimeSTT not installed. Install with: pip install RealtimeSTT[whisper-cpp]")
            return

        if self._model_dir:
            kwargs = {"download_root": self._model_dir}
        else:
            kwargs = {}

        self._recorder = AudioToTextRecorder(
            transcription_engine=self._engine_name,
            model=self._model_name,
            device="cpu",
            enable_realtime_transcription=True,
            realtime_model_type="tiny.en",
            beam_size_realtime=1,
            **kwargs,
        )

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the STT engine."""
        self._running = False
        if self._recorder:
            self._recorder.shutdown()
            self._recorder = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        with self._lock:
            self._stats.state = STTState.IDLE

    def transcribe_chunk(self, audio_data: bytes, sample_rate: int = 16000) -> STTResult:
        """Transcribe a single audio chunk (non-streaming mode)."""
        if self._recorder is None:
            return STTResult(text="", is_final=True, realtime=False)
        self._recorder.feed_audio(audio_data, original_sample_rate=sample_rate)
        return STTResult(text=self._recorder.text(), is_final=True, realtime=False)

    def _listen_loop(self) -> None:
        """Background loop that listens for speech and calls the transcription callback."""
        with self._lock:
            self._stats.state = STTState.LISTENING

        def on_realtime(text: str) -> None:
            with self._lock:
                self._stats.last_text = text
                self._stats.last_is_final = False
            if self._on_transcription:
                self._on_transcription(STTResult(text=text, is_final=False, realtime=True))

        def on_final(text: str) -> None:
            with self._lock:
                self._stats.last_text = text
                self._stats.last_is_final = True
                self._stats.transcription_count += 1
            if self._on_transcription:
                self._on_transcription(STTResult(text=text, is_final=True, realtime=False))

        if self._recorder:
            self._recorder.on_realtime_transcription_update = on_realtime
            # RealtimeSTT doesn't have a direct "on final" callback — we poll text() in the loop

        while self._running and self._recorder:
            try:
                text = self._recorder.text()
                if text:
                    on_final(text)
            except Exception:
                logger.exception("STT transcription error")
                break

        with self._lock:
            self._stats.state = STTState.IDLE

    def shutdown(self) -> None:
        """Alias for stop() — cleanup."""
        self.stop()


def download_model(model_name: str = "tiny.en", download_root: str | None = None) -> Path:
    """Download a whisper.cpp model file. Returns path to downloaded model."""
    from pywhispercpp import model as whisper_model

    if download_root:
        Path(download_root).mkdir(parents=True, exist_ok=True)
        return whisper_model.download(model_name, models_dir=download_root)
    else:
        return whisper_model.download(model_name)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_stt.py -v`
Expected: PASS (if RealtimeSTT is installed) or SKIP (if not)

- [ ] **Step 6: Commit**

```bash
git add src/ziomek/stt.py pyproject.toml tests/test_stt.py
git commit -m "feat(stt): add STT engine module with RealtimeSTT integration" --signoff
```

---

## Task 2: Merge Client into Server

**Files:**
- Modify: `src/ziomek/server.py` — absorb client logic (HTML serving, WebSocket relay, gamepad)
- Modify: `src/ziomek/api/avatar.py` — update route paths and references
- Move: `src/ziomek/client/resources/renderer.html` → keep in place, update import path in avatar.py

**Interfaces:**
- Consumes: Existing server routes and state machine
- Produces: Single FastAPI app with all functionality (TTS, STT, avatar, gamepad, HTML, WebSocket)

- [ ] **Step 1: Move HTML renderer path reference**

In `src/ziomek/api/avatar.py`, the `_renderer_html` path already resolves correctly since it's `Path(__file__).parent.parent / "client" / "resources" / "renderer.html"` — this still works after merge since the file stays in place.

- [ ] **Step 2: Add HTML serving route to server**

In `src/ziomek/server.py`, add a route in `create_app()`:
```python
@router.get("/")
async def root_html():
    """Serve the avatar renderer HTML page."""
    from fastapi.responses import HTMLResponse
    from pathlib import Path
    renderer_html = Path(__file__).parent / "client" / "resources" / "renderer.html"
    if renderer_html.exists():
        return HTMLResponse(content=renderer_html.read_text())
    return HTMLResponse(content="<html><body>ziomek</body></html>", status_code=200)
```

- [ ] **Step 3: Add gamepad polling thread to server**

In `src/ziomek/server.py`, import `GamepadManager` from `ziomek.client.gamepad` and add the gamepad polling thread to the server startup (same logic as client's `_start_gamepad_thread`).

- [ ] **Step 4: Add WebSocket relay to VS Code**

In `src/ziomek/server.py`, add a WebSocket endpoint:
```python
from fastapi import WebSocket

@router.websocket("/api/avatar/ws")
async def avatar_websocket(websocket: WebSocket):
    """WebSocket relay for VS Code extension — sends avatar state updates."""
    await websocket.accept()
    try:
        from ziomek.server import _state_machine
        last_expr = ""
        last_cycle = -1
        while True:
            state = _state_machine.tick(16)
            if state.expressionName != last_expr or state.cycleIndex != last_cycle:
                await websocket.send_json({
                    "expression": state.expressionName,
                    "cycleIndex": state.cycleIndex,
                })
                last_expr = state.expressionName
                last_cycle = state.cycleIndex
            await asyncio.sleep(0.01)
    except Exception:
        logger.exception("avatar_ws: error in WebSocket loop")
```

- [ ] **Step 5: Add STT WebSocket endpoint**

In `src/ziomek/server.py`, add:
```python
@router.websocket("/api/stt/stream")
async def stt_websocket(websocket: WebSocket):
    """WebSocket for real-time STT transcription updates."""
    await websocket.accept()
    try:
        from ziomek.server import _stt_engine
        while True:
            if _stt_engine and _stt_engine.stats.state != STTState.IDLE:
                await websocket.send_json({
                    "type": "transcription",
                    "text": _stt_engine.stats.last_text,
                    "is_final": _stt_engine.stats.last_is_final,
                    "realtime": not _stt_engine.stats.last_is_final,
                })
            await asyncio.sleep(0.05)
    except Exception:
        logger.exception("stt_ws: error in WebSocket loop")
```

- [ ] **Step 6: Initialize STT engine in create_app()**

In `create_app()`, add:
```python
from ziomek.stt import STTEngine, STTState

def _on_transcription(result) -> None:
    # Broadcast to connected STT WebSocket clients
    pass

_stt_engine = STTEngine(
    engine_name=settings.stt_engine,
    model_name=settings.stt_model,
    model_dir=settings.stt_model_dir,
    on_transcription=_on_transcription,
)
```

- [ ] **Step 7: Remove client-only code**

The client's `server.py` and `cli.py` are no longer needed — their functionality is absorbed into the server.

- [ ] **Step 8: Run existing tests**

Run: `uv run pytest -v`
Expected: All existing tests still pass

- [ ] **Step 9: Commit**

```bash
git add src/ziomek/server.py src/ziomek/api/avatar.py tests/test_stt.py
git commit -m "feat(server): merge client into server — single process with HTML, WebSocket, gamepad" --signoff
```

---

## Task 3: Merge CLI and Rename Config

**Files:**
- Modify: `src/ziomek/cli.py` — merge into single command, add new args
- Modify: `src/ziomek/config.py` — rename config file, add new fields
- Modify: `src/ziomek/__main__.py` — update entry point

**Interfaces:**
- Consumes: Existing CLI args and config loading
- Produces: Single `ziomek` command with all args at top level

- [ ] **Step 1: Add new Settings fields**

In `src/ziomek/config.py`, add:
```python
no_vscode: bool = False
no_browser: bool = False
stt_engine: str = "whisper_cpp"
stt_model: str = "tiny.en"
stt_model_dir: str | None = None
```

- [ ] **Step 2: Update scaffold_config**

Change the default config filename from `ziomek_server_config.yaml` to `ziomek_config.yaml` and update the comment header.

- [ ] **Step 3: Rewrite CLI**

Replace the entire `cli.py` with a merged single-command version:
```python
"""ziomek CLI — unified command-line interface.

Usage:
    ziomek [options]   # Start ziomek (single process, port 5004)
"""

import argparse
from importlib.metadata import version as get_version
import sys

from ziomek.server import run_server


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ziomek",
        description="ziomek — Humanize AI (TTS, STT, avatar, gamepad)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {get_version('ziomek')}")

    # Server args
    parser.add_argument("--port", type=int, default=5004, help="HTTP/WebSocket port (default: 5004)")
    parser.add_argument("--host", type=str, default=None, help="Host to bind (default: localhost)")
    parser.add_argument("--model-path", type=str, default=None, help="TTS model path")
    parser.add_argument("--voice", type=str, default="default", help="TTS voice")
    parser.add_argument("--cache-dir", type=str, default=None, help="Voice cache directory")
    parser.add_argument(
        "--audio-backend",
        type=str,
        default=None,
        help="Audio playback backend (sounddevice, pygame, pyaudio, playsound, noop)",
    )
    parser.add_argument(
        "--audio-device",
        type=str,
        default=None,
        help="Audio device index, name, or 'default'",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # Client args
    parser.add_argument("--no-vscode", action="store_true", help="Disable VS Code WebSocket relay")
    parser.add_argument("--no-browser", action="store_true", help="Do not open local browser")

    # STT args
    parser.add_argument(
        "--stt-engine",
        type=str,
        default=None,
        help="STT engine (whisper_cpp, faster_whisper)",
    )
    parser.add_argument(
        "--stt-model",
        type=str,
        default=None,
        help="STT model (tiny.en, base.en, small.en)",
    )
    parser.add_argument(
        "--stt-model-dir",
        type=str,
        default=None,
        help="STT model download directory",
    )

    # Config scaffold
    parser.add_argument(
        "--scaffold-config",
        action="store_true",
        help="Create a default ziomek_config.yaml and exit",
    )

    args = parser.parse_args()

    if args.scaffold_config:
        from ziomek.config import Settings
        path = Settings.scaffold_config("ziomek_config.yaml")
        print(f"Config file created at {path}")
        return

    run_server(
        port=args.port,
        model_path=args.model_path,
        voice=args.voice,
        cache_dir=args.cache_dir,
        audio_backend=args.audio_backend,
        audio_device=args.audio_device,
        host=args.host,
        log_level=args.log_level,
        no_vscode=args.no_vscode,
        no_browser=args.no_browser,
        stt_engine=args.stt_engine,
        stt_model=args.stt_model,
        stt_model_dir=args.stt_model_dir,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Update `__main__.py`**

In `src/ziomek/__main__.py`:
```python
from ziomek.cli import main

main()
```

- [ ] **Step 5: Update scaffold_config in config.py**

Change the default filename and comment:
```python
content = """# ziomek configuration
# Generate with: ziomek --scaffold-config

# Audio playback backend (sounddevice, pygame, pyaudio, playsound, noop)
audio_backend: sounddevice

# Audio device (None/default = system default, or int index, or device name string)
# audio_device:

# Server settings
# port: 5004
# host: localhost
# model_path:
# voice: default
# cache_dir:

# STT settings
# stt_engine: whisper_cpp
# stt_model: tiny.en
# stt_model_dir:
"""
```

- [ ] **Step 6: Add backward compatibility for old config name**

In `Settings.load()`, try both `ziomek_config.yaml` and `ziomek_server_config.yaml`:
```python
@classmethod
def load(cls, config_path: str | Path | None = None) -> "Settings":
    # Try explicit path first, then default names
    if config_path:
        return cls._load_file(config_path) or cls()
    # Try new name, then old name for backward compatibility
    for name in ["ziomek_config.yaml", "ziomek_server_config.yaml"]:
        for base in [Path.cwd(), Path.home() / ".ziomek"]:
            path = base / name
            result = cls._load_file(path)
            if result != cls():
                return result
    return cls()

@classmethod
def _load_file(cls, path: Path) -> "Settings | None":
    path = path.resolve()
    allowed = {Path.cwd().resolve(), Path.home().resolve()}
    if not any(path.is_relative_to(a) or path == a for a in allowed):
        return None
    if not path.is_file():
        return None
    try:
        import yaml
    except ImportError:
        return None
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except OSError:
        return None
    known = {k: v for k, v in data.items() if k in cls.model_fields}
    return cls(**known)
```

- [ ] **Step 7: Update `run_server()` signature**

In `src/ziomek/server.py`, update `run_server()` to accept the new args and pass them through:
```python
def run_server(
    port=5004,
    model_path=None,
    voice="default",
    cache_dir=None,
    audio_backend=None,
    audio_device=None,
    host=None,
    log_level="INFO",
    no_vscode=False,
    no_browser=False,
    stt_engine=None,
    stt_model=None,
    stt_model_dir=None,
):
    settings = Settings.compose(
        cli_backend=audio_backend,
        cli_device=audio_device,
        cli_host=host,
        port=port,
        model_path=model_path,
        voice=voice,
        cache_dir=cache_dir,
        no_vscode=no_vscode,
        stt_engine=stt_engine,
        stt_model=stt_model,
        stt_model_dir=stt_model_dir,
    )
    setup_logging(level=log_level)
    app = create_app(settings)

    # Open browser if not disabled
    if not no_browser:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{settings.port}/")

    print(f"ziomek listening on http://{settings.host}:{settings.port}", file=sys.stderr)
    uvicorn.run(app, host=settings.host, port=settings.port)
```

- [ ] **Step 8: Run tests**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 9: Commit**

```bash
git add src/ziomek/cli.py src/ziomek/config.py src/ziomek/server.py src/ziomek/__main__.py
git commit -m "refactor: merge CLI into single command and rename config to ziomek_config.yaml" --signoff
```

---

## Task 4: Remove Client Directory & Clean Up

**Files:**
- Delete: `src/ziomek/client/server.py`
- Delete: `src/ziomek/client/cli.py`
- Keep: `src/ziomek/client/gamepad.py` (moved reference in server)
- Keep: `src/ziomek/client/resources/renderer.html` (still used by avatar.py)
- Modify: `src/ziomek/api/avatar.py` — update `_renderer_html` path
- Modify: `src/ziomek/server.py` — import gamepad from correct path

**Interfaces:**
- Consumes: No external dependencies
- Produces: Clean directory structure with no dead code

- [ ] **Step 1: Move gamepad module**

Move `src/ziomek/client/gamepad.py` → `src/ziomek/gamepad.py` and update imports.

- [ ] **Step 2: Update avatar.py renderer path**

Change `_renderer_html` to:
```python
_renderer_html = Path(__file__).parent.parent / "client" / "resources" / "renderer.html"
```
(This already works since the file stays in place.)

- [ ] **Step 3: Delete client server.py and cli.py**

- [ ] **Step 4: Update server.py gamepad import**

Change `from ziomek.client.gamepad import GamepadManager` → `from ziomek.gamepad import GamepadManager`

- [ ] **Step 5: Run tests**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/ziomek/server.py src/ziomek/api/avatar.py src/ziomek/gamepad.py
git rm src/ziomek/client/server.py src/ziomek/client/cli.py
git commit -m "refactor: remove client directory, move gamepad to root package" --signoff
```

---

## Task 5: Update Documentation & Verification

**Files:**
- Modify: `README.md` — update CLI examples
- Modify: `docs/internal/TODO.md` — mark items as done
- Modify: `CHANGELOG.md` — add merged server entry

- [ ] **Step 1: Update README CLI examples**

Change all `ziomek server` references to `ziomek` and add new args:
```bash
ziomek --port 5004 --voice cosette --cache-dir ./voices --no-browser
ziomek --stt-engine whisper_cpp --stt-model tiny.en
ziomek --scaffold-config
```

- [ ] **Step 2: Update TODO.md**

Mark as done:
- [x] Configuration file support (client)
- [x] Listen and answer (RealtimeSTT + whisper.cpp)

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add README.md docs/internal/TODO.md CHANGELOG.md
git commit -m "docs: update CLI examples and mark merged server + STT tasks done" --signoff
```
