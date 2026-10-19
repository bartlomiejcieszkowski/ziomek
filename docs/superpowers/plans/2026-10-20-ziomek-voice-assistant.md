# Ziomek Voice Assistant — Pi Extension

## Overview

A Pi extension that turns Pi sessions into hands-free voice conversations. The extension bridges Pi's tool call system with ziomek's TTS/STT/WebSocket infrastructure, letting the LLM speak responses, listen to user input, and respond to gamepad input — all feeding into Pi's message flow.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Pi Agent                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Voice Assistant Extension (TypeScript)                     │  │
│  │                                                             │  │
│  │  Tools: speak, listen, start, stop, status, transcribe      │  │
│  │  Commands: /voice, /voice-tools, /voice-start, /voice-stop  │  │
│  │  Dashboard: overlay showing transcription, state, activity  │  │
│  │  Gamepad: button press → user message / tool call           │  │
│  └──────────────────────────┬─────────────────────────────────┘  │
│                              │                                    │
│  sendUserMessage() ──────────┘ (injects STT/gamepad as user msgs)│
└──────────────────────────────┼───────────────────────────────────┘
                               │ HTTP (TTS) / WS (STT)
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    ziomek server (Python)                         │
│                                                                  │
│  POST /api/tts/synthesize  → WAV playback                        │
│  WS   /api/stt/stream      → live STT                            │
│  GET  /api/stt/status      → stats                               │
│  GET  /api/gamepad/state   → gamepad state                       │
└──────────────────────────────────────────────────────────────────┘
```

## Two Input Channels + Keyword Gating

The extension provides **two ways** for the user to send messages to the LLM, both gated by a keyword:

### 1. Tool-based (one-shot)
- **`ziomek_voice_listen`** — one-shot voice command (~5s capture), returns transcription
- **`ziomek_voice_transcribe`** — transcribe an audio file

### 2. Continuous voice (hands-free)
- **`ziomek_voice_start`** — starts continuous listening
- STT captures all speech, but only injects into the LLM when a **keyword** is detected
- Keyword-gated transcriptions are sent via `pi.sendUserMessage(text, { deliverAs: "followUp" })`
- LLM sees them as if the user typed them
- **`ziomek_voice_stop`** — stops continuous listening

## Keyword Gating

Continuous listening only sends transcriptions to the LLM if they start with a configured keyword. The keyword is stripped before sending.

- **Default keyword:** `"ziomek"` (configurable)
- **Matching:** case-insensitive prefix match
- **Stripping:** keyword + optional trailing comma/whitespace removed before sending
- **Logging:** non-matching transcriptions are logged (dashboard shows "ignored")

Examples:
- User says: `"ziomek, tell me a joke"` → keyword `ziomek` detected → sends `"tell me a joke"` to LLM
- User says: `"ziomek continue"` → keyword detected → sends `"continue"` to LLM
- User says: `"hmm, let me think"` → no keyword → ignored (logged as ignored)
- User says: `"Ziomek what's the time"` → keyword detected (case-insensitive) → sends `"what's the time"` to LLM

Configurable via `config.json`:
```json
{
  "keywords": ["ziomek", "hey", "assistant"]
}
```

Multiple keywords supported. Any of them triggers the gate.
- Gamepad polling runs in a background interval (checked every 2s)
- Button presses are debounced (1s cooldown per button)
- Transcriptions injected via `pi.sendUserMessage(text, { deliverAs: "followUp" })`

## Tools

### 1. `ziomek_voice_speak` (hidden)
Speak text via TTS. The LLM calls this to speak its response.

- **Parameters:**
  - `text` (string, required) — text to speak
  - `voice` (string, optional) — voice name (cosette, default, etc.)
- **Annotations:** readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false
- **Prompt guidelines:**
  - "Use this to speak the response aloud to the user"
  - "The user will hear the text via TTS"
  - "Use voice parameter to select a specific voice if needed"
- **Returns:** `{ content: [{ type: "text", text: "✓ Spoken: ..." }] }`

### 2. `ziomek_voice_listen` (hidden)
One-shot voice command. Captures ~5 seconds of user speech and returns transcription.

- **Parameters:**
  - `duration` (number, optional, default 5) — max seconds to listen
  - `prompt` (string, optional) — hint for what to listen for
- **Annotations:** readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true
- **Prompt guidelines:**
  - "Use this to capture a one-shot voice command from the user"
  - "Listens for up to `duration` seconds (default 5)"
  - "The returned text is the user's spoken command"
  - "Use `prompt` to guide what the user should say"
- **Returns:** `{ content: [{ type: "text", text: "User said: ..." }] }`

### 3. `ziomek_voice_start` (hidden)
Start continuous listening mode. The extension will listen for user speech and inject transcriptions as user messages.

- **Parameters:** none
- **Annotations:** readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true
- **Prompt guidelines:**
  - "Use this to enter hands-free mode — the extension will listen for user speech"
  - "Each transcription will be injected as a user message"
  - "Call `ziomek_voice_stop` when done"
- **Returns:** `{ content: [{ type: "text", text: "✓ Listening... (call ziomek_voice_stop to stop)" }] }`

### 4. `ziomek_voice_stop` (hidden)
Stop continuous listening mode.

- **Parameters:** none
- **Annotations:** readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false
- **Prompt guidelines:**
  - "Call this when you're done with hands-free mode"
  - "Resumes normal Pi interaction"
- **Returns:** `{ content: [{ type: "text", text: "✓ Listening stopped." }] }`

## Gamepad Controls

Gamepad provides parallel control actions (not feeding into the LLM):

- **Button mappings** (configurable):
  - `A` (South) — short voice capture → keyword-gated → inject as user message
  - `B` (East) — cycle through preset responses
  - `X` (West) — long voice capture → keyword-gated → inject as user message
  - `Y` (North) — trigger TTS speak of last LLM response
  - `LB` — increment response index
  - `RB` — decrement response index
  - `D-Pad Up/Down` — scroll through conversation history
  - `Start` — toggle voice assistant dashboard
  - `Select` — show current status

Gamepad polling runs in a background interval (checked every 2s). Button presses are debounced (1s cooldown per button). Keyword-gated captures use the same keyword logic as continuous voice mode.

### 5. `ziomek_voice_status` (hidden)
Check current voice assistant state.

- **Parameters:** none
- **Annotations:** readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false
- **Prompt guidelines:**
  - "Use this to check if voice assistant is active and what mode it's in"
- **Returns:** `{ content: [{ type: "text", text: "State: idle/listening | Engine: faster_whisper | Model: tiny.en" }] }`

### 6. `ziomek_voice_transcribe` (hidden)
Transcribe an audio file (WAV/MP3). Useful for transcribing pre-recorded audio.

- **Parameters:**
  - `file` (string, required) — path to audio file
- **Annotations:** readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false
- **Prompt guidelines:**
  - "Use this to transcribe a pre-recorded audio file"
  - "Supports WAV and MP3 formats"
- **Returns:** `{ content: [{ type: "text", text: "Transcription: ..." }] }`

### 7. `ziomek_gamepad_state` (hidden)
Get current gamepad state (buttons, axes, connected).

- **Parameters:** none
- **Annotations:** readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false
- **Prompt guidelines:**
  - "Use this to check the current gamepad state"
  - "Returns buttons, axes, and connection status"
- **Returns:** `{ content: [{ type: "text", text: "Connected: true | Buttons: [A,B,X,Y,...] | Axes: [0,0]" }] }`

## Slash Commands

### `/voice`
Toggle voice assistant dashboard overlay.

### `/voice-tools`
Manage tool visibility.
- `/voice-tools enable` — show all voice tools to the LLM
- `/voice-tools disable` — hide all voice tools
- `/voice-tools status` — show current tool state

### `/voice-start`
Start continuous listening mode (convenience wrapper).

### `/voice-stop`
Stop continuous listening mode (convenience wrapper).

### `/voice-status`
Show current voice assistant state.

### `/gamepad`
Toggle gamepad monitoring overlay.

## Dashboard Overlay

Non-capturing overlay (like kijek's log overlay, todo.ts pattern) showing:

```
┌─ Ziomek Voice ─────────────────────────────┐
│ State: 🔴 Listening                         │
│ Engine: faster_whisper / tiny.en            │
│                                             │
│ ─ Live Transcription ─                      │
│ [12:34:56] Hello, how are you?              │
│ [12:35:01] The weather is nice today.       │
│                                             │
│ ─ Gamepad ─                                 │
│ Connected: ✓ Xbox Wireless Controller        │
│ A: ○  B: ○  X: ○  Y: ○                     │
│                                             │
│ ─ Recent Activity ─                         │
│ 12:34:50 → spoke: "Hello, welcome!"         │
│ 12:34:55 → listened: "Hello, how are you?"  │
│ 12:35:02 → gamepad: A pressed               │
└─────────────────────────────────────────────┘
```

- Auto-scrolls on new transcription
- Color-coded state indicator (red=listening, green=idle, yellow=speaking)
- Shows last 20 transcription entries
- Shows last 10 activity entries (speak/listen/gamepad events)
- Gamepad section shows current button state
- Uses `@earendil-works/pi-tui` components (Text, truncateToWidth, theme.fg)

## Configuration

Config file: `~/.pi/agent/extensions/ziomek-voice/config.json`

```json
{
  "serverUrl": "http://localhost:5003",
  "sttEngine": "faster_whisper",
  "sttModel": "tiny.en",
  "ttsVoice": "cosette",
  "listenDuration": 5,
  "autoStartDashboard": false,
  "toolsHiddenByDefault": true,
  "gamepad": {
    "pollIntervalMs": 2000,
    "debounceMs": 1000,
    "buttonMap": {
      "A": "listen_short",
      "B": "cycle_responses",
      "X": "listen_long",
      "Y": "speak_last",
      "LB": "next_response",
      "RB": "prev_response",
      "DPAD_UP": "scroll_up",
      "DPAD_DOWN": "scroll_down",
      "START": "toggle_dashboard",
      "SELECT": "show_status"
    }
  }
}
```

## File Structure

```
ziomek-voice/
├── package.json          # name: "ziomek-voice", pi.extensions: ["src/index.ts"]
├── tsconfig.json
├── src/
│   ├── index.ts          # Extension factory (entry point)
│   ├── tools.ts          # Tool definitions + handlers (7 tools)
│   ├── dashboard.ts      # TUI overlay component (pi-tui Text, truncateToWidth, theme)
│   ├── stt-client.ts     # WebSocket STT client (connect, start, stop, onTranscription)
│   ├── tts-client.ts     # HTTP TTS client (speak, cancel, getVoices)
│   ├── gamepad.ts        # Gamepad polling + button mapping + debounce
│   ├── config.ts         # Config management (load/save from ~/.pi/agent/extensions/ziomek-voice/)
│   └── state.ts          # Extension state (listening, dashboard, gamepad, activity log)
├── tests/
│   ├── tools.test.ts     # Tool execution tests (mock TTS/STT)
│   ├── stt-client.test.ts# WebSocket client tests
│   ├── tts-client.test.ts# HTTP client tests
│   ├── gamepad.test.ts   # Gamepad polling + debounce tests
│   └── config.test.ts    # Config load/save tests
└── dist/                 # Build output (if compiled)
```

## Implementation Plan

### Task 1: Package scaffold ✅ COMPLETED
- Created `pi_extension/` project structure
- `package.json` with `pi.extensions: ["src/index.ts"]`
- `tsconfig.json`, vitest config
- `src/index.ts` with extension factory stub
- Test: `tests/scaffold.test.ts` (1 test)

### Task 2: Config module ✅ COMPLETED
- `src/config.ts` — load/save config from `~/.pi/agent/extensions/ziomek-voice/config.json`
- Default values for all fields including gamepad config
- Test: `tests/config.test.ts` (8 tests — load defaults, invalid JSON, merge partial, save/reload, buttonMap preservation)

### Task 3: TTS client ✅ COMPLETED
- `src/tts-client.ts` — HTTP client for ziomek TTS endpoints
- `speak(text, voice?)` — POST to `/api/tts/synthesize`
- `cancel()` — cancel current playback
- `getVoices()` — list available voices
- `getLastWavPath()` — return last generated WAV path
- Test: `tests/tts-client.test.ts` (13 tests)

### Task 4: STT client ✅ COMPLETED
- `src/stt-client.ts` — WebSocket client for ziomek STT streaming
- `connect()`, `start()`, `stop()`, `disconnect()`
- `onTranscription(callback)`, `onStatus(callback)`
- `getStatus()`, `reconfigure()`, `setBaseUrl()`
- WebSocket auto-reconnect with exponential backoff (2s→30s)
- Command-response matching with 5s timeout
- Test: `tests/stt-client.test.ts` (16 tests with mock WebSocket)

### Task 5: Gamepad module ✅ COMPLETED
- `src/gamepad.ts` — gamepad polling with debounce
- Polls `navigator.getGamepads()` every `pollIntervalMs` (default 2s)
- Tracks button state, detects press/release events
- Debounces button presses (1s cooldown per button)
- Maps buttons to actions via `buttonMap` config
- Test: `tests/gamepad.test.ts` (14 tests)

### Task 5.5: Keyword gating module ✅ COMPLETED
- `src/keyword.ts` — keyword detection and stripping
- `matchKeyword(text, keywords)` — case-insensitive prefix match
- `stripKeyword(text, keywords)` — remove keyword + trailing comma/whitespace
- `gateKeyword(text, keywords)` — returns `{ matched, keyword?, cleaned }`
- Test: `tests/keyword.test.ts` (23 tests)

### Task 6: Tool definitions + handlers ✅ COMPLETED
- `src/tools.ts` — register all 7 tools with ExtensionAPI
- `ziomek_voice_speak` → POST TTS
- `ziomek_voice_listen` → start STT, wait, stop, return transcription
- `ziomek_voice_start` → start continuous STT, apply keyword gate, inject via `pi.sendUserMessage()`
- `ziomek_voice_stop` → stop continuous STT
- `ziomek_voice_status` → return current state
- `ziomek_voice_transcribe` → placeholder (server endpoint not yet implemented)
- `ziomek_gamepad_state` → return current gamepad state
- Test: `tests/tools.test.ts` (13 tests)

### Task 7: Dashboard overlay ✅ COMPLETED
- `src/dashboard.ts` — TUI overlay component
- Shows state (🔴🟡🟢), engine info, live transcription (last 5), gamepad status, recent activity (last 3)
- Auto-refresh at config interval, max 20 transcription entries
- Test: `tests/dashboard.test.ts` (14 tests)

### Task 8: Slash commands + lifecycle ✅ COMPLETED
- `src/lifecycle.ts` — extension factory with slash commands and lifecycle hooks
- Slash commands: `/voice-start`, `/voice-stop`, `/voice-status`, `/voice-speak`, `/voice-listen`, `/dashboard`, `/gamepad-state`
- Lifecycle: `session_start` (init gamepad, show dashboard), `session_shutdown` (cleanup)
- Test: `tests/lifecycle.test.ts` (7 tests)

### Task 9: Integration + verification ✅ COMPLETED
- Full extension integration test: `tests/integration.test.ts` (14 tests)
- Tests: tool execution, slash command execution, lifecycle events, keyword gating, dashboard rendering
- TypeScript compiles clean, 122 tests pass

## Key Technical Notes

- **Keyword gating**: When `ziomek_voice_start` is active, each STT transcription is checked against configured keywords (default: "ziomek"). Only keyword-matched transcriptions are injected as user messages via `pi.sendUserMessage(text, { deliverAs: "followUp" })`. The keyword is stripped before sending.
- **Gamepad keyword-gated capture**: Button presses mapped to `listen_short` or `listen_long` trigger STT capture, then apply the same keyword gate before injecting via `pi.sendUserMessage()`.
- **Tool exposure**: All tools start as `"hidden"` (save context). User enables with `/voice-tools enable`.
- **No audio capture in extension**: The extension sends audio to ziomek server's STT endpoint. The server handles audio capture (via RealtimeSTT) and returns transcriptions via WebSocket.
- **Error handling**: All tool handlers catch errors and return `{ isError: true, content: [{ type: "text", text: "Error: ..." }] }`.
- **State management**: Extension state stored in memory, reconstructed from session entries on `session_start`/`session_tree` (like todo.ts pattern). Activity log stored via `pi.appendEntry()` for durability.
- **TUI guards**: Dashboard uses `ctx.mode === "tui"` check before showing overlay. RPC mode falls back to `setWidget()` for status.
- **Cleanup**: `session_shutdown` closes WebSocket, stops gamepad polling, hides dashboard overlay.
