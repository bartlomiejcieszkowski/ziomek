# STT Streaming Endpoint

**Date:** 2026-10-17  
**Status:** Plan  
**Goal:** Wire up the existing STT engine to be accessible via WebSocket and HTTP endpoints so the VS Code extension and debug page can use speech-to-text.

## Problem

The STT engine (`src/ziomek/stt.py`) exists and starts automatically with the server, but:
- No WebSocket endpoint for live transcription streaming
- No HTTP endpoint for one-shot transcription
- The `on_transcription` callback is defined but nobody consumes it
- Debug page has STT UI (start/stop, live transcription, stats) but nothing connected
- VS Code extension has no way to use STT

## Design

### Architecture

```
┌─────────────────┐     WebSocket      ┌──────────────────┐
│  VS Code Ext    │ ◄─────────────────►│  STT Engine      │
│  (mic capture)  │                    │  (RealtimeSTT)   │
└─────────────────┘                    └──────────────────┘
                                              │
┌─────────────────┐     HTTP POST           │ transcription
│  Debug Page     │ ──────────────────────►  │ results
│  (one-shot)     │                         │
└─────────────────┘                         │
                                            ▼
                                    ┌──────────────────┐
                                    │  WebSocket       │
                                    │  /api/stt/stream │
                                    │  (live results)  │
                                    └──────────────────┘
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `WS /api/stt/stream` | WebSocket | Live transcription streaming. Client sends commands, server pushes results. |
| `POST /api/stt/transcribe` | HTTP | One-shot transcription. Send audio blob (base64 WAV), get text back. |
| `GET /api/stt/status` | HTTP | Returns STT stats (state, engine, model, transcription count). |
| `POST /api/stt/start` | HTTP | Start recording (alias for WebSocket start command). |
| `POST /api/stt/stop` | HTTP | Stop recording. |
| `POST /api/stt/reconfigure` | HTTP | Change engine/model at runtime. Stops recording, recreates engine, returns to idle. |
| `GET /api/stt/models` | HTTP | List available faster-whisper models. |

### WebSocket Protocol

**Client → Server commands:**
```json
{ "action": "start" }          // Start recording
{ "action": "stop" }           // Stop recording
{ "action": "status" }         // Request current status
{ "action": "reconfigure", "engine": "faster_whisper", "model": "base.en" }  // Change engine/model (stops recording, recreates engine)
```

**Server → Client messages:**
```json
// Transcription result (realtime or final)
{ "type": "transcription", "text": "hello world", "is_final": true }

// Realtime partial transcription
{ "type": "transcription", "text": "hello...", "is_final": false }

// Status response
{ "type": "status", "state": "listening", "engine": "faster_whisper", "model": "tiny.en", "transcription_count": 5 }

// Error
{ "type": "error", "message": "STT engine not initialized" }
```

### Implementation Tasks

#### Task 1: Create STT API Router (`src/ziomek/api/stt.py`)

New file with HTTP endpoints:
- `GET /api/stt/status` — returns STT stats from `_stt_engine.stats`
- `POST /api/stt/start` — starts recording (if not already)
- `POST /api/stt/stop` — stops recording (if recording)
- `POST /api/stt/transcribe` — one-shot transcription (accepts base64 audio, returns text)
- `POST /api/stt/reconfigure` — change engine/model at runtime
  - Stops recording, shuts down recorder
  - Recreates `AudioToTextRecorder` with new engine/model params
  - Restarts engine in idle state
  - Returns `{ "status": "reconfigured", "engine": "...", "model": "..." }`
  - Error handling: if new engine/model fails to load, restore previous config
- `GET /api/stt/models` — list available faster-whisper models (`tiny.en`, `base.en`, `small.en`, `medium.en`, `large-v3`)

#### Task 2: Create WebSocket Endpoint (`src/ziomek/api/stt_ws.py`)

New file with WebSocket endpoint:
- `WS /api/stt/stream` — manages live transcription streaming
- Tracks connected clients
- Routes transcription callback results to all connected clients
- Handles client commands (start/stop/status)
- Cleans up on disconnect

#### Task 3: Wire STT Callback to WebSocket

- Modify `STTEngine` or server to connect `on_transcription` callback to WebSocket broadcaster
- When transcription callback fires, push result to all connected WebSocket clients
- Handle realtime vs final transcriptions

#### Task 4: Wire Up Debug Page STT Controls

- Connect debug page STT section to WebSocket `/api/stt/stream`
- Start/Stop buttons → WebSocket commands
- Live transcription → WebSocket message handler
- Stats → poll `/api/stt/status` or receive via WebSocket

#### Task 5: Add Engine/Model Reconfigure to STTEngine

- Add `reconfigure(engine_name: str, model_name: str)` method to `STTEngine` class
- Stops recording, shuts down recorder
- Recreates `AudioToTextRecorder` with new params
- Restarts engine in idle state
- Returns `(success: bool, message: str)`
- Error handling: if new engine/model fails to load, restore previous config
- Thread-safe: use lock to prevent concurrent reconfigure/start/stop

#### Task 6: Update Health Endpoint

- Add STT info to `/status` response (engine name, model, state)

#### Task 7: Tests

- Test STT HTTP endpoints (status, start, stop)
- Test WebSocket endpoint (connect, send commands, receive results)
- Test debug page STT section connectivity

#### Task 8: Documentation

- Update README with STT usage
- Update TODO.md

### Files to Create/Modify

| File | Action |
|------|--------|
| `src/ziomek/api/stt.py` | **Create** — HTTP endpoints |
| `src/ziomek/api/stt_ws.py` | **Create** — WebSocket endpoint |
| `src/ziomek/api/__init__.py` | **Modify** — add stt import |
| `src/ziomek/server.py` | **Modify** — include STT router + WebSocket, wire callback |
| `src/ziomek/client/resources/debug.html` | **Modify** — connect STT controls to WebSocket |
| `tests/test_stt_api.py` | **Create** — HTTP endpoint tests |
| `tests/test_stt_ws.py` | **Create** — WebSocket tests |
| `tests/test_stt_reconfigure.py` | **Create** — reconfigure tests |
| `README.md` | **Modify** — add STT docs |

## Notes

- STT engine auto-starts with server (model loaded at boot)
- Recording can be started/stopped independently of engine state
- Multiple WebSocket clients can connect simultaneously (all receive transcriptions)
- One-shot `/api/stt/transcribe` uses `transcribe_chunk()` for non-streaming mode
- The `faster_whisper` model is already cached from earlier testing
