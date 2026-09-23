# Avatar Enhancement Plan: Messages, Timed Emotions & TTS

## Goal
1. Extend emotion system: set emotion with optional message text, duration, and text-only mode
2. Add TTS architecture with swappable backends
3. Display messages on avatar via HTTP endpoints

## Tasks

### Task 1: Create TTS interface and abstract backend
- Create `src/gamepad/tts/tts-service.ts` with abstract `TTSBackend` interface
- Define methods: `speak(text)`, `stop()`, `getStatus()`, `isAvailable()`
- Each backend implements the interface; easy to swap later
- No implementation yet — just the contract

### Task 2: Implement StubTTs backend (for testing)
- Create `src/gamepad/tts/stub-tts.ts` that logs to console
- No audio output — just proof-of-concept
- Makes TTS interface testable without requiring system audio
- Stub can later be replaced with `espeak`, `svox`, `windows-speech`, or API-based TTS

### Task 3: Add message display to state machine
- Modify `ExpressionState` to include `message?: string` field
- Add `setMessage(text?: string)` method to AvatarStateMachine
- Separate concept from emotion: emotion = visual state, message = displayed text
- External messages auto-clear after configurable duration (default 10s)
- Message can be set independently of emotion

### Task 4: Add timed emotions to state machine
- Modify `setExpression` to accept optional `durationMs` parameter
- If duration provided, schedule auto-return after duration
- Track scheduled timers on state machine instance
- Auto-clear timers on state machine reset
- Also track message timers together

### Task 5: Wire TTS into HTTP server
- Add TTSManager to LocalHTTPServer
- Register endpoints:
  - `POST /api/avatar/message` — set message (with optional emotion + duration)
  - `POST /api/tts/speak` — send text to TTS
  - `GET /api/tts/status` — check TTS status
  - `POST /api/tts/stop` — stop current speech
- Backward-compatible: existing `/api/avatar/emotion` still works

### Task 6: Wire TTS + messages into extension lifecycle
- Register TTS backend in extension.ts
- Create TTSManager instance
- Pass to HTTP server and avatar panel
- Cleanup TTS in deactivate()

### Task 7: Update avatar panel to display messages
- Add message display area below canvas in HTML
- Render message text (word-wrap, scroll if needed)
- Auto-hide after timeout
- Style message text in HUD overlay

### Task 8: Update HTTP server documentation and tests
- Update root endpoint with new endpoints list
- Add integration tests for message and TTS endpoints

## File Structure
```
src/gamepad/
├── tts/
│   ├── tts-service.ts      # Abstract interface (Task 1)
│   └── stub-tts.ts         # Stub implementation (Task 2)
├── avatar/
│   ├── state-machine.ts    # Messages + timed emotions (Task 3 & 4)
│   └── avatar-panel.ts     # Display messages (Task 7)
├── local-http-server.ts    # New endpoints (Task 5)
├── extension.ts            # Wiring (Task 6)
```

## Commit Strategy
One commit per task, all following Conventional Commits format.
