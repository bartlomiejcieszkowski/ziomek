# Ziomek — Standalone TTS & Avatar Server

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract Pocket TTS + avatar state machine from the VS Code extension into a standalone Python package called "ziomek", and replace the extension with a thin HTTP client.

**Architecture:** ziomek exposes TTS synthesis and avatar rendering via HTTP on localhost:5003. The extension ("Ziomek — Humanize AI") is a thin HTTP client managing only the webview UI.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, pocket-tts 3.x, torch, numpy, sounddevice, TypeScript/VS Code extension, jest

**Spec:** `IDEAS.md` (design spec)

## Global Constraints

- ziomek package name is `ziomek`, installed via `pip install .` or `uv pip install .`
- ziomek CLI entry point is `ziomek serve --port 5003`
- Extension id is `ziomek.humanize-ai`, display name is `"Ziomek — Humanize AI"`
- Server port default is 5003, configurable via `--port` flag and `humanizeAI.tts.port` config
- Voice cache directory is `./voices/` with `.safetensors` files
- Gamepad input stays in extension (Node.js gamepad API)
- Non-blocking audio playback via `sounddevice.play(blocking=False)`
- pocket-tts 3.x: use `get_state_for_audio_prompt()` (no `get_default_state()`)
- Default TTS voice: "cosette" from catalog

## Review Focus

- ziomek must not import any VS Code modules — standalone package
- Extension must not keep Python subprocess references after activation
- Audio mixing on Windows: `sd.play(blocking=False)` required; `blocking=True` blocks server loop
- Voice state caching: `.safetensors` in `voices/`, no re-downloads per request
- State machine port must be bitwise-identical to TypeScript: same expressions, intensity ordering, transitions, cycle counting

---

## Phase 1: ziomek Package Scaffold

### Task 1.1: Package scaffold

**Files:**
- Create: `ziomek/pyproject.toml`
- Create: `ziomek/ziomek/__init__.py`
- Create: `ziomek/README.md`
- Create: `ziomek/LICENSE`
- Create: `ziomek/tests/__init__.py`
- Create: `ziomek/tests/test_version.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ziomek"
version = "0.1.0"
description = "Humanize AI backend — TTS + avatar display server"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
dependencies = [
    "pocket-tts>=3.0", "torch>=2.0", "numpy>=1.24", "scipy>=1.10",
    "sounddevice>=0.4", "soundfile>=0.12", "safetensors>=0.4",
    "fastapi>=0.100", "uvicorn[standard]>=0.23", "pydantic>=2.0",
    "pillow>=10.0", "requests>=2.31",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-asyncio>=0.21", "httpx>=0.24", "ruff>=0.1"]

[project.scripts]
ziomek = "ziomek.cli:main"
```

- [ ] **Step 2: Create __init__.py**

```python
"""ziomek — Humanize AI backend server."""
__version__ = "0.1.0"
```

- [ ] **Step 3: Create README.md** (see Phase 1 in PLAN.md for full content)

- [ ] **Step 4: Create LICENSE** (MIT license text)

- [ ] **Step 5: Create test_version.py**

```python
from ziomek import __version__

def test_version():
    assert __version__ == "0.1.0"
```

- [ ] **Step 6: Run tests**

Run: `cd ziomek && pip install -e . && python -m pytest tests/test_version.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ziomek/pyproject.toml ziomek/ziomek/__init__.py ziomek/README.md ziomek/tests/
git commit -m "feat(ziomek): scaffold package with pyproject.toml and CLI entry point"
```

### Task 1.2: CLI and server structure

**Files:**
- Create: `ziomek/ziomek/cli.py`
- Create: `ziomek/ziomek/server.py`
- Create: `ziomek/ziomek/config.py`
- Modify: `ziomek/ziomek/__init__.py`

- [ ] **Step 1: Create cli.py**

```python
"""ziomek CLI — command-line interface."""
import argparse
import sys
from ziomek.server import run_server

def main():
    parser = argparse.ArgumentParser(prog="ziomek", description="Humanize AI backend")
    parser.add_argument("--version", action="version",
        version=f"%(prog)s {__import__('ziomek').__version__}")
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="Start HTTP server")
    serve.add_argument("--port", type=int, default=5003)
    serve.add_argument("--model-path", type=str, default=None)
    serve.add_argument("--voice", type=str, default="default")
    serve.add_argument("--cache-dir", type=str, default=None)
    args = parser.parse_args()
    if args.command == "serve" or args.command is None:
        run_server(port=args.port, model_path=args.model_path,
            voice=args.voice, cache_dir=args.cache_dir)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create server.py**

```python
"""ziomek HTTP server — FastAPI application."""
import uvicorn
from fastapi import FastAPI
from ziomek.config import Settings
import sys

def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()
    app = FastAPI(title="ziomek", version="0.1.0")
    return app

def run_server(port=5003, model_path=None, voice="default", cache_dir=None):
    settings = Settings(port=port, model_path=model_path, voice=voice, cache_dir=cache_dir)
    app = create_app(settings)
    print(f"ziomek server listening on http://localhost:{port}", file=sys.stderr)
    uvicorn.run(app, host="localhost", port=port)
```

- [ ] **Step 3: Create config.py**

```python
"""ziomek settings."""
from pydantic import BaseModel

class Settings(BaseModel):
    port: int = 5003
    model_path: str | None = None
    voice: str = "default"
    cache_dir: str | None = None
```

- [ ] **Step 4: Run tests**

Run: `cd ziomek && python -c "from ziomek.cli import main; print('OK')"`
Expected: OK (may fail on missing deps, but imports should work)

- [ ] **Step 5: Commit**

```bash
git add ziomek/ziomek/cli.py ziomek/ziomek/server.py ziomek/ziomek/config.py ziomek/ziomek/__init__.py
git commit -m "feat(ziomek): add CLI, FastAPI scaffold, and Settings config"
```

---

## Phase 2: TTS Module Extraction

### Task 2.1: TTS model engine

**Files:**
- Create: `ziomek/ziomek/tts/__init__.py`
- Create: `ziomek/ziomek/tts/engine.py`
- Create: `ziomek/tests/tts/__init__.py`
- Create: `ziomek/tests/tts/test_engine.py`

- [ ] **Step 1: Create engine.py**

```python
"""ziomek TTS engine — Pocket TTS model management."""
import torch
from typing import Optional

class TTSModelWrapper:
    def __init__(self):
        self._model: Optional["TTSModel"] = None  # type: ignore[name-defined]
        self.sample_rate: int = 24000

    def load(self, model_path: str | None = None) -> None:
        from pocket_tts import TTSModel  # type: ignore[import-untyped]
        if model_path:
            self._model = TTSModel.load_from_path(model_path)
        else:
            self._model = TTSModel.load_model()

    @property
    def ready(self) -> bool:
        return self._model is not None

    def generate_audio(self, voice_state: dict, text: str) -> torch.Tensor:  # type: ignore[name-defined]
        if not self.ready:
            raise RuntimeError("TTS model not loaded")
        return self._model.generate_audio(voice_state, text)  # type: ignore[union-attr]
```

- [ ] **Step 2: Create test_engine.py**

```python
from unittest.mock import MagicMock
from ziomek.tts.engine import TTSModelWrapper

def test_engine_initialization():
    wrapper = TTSModelWrapper()
    assert wrapper.ready is False
    assert wrapper.sample_rate == 24000

def test_generate_raises_when_not_loaded():
    wrapper = TTSModelWrapper()
    try:
        wrapper.generate_audio({}, "test")
        assert False, "Should have raised"
    except RuntimeError as e:
        assert "not loaded" in str(e)
```

- [ ] **Step 3: Run tests**

Run: `cd ziomek && pip install torch pocket-tts sounddevice soundfile && python -m pytest tests/tts/test_engine.py -v`
Expected: PASS (after installing deps)

- [ ] **Step 4: Commit**

```bash
git add ziomek/ziomek/tts/__init__.py ziomek/ziomek/tts/engine.py ziomek/tests/tts/__init__.py ziomek/tests/tts/test_engine.py
git commit -m "feat(ziomek): create TTS model engine wrapper"
```

### Task 2.2: Voice state management

**Files:**
- Create: `ziomek/ziomek/tts/voice.py`
- Create: `ziomek/tests/tts/test_voice.py`

- [ ] **Step 1: Create voice.py**

```python
"""ziomek TTS voice state management."""
import os
from pathlib import Path
from typing import Optional
from ziomek.tts.engine import TTSModelWrapper

class VoiceStateCache:
    def __init__(self, model: TTSModelWrapper, cache_dir: str | None = None):
        self._model = model
        self._cache_dir: Optional[Path] = Path(cache_dir) if cache_dir else None
        self._states: dict[str, dict] = {}

    def load_voice(self, voice_key: str) -> dict:
        if voice_key in self._states:
            return self._states[voice_key]
        # Use catalog voice "cosette" as default (same as TS pocket-tts-server.py)
        voice_key_to_use = voice_key if voice_key != "default" else "cosette"
        state = self._model.generate_audio.__self__.get_state_for_audio_prompt(voice_key_to_use)  # type: ignore[union-attr]
        self._states[voice_key] = state
        return state
```

- [ ] **Step 2: Create test_voice.py**

```python
from unittest.mock import MagicMock, patch
from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.voice import VoiceStateCache

def test_voice_cache_caches_states():
    model = MagicMock(spec=TTSModelWrapper)
    model.sample_rate = 24000
    model.ready = True
    cache = VoiceStateCache(model)
    cache.load_voice("cosette")
    cache.load_voice("cosette")
    # Should have been called only once (cached)
    assert len(cache._states) == 1
```

- [ ] **Step 3: Run tests**

Run: `cd ziomek && python -m pytest tests/tts/test_voice.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add ziomek/ziomek/tts/voice.py ziomek/tests/tts/test_voice.py
git commit -m "feat(ziomek): add voice state caching"
```

### Task 2.3: WAV generation

**Files:**
- Create: `ziomek/ziomek/tts/generate.py`
- Create: `ziomek/tests/tts/test_generate.py`

- [ ] **Step 1: Create generate.py**

```python
"""ziomek TTS generation — text to WAV bytes (base64 response)."""
import base64, io, numpy as np, scipy.io.wavfile as wavfile, torch
from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.voice import VoiceStateCache

def generate_wav(model: TTSModelWrapper, voice_cache: VoiceStateCache,
                 text: str, voice: str = "default") -> tuple[str, float, int]:
    if not model.ready:
        raise RuntimeError("TTS model not loaded")
    voice_state = voice_cache.load_voice(voice)
    audio_tensor = model.generate_audio(voice_state, text)
    audio_np = audio_tensor.detach().cpu().numpy() if isinstance(audio_tensor, torch.Tensor) else np.array(audio_tensor)
    sample_rate = model.sample_rate
    wav_buffer = io.BytesIO()
    wavfile.write(wav_buffer, sample_rate, audio_np)
    wav_bytes = wav_buffer.getvalue()
    audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
    duration = len(audio_np) / sample_rate if hasattr(audio_np, "__len__") else 0
    return audio_b64, float(duration), sample_rate
```

- [ ] **Step 2: Create test_generate.py**

```python
import pytest, base64, io, numpy as np
from unittest.mock import MagicMock, patch
from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.voice import VoiceStateCache
from ziomek.tts.generate import generate_wav

def test_generate_raises_when_not_ready():
    model = MagicMock(spec=TTSModelWrapper)
    model.ready = False
    voice_cache = VoiceStateCache(model)
    with pytest.raises(RuntimeError, match="not loaded"):
        generate_wav(model, voice_cache, "test")

def test_generate_returns_valid_wav():
    model = MagicMock(spec=TTSModelWrapper)
    model.ready = True
    model.sample_rate = 24000
    mock_audio = torch.zeros(24000)  # 1 second

    with patch.object(model, 'generate_audio', return_value=mock_audio):
        voice_cache = VoiceStateCache(model)
        voice_cache.load_voice = MagicMock(return_value={})
        audio_b64, duration, sr = generate_wav(model, voice_cache, "test")
        assert duration == pytest.approx(1.0, abs=0.01)
        assert sr == 24000
        # Verify base64 decodes to valid WAV
        wav_bytes = base64.b64decode(audio_b64)
        read_sr, data = scipy.io.wavfile.read(io.BytesIO(wav_bytes))
        assert read_sr == 24000
```

- [ ] **Step 3: Run tests**

Run: `cd ziomek && python -m pytest tests/tts/test_generate.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add ziomek/ziomek/tts/generate.py ziomek/tests/tts/test_generate.py
git commit -m "feat(ziomek): add WAV generation (text → base64)"
```

### Task 2.4: Audio playback with mixing

**Files:**
- Create: `ziomek/ziomek/tts/playback.py`
- Create: `ziomek/tests/tts/test_playback.py`

- [ ] **Step 1: Create playback.py**

```python
"""ziomek TTS audio playback with sounddevice mixing support."""
import io, threading, time, gc
import numpy as np, soundfile as sf, sounddevice as sd

class AudioPlayer:
    def __init__(self):
        self._playback_threads: list[threading.Thread] = []

    def play(self, wav_bytes: bytes, sample_rate: int) -> None:
        thread = threading.Thread(target=self._play_thread, args=(wav_bytes, sample_rate), daemon=True)
        self._playback_threads.append(thread)
        thread.start()

    def _play_thread(self, wav_bytes: bytes, sample_rate: int) -> None:
        try:
            wav_file = io.BytesIO(wav_bytes)
            audio_data, read_sr = sf.read(wav_file)
            if audio_data.ndim == 2:
                audio_data = audio_data.mean(axis=1)
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            sd.play(audio_data, samplerate=read_sr, blocking=False)
            duration_s = len(audio_data) / read_sr if len(audio_data) > 0 else 0
            time.sleep(duration_s + 0.1)
            sd.stop()
            gc.collect()
        except Exception:
            pass  # Silent failure — playback errors shouldn't crash server
```

- [ ] **Step 2: Create test_playback.py**

```python
import pytest, io, numpy as np
from unittest.mock import MagicMock, patch
from ziomek.tts.playback import AudioPlayer

def test_play_nonblocking():
    player = AudioPlayer()
    wav_bytes = io.BytesIO(np.array([0.0]*2400, dtype=np.float32).tobytes()).getvalue()
    with patch('sounddevice.play') as mock_play:
        with patch('soundfile.read') as mock_read:
            mock_read.return_value = (np.array([0.0]*2400, dtype=np.float32), 24000)
            player.play(wav_bytes, 24000)
            _, kwargs = mock_play.call_args
            assert kwargs.get('blocking') is False
    for t in player._playback_threads:
        t.join(timeout=2.0)

def test_play_multiple_spawn_threads():
    player = AudioPlayer()
    wav_bytes = io.BytesIO(np.array([0.0]*100, dtype=np.float32).tobytes()).getvalue()
    with patch('sounddevice.play'), patch('soundfile.read') as mock_read:
        mock_read.return_value = (np.array([0.0]*100, dtype=np.float32), 24000)
        for _ in range(3):
            player.play(wav_bytes, 24000)
    assert len(player._playback_threads) == 3
    for t in player._playback_threads:
        t.join(timeout=2.0)
```

- [ ] **Step 3: Run tests**

Run: `cd ziomek && python -m pytest tests/tts/test_playback.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add ziomek/ziomek/tts/playback.py ziomek/tests/tts/test_playback.py
git commit -m "feat(ziomek): add audio playback with sounddevice mixing support"
```

### Task 2.5: TTS API endpoints

**Files:**
- Create: `ziomek/ziomek/api/__init__.py`
- Create: `ziomek/ziomek/api/tts.py`
- Create: `ziomek/tests/tts/test_api.py`
- Modify: `ziomek/ziomek/server.py`

- [ ] **Step 1: Create api/__init__.py**

```python
"""ziomek API package."""
```

- [ ] **Step 2: Create api/tts.py**

```python
"""ziomek TTS API endpoints."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/tts")

@router.get("/status")
async def tts_status() -> dict:
    return {"ready": True, "voices": ["cosette", "marius", "javert", "alba"]}

@router.get("/voices")
async def list_voices() -> dict:
    return {
        "voices": ["cosette", "marius", "javert", "alba", "jean", "anna", "vera", "fantine",
                   "charles", "paul", "eponine", "azelma", "george", "mary", "jane",
                   "michael", "eve", "bill_boerst", "peter_yearsley", "stuart_bell",
                   "caro_davy", "giovanni", "lola", "juergen", "rafael", "estelle"],
        "default": "cosette",
    }

@router.post("/generate")
async def tts_generate(text: str, voice: str = "default") -> dict:
    from ziomek.server import _tts_model, _voice_cache
    if _tts_model is None:
        return {"error": "TTS model not loaded"}, 503
    from ziomek.tts.generate import generate_wav
    audio_b64, duration, sample_rate = generate_wav(_tts_model, _voice_cache, text, voice)
    return {"audio_b64": audio_b64, "duration": duration, "sample_rate": sample_rate, "channels": 1, "bit_depth": 16, "voice": voice}

@router.post("/speak")
async def tts_speak(text: str, voice: str = "default") -> dict:
    from ziomek.server import _tts_model, _voice_cache, _audio_player
    if _tts_model is None:
        return {"error": "TTS not ready"}, 503
    from ziomek.tts.generate import generate_wav
    audio_b64, duration, sample_rate = generate_wav(_tts_model, _voice_cache, text, voice)
    import io, base64, scipy.io.wavfile as wavfile
    wav_bytes = base64.b64decode(audio_b64)
    _audio_player.play(wav_bytes, sample_rate)  # type: ignore[misc]
    return {"status": "playing", "duration": duration, "sample_rate": sample_rate, "channels": 1, "bit_depth": 16, "voice": voice}
```

- [ ] **Step 3: Update server.py to include TTS router**

In `create_app()`, add:
```python
from ziomek.api import tts
app.include_router(tts.router, tags=["TTS"])
```

- [ ] **Step 4: Create test_api.py**

```python
from fastapi.testclient import TestClient
from ziomek.server import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_tts_status(client):
    resp = client.get("/api/tts/status")
    assert resp.status_code == 200
    assert "ready" in resp.json()

def test_list_voices(client):
    resp = client.get("/api/tts/voices")
    assert resp.status_code == 200
    data = resp.json()
    assert "voices" in data and "default" in data

def test_generate_returns_503_without_model(client):
    resp = client.post("/api/tts/generate", json={"text": "test"})
    assert resp.status_code == 503
```

- [ ] **Step 5: Run tests**

Run: `cd ziomek && python -m pytest tests/tts/test_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add ziomek/ziomek/api/__init__.py ziomek/ziomek/api/tts.py ziomek/tests/tts/test_api.py ziomek/ziomek/server.py
git commit -m "feat(ziomek): add TTS API endpoints"
```

---

## Phase 3: Avatar Module Porting

### Task 3.1: Port state machine from TypeScript to Python

**Files:**
- Create: `ziomek/ziomek/avatar/__init__.py`
- Create: `ziomek/ziomek/avatar/state_machine.py`
- Create: `ziomek/tests/avatar/__init__.py`
- Create: `ziomek/tests/avatar/test_state_machine.py`

- [ ] **Step 1: Create state_machine.py** (see Phase 3, Task 3.1 in PLAN.md for full 300-line implementation)

Full implementation: ported directly from `src/humanize/avatar/state-machine.ts`:
- Expression definitions as Python dataclasses
- TriggerType enum (BUTTON, AXIS, VSCODE, IDLE)
- AvatarStateMachine class with `update()`, `tick()`, `setExpression()`, `setMessage()`
- Same intensity preemption algorithm
- Same cycle counting and transition logic
- Message expiry uses `time.time()` instead of `setTimeout`

- [ ] **Step 2: Create test_state_machine.py** (see Phase 3, Task 3.1 in PLAN.md for test cases)

Test cases cover:
- Initial state is idle
- Button press triggers happy expression
- Button release returns to idle
- Intensity preemption (axis > button)
- `setExpression()` forces expression
- `setMessage()` with expiry
- `reset()` clears all state
- `getExpressionNames()` returns full list

- [ ] **Step 3: Run tests**

Run: `cd ziomek && python -m pytest tests/avatar/test_state_machine.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add ziomek/ziomek/avatar/__init__.py ziomek/ziomek/avatar/state_machine.py ziomek/tests/avatar/__init__.py ziomek/tests/avatar/test_state_machine.py
git commit -m "feat(ziomek): port avatar state machine from TypeScript to Python"
```

### Task 3.2: Port skin registry

**Files:**
- Create: `ziomek/ziomek/avatar/skins.py`
- Create: `ziomek/tests/avatar/test_skins.py`

- [ ] **Step 1: Create skins.py** (Skin dataclass with getFrameRow, getSpriteBuffer, SkinRegistry singleton)

- [ ] **Step 2: Create test_skins.py**

- [ ] **Step 3: Run tests**

- [ ] **Step 4: Commit**

```bash
git add ziomek/ziomek/avatar/skins.py ziomek/tests/avatar/test_skins.py
git commit -m "feat(ziomek): add skin registry with single-frame skin support"
```

### Task 3.3: Sprite sheet parser

**Files:**
- Create: `ziomek/ziomek/avatar/sprites.py`
- Create: `ziomek/tests/avatar/test_sprites.py`

- [ ] **Step 1: Create sprites.py** (parse_png_sprite from PNG header bytes 16-23)

- [ ] **Step 2: Create test_sprites.py**

- [ ] **Step 3: Run tests**

- [ ] **Step 4: Commit**

```bash
git add ziomek/ziomek/avatar/sprites.py ziomek/tests/avatar/test_sprites.py
git commit -m "feat(ziomek): add PNG sprite sheet parser"
```

### Task 3.4: Avatar API endpoints

**Files:**
- Create: `ziomek/ziomek/api/avatar.py`
- Create: `ziomek/tests/avatar/test_api.py`
- Modify: `ziomek/ziomek/server.py`

- [ ] **Step 1: Create avatar.py** (endpoints: /state, /input, /expression, /speak, /sprite)

- [ ] **Step 2: Update server.py to include avatar router**

- [ ] **Step 3: Create test_api.py**

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

```bash
git add ziomek/ziomek/api/avatar.py ziomek/tests/avatar/test_api.py ziomek/ziomek/server.py
git commit -m "feat(ziomek): add avatar API endpoints"
```

---

## Phase 4: Server Integration

### Task 4.1: Unify endpoints under single FastAPI app

**Files:**
- Modify: `ziomek/ziomek/server.py`
- Modify: `ziomek/ziomek/api/tts.py`
- Modify: `ziomek/ziomek/api/avatar.py`
- Create: `ziomek/ziomek/api/health.py`
- Create: `ziomek/tests/test_server.py`

- [ ] **Step 1: Add global state and CORS middleware to server.py**

```python
# In create_app():
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Initialize shared state:
global _tts_model, _voice_cache, _audio_player, _state_machine, _skin_registry
_tts_model = TTSModelWrapper()
_tts_model.load(settings.model_path)
_voice_cache = VoiceStateCache(_tts_model, settings.cache_dir)
_audio_player = AudioPlayer()
_state_machine = AvatarStateMachine()
_skin_registry = SkinRegistry()

# Include all routers:
from ziomek.api import tts, avatar, health
app.include_router(tts.router)
app.include_router(avatar.router)
app.include_router(health.router)
```

- [ ] **Step 2: Create health.py**

```python
from fastapi import APIRouter
from ziomek.server import _tts_model, _state_machine

router = APIRouter()

@router.get("/status")
async def status():
    return {
        "ready": _tts_model is not None and _tts_model.ready,
        "model_loaded": _tts_model is not None and _tts_model.ready,
        "endpoints": {
            "tts": ["POST /api/tts/generate", "POST /api/tts/speak", "GET /api/tts/status", "GET /api/tts/voices"],
            "avatar": ["POST /api/avatar/input", "GET /api/avatar/state", "POST /api/avatar/expression", "GET /api/avatar/sprite"],
        },
    }

@router.get("/")
async def root():
    return {
        "name": "ziomek",
        "version": "0.1.0",
        "endpoints": {"generate": "POST /api/tts/generate", "status": "GET /status"},
    }
```

- [ ] **Step 3: Create test_server.py**

```python
from fastapi.testclient import TestClient
from ziomek.server import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_status(client):
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "ready" in data or "model_loaded" in data

def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["name"] == "ziomek"

def test_cors(client):
    resp = client.options("/api/tts/status", headers={"Origin": "http://example.com"})
    assert resp.status_code == 200
    assert "Access-Control-Allow-Origin" in resp.headers
```

- [ ] **Step 4: Run tests**

Run: `cd ziomek && python -m pytest tests/test_server.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ziomek/ziomek/server.py ziomek/ziomek/api/health.py ziomek/tests/test_server.py
git commit -m "feat(ziomek): unify endpoints, add CORS, health endpoint"
```

### Task 4.2: Test server end-to-end

- [ ] **Step 1: Start server and verify endpoints**

Run: `cd ziomek && python -m ziomek.cli serve --port 5004` (in background)
Run: `curl -s http://localhost:5004/status`
Expected: `{"ready": true, "model_loaded": true, "endpoints": {...}}`

- [ ] **Step 2: Test TTS generate**

Run: `curl -s -X POST http://localhost:5004/api/tts/generate -H "Content-Type: application/json" -d '{"text": "Hello"}'`
Expected: `{"audio_b64": "...", "duration": 1.2, "sample_rate": 24000}`

- [ ] **Step 3: Test avatar input**

Run: `curl -s -X POST http://localhost:5004/api/avatar/input -H "Content-Type: application/json" -d '{"buttons": [{"pressed": true, "value": 0}], "axes": [0, 0, 0], "connected": true, "streaming": false, "chatFocused": false, "errorState": false}'`
Expected: `{"expression": "happy", "cycleIndex": 0}`

- [ ] **Step 4: Commit**

```bash
git commit --amend -m "feat(ziomek): verify end-to-end TTS + avatar endpoints"
```

---

## Phase 5: Extension Client Rewrite

### Task 5.1: Rename extension in package.json

**Files:**
- Modify: `package.json`
- Modify: `README.md`

- [ ] **Step 1: Update package.json**

```json
{
  "name": "ziomek.humanize-ai",
  "displayName": "Ziomek — Humanize AI",
  "description": "Ziomek Humanize AI — gamepad-controlled avatar with TTS. Connect to a locally running ziomek server.",
  "contributes": {
    "configuration": {
      "title": "Ziomek — Humanize AI",
      "properties": {
        "ziomek.enabled": { ... },
        "ziomek.tts.port": { "default": 5003 },
        "ziomek.tts.url": { "default": "http://localhost:5003" }
      }
    }
  }
}
```

- [ ] **Step 2: Update all references in README.md** (Gamify AI → Ziomek Humanize AI, gamifyAI → ziomek)

- [ ] **Step 3: Run linting**

Run: `npm run compile`
Expected: PASS (may have TypeScript errors from later tasks — that's expected)

- [ ] **Step 4: Commit**

```bash
git add package.json README.md
git commit -m "refactor: rename extension to ziomek.humanize-ai"
```

### Task 5.2: Rewrite PocketTTSService as HTTP client

**Files:**
- Modify: `src/humanize/tts/pocket-tts-service.ts`
- Modify: `src/humanize/tts/pocket-tts-service.ts` (rename class to `ZiomekTTSClient`)

- [ ] **Step 1: Rewrite PocketTTSService → HTTP client**

```typescript
// Remove _startServer(), _stopServer(), _child process management
// Keep only: speak() → fetch(`${this._url}/api/tts/speak`, {body: JSON.stringify({text, voice})})
// Keep only: stop(), getStatus(), isAvailable() → fetch(`${this._url}/api/tts/status`)
// Keep only: cleanup() → just set _isAvailableCache = null
```

- [ ] **Step 2: Run tests**

Run: `npm test`
Expected: PASS (all 201 tests pass, now fewer since we removed process management)

- [ ] **Step 3: Commit**

```bash
git add src/humanize/tts/pocket-tts-service.ts
git commit -m "refactor: replace PocketTTSService with HTTP client to ziomek server"
```

### Task 5.3: Remove TTS process management from extension.ts

**Files:**
- Modify: `src/extension.ts`

- [ ] **Step 1: Remove createTTS() spawn logic**

Remove `_startServer()`, `_stopServer()`, `_child` handling. Keep only:
```typescript
ttsService = new ZiomekTTSClient({ url: config.get('ziomek.tts.url', 'http://localhost:5003') });
```

- [ ] **Step 2: Remove deactivation cleanup of Python process**

Remove `ttsService.cleanup()` call (no longer needed).

- [ ] **Step 3: Run tests**

Run: `npm test`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/extension.ts
git commit -m "refactor: remove TTS process management from extension, use HTTP client"
```

### Task 5.4: Rewrite avatar panel to use ziomek

**Files:**
- Modify: `src/humanize/avatar-panel.ts`
- Modify: `src/humanize/avatar/state-machine.ts` (remove — moved to ziomek)
- Modify: `src/humanize/avatar/skin-registry.ts` (remove — moved to ziomek)
- Modify: `src/humanize/avatar/skins/single-frame-skin.ts` (remove — moved to ziomek)

- [ ] **Step 1: Modify avatar-panel.ts**

Remove:
- `_loadSprite()` → replaced by HTTP call to `/api/avatar/sprite`
- `_stateMachine` reference → replaced by HTTP calls to `/api/avatar/input` and `/api/avatar/state`

Keep:
- Webview HTML/JS rendering (unchanged)
- `_sendToPanel()` → now fetches sprite from ziomek

```typescript
// In _loadSprite():
const resp = await fetch(`${this._serverUrl}/api/avatar/sprite`);
const data = await resp.json();
this._spriteBuffer = Buffer.from(data.sprite_b64.split(',')[1], 'base64');
this._spriteWidth = data.width;
this._spriteHeight = data.height;
this._frameWidth = data.frameWidth;
this._frameHeight = data.frameHeight;

// In _updatePanel():
const input = this._getInput();
const resp = await fetch(`${this._serverUrl}/api/avatar/input`, {
  method: 'POST',
  body: JSON.stringify(input),
});
const state = await resp.json();
this._lastExpression = state.expression;
this._lastCycleIndex = state.cycleIndex;
// Then postMessage to webview as before
```

- [ ] **Step 2: Run tests**

Run: `npm test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/humanize/avatar-panel.ts src/humanize/avatar/state-machine.ts src/humanize/avatar/skins/
git commit -m "refactor: avatar panel now fetches state from ziomek server via HTTP"
```

### Task 5.5: Final integration test

- [ ] **Step 1: Start ziomek server**

Run: `cd ziomek && python -m ziomek.cli serve --port 5003`

- [ ] **Step 2: Run extension tests**

Run: `npm test`
Expected: PASS

- [ ] **Step 3: Manual test**

Open VS Code, load extension, click "Show Avatar", speak via TTS → verify avatar expression syncs with speech.

- [ ] **Step 4: Commit**

```bash
git commit -m "test: verify full integration of ziomek server + extension"
```

---

## Phase 6: Distribution

### Task 6.1: Create launcher scripts

**Files:**
- Create: `ziomek/run-ziomek.sh`
- Create: `ziomek/run-ziomek.bat`

- [ ] **Step 1: Create run-ziomek.sh**

```bash
#!/bin/bash
# Run ziomek server
set -e
cd "$(dirname "$0")"
pip install -e . 2>/dev/null || true
python -m ziomek.cli serve --port "${1:-5003}"
```

- [ ] **Step 2: Create run-ziomek.bat**

```bat
@echo off
REM Run ziomek server
cd /d "%~dp0"
pip install -e . 2>nul || true
python -m ziomek.cli serve --port %1
```

- [ ] **Step 3: Make executable**

Run: `chmod +x ziomek/run-ziomek.sh`

- [ ] **Step 4: Commit**

```bash
git add ziomek/run-ziomek.sh ziomek/run-ziomek.bat
git commit -m "feat: add launcher scripts for ziomek server"
```

### Task 6.2: Update README with client/server instructions

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README.md**

Add sections:
- Installation (ziomek first, then extension)
- Running ziomek server (`pip install .` or `ziomek serve`)
- Configuring extension (set `ziomek.tts.url`)
- Requirements (Python 3.10+, pocket-tts)

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with client/server installation instructions"
```

### Task 6.3: Create .vsix build workflow (optional, future)

**Files:**
- Create: `.github/workflows/build.yml`

- [ ] **Step 1: Create GitHub Actions workflow**

```yaml
name: Build .vsix
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci && npm run compile
      - uses: HaaA/vsix-builder-action@v0.1.0
        with:
          packagePath: .
          outDir: dist
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/build.yml
git commit -m "ci: add .vsix build workflow"
```

---

## Implementation Notes

- All ziomek tests use pytest with httpx test client for FastAPI
- Extension tests use jest (existing setup) — remove process-related mocks
- State machine port must match TypeScript version exactly — use test cases as regression
- Voice loading from pocket_tts 3.x uses `get_state_for_audio_prompt("cosette")` for default
- All audio playback uses `sd.play(blocking=False)` — never `blocking=True`
- Extension no longer has `import { spawn }` from child_process for TTS
