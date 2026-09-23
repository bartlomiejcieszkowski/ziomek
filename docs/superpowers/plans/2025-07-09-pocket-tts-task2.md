# Task 2: PocketTTSService Implementation Plan

## Overview
Create `PocketTTSService` that wraps the Python Pocket TTS server via HTTP, implementing the `TTSService` interface.

## Files to Create
- `src/gamepad/tts/pocket-tts-service.ts` — main service implementation
- `tests/gamepad/tts/pocket-tts-service.test.ts` — unit tests (mocked HTTP)

## Design Decisions

### Lifecycle
- **Lazy spawn**: Python server starts on first `speak()` call (not on construction)
- **Sticky**: Server stays alive between speak calls; kills on `stop()` or `deactivate()`
- **Auto-reconnect**: If server dies mid-stream, re-spawn on next speak()
- **isAvailable()**: Checks for `python` / `python3` binary on PATH

### speak()
1. Check `isAvailable()` → return error if not
2. Start Python server if not running
3. POST to `http://localhost:${port}/generate` with `{ text, voice }`
4. Set status → 'speaking'
5. Await response (base64 WAV + metadata)
6. Set status → 'idle'
7. Return Promise

### stop()
1. Set status → 'stopping'
2. Kill child process (terminates generation)
3. Reset status → 'idle'

### isAvailable()
- Check `child_process.spawnSync('python3', ['--version'])` first
- If fails, try `python`
- Return false if neither found

## Config Interface
```ts
interface PocketTTSConfig {
  port: number;           // default 5003
  modelPath?: string;     // optional custom model path
  voice: string;          // default 'default'
  timeoutMs: number;      // default 30000
}
```

## Test Strategy (mocked HTTP)
- No real Python server required
- Mock `fetch` (or use nock/http-mock)
- Test: speak successful, speak error, stop, isAvailable, config options
