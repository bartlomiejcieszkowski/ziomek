# Pocket TTS Integration Plan

## Goal
Replace StubTTSService with Pocket TTS backend for natural-sounding speech synthesis.

## Architecture
```
HTTP Client (curl/browser)
  ↓ POST /api/tts/speak
PocketTTSService (Node.js)
  ↓ spawn Python HTTP server
pocket-tts-server.py (Python)
  ↓ pocket_tts API
Pocket TTS model (PyTorch, CPU, 100M params)
  ↓ generate audio
WAV bytes → base64 → HTTP response
```

## Tasks

### Task 1: Create Pocket TTS Python server script
- `debug_tools/pocket-tts-server.py` — lightweight HTTP server wrapping Pocket TTS API
- Loads model once on startup, serves `/generate` endpoint
- Accepts POST JSON with `text` and optional `voice` parameters
- Returns base64 WAV audio with metadata (duration, sample rate)
- Handles voice cloning from HuggingFace or local audio file
- Configurable port, model path, voice parameters

### Task 2: Create PocketTTSService in Node.js
- `src/gamepad/tts/pocket-tts-service.ts` extending `TTSService`
- Manages Python server lifecycle (start/stop)
- Calls `/generate` endpoint, returns audio as base64
- Handles async speak() with proper error handling
- Configurable: port, model path, voice, timeout
- Fallback: returns error status if Python not available
- Uses `child_process.spawn()` to start Python server
- Cleans up server process in `stop()`

### Task 3: Wire Pocket TTS into extension
- Update `src/extension.ts` to use `PocketTTSService` instead of `StubTTSService`
- Add configuration options in `package.json` for:
  - `tts.backend`: 'stub' | 'pocket' | 'auto'
  - `tts.pocket.port`: port for Python server (default 5003)
  - `tts.pocket.modelPath`: optional custom model path
  - `tts.pocket.voice`: voice identifier (HF or local)
- Handle extension activation/deactivation lifecycle
- Add error handling for missing Python/pocket-tts

### Task 4: Add integration tests
- Test `PocketTTSService` class (unit tests with mocked HTTP)
- Test Python server script (E2E with actual pocket-tts)
- Verify audio output format (base64 WAV)
- Verify fallback behavior when Python unavailable

## File Structure
```
src/gamepad/tts/
├── pocket-tts-service.ts    # Node.js backend
tests/gamepad/tts/
├── pocket-tts-service.test.ts  # Unit tests
debug_tools/
└── pocket-tts-server.py      # Python HTTP server
package.json                   # New config options
src/extension.ts               # Wire up PocketTTSService
```

## Implementation Details

### Python Server (`pocket-tts-server.py`)
- Uses `pocket_tts` Python package API
- Loads model once: `TTSModel.load_model()`
- Generates audio: `model.generate_audio(voice_state, text)`
- Converts to WAV via `scipy.io.wavfile.write`
- Base64 encodes WAV bytes
- HTTP endpoint: `POST /generate` → `{ "audio_b64": "...", "duration": 2.5 }`
- Status endpoint: `GET /status` → `{ "ready": true, "voices": [...] }`

### Node.js Backend (`PocketTTSService`)
- Constructor: port, modelPath, voice, timeoutMs
- `speak(text)`: spawn server if not running → POST /generate → return audio b64
- `stop()`: kill server process
- `isAvailable()`: check Python + pocket_tts installed
- `getStatus()`: return 'idle' | 'speaking' | 'stopping' | 'error'

### Error Handling
- Python not installed: return error status, log message
- pocket_tts not installed: return error status, log message
- Server timeout: return error status
- Model load failure: return error status
- Network error: retry once, then return error

## Commit Strategy
One commit per task, following Conventional Commits.
