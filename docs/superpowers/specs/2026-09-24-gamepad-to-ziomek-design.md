# Design: Gamepad → ziomek Client

**Date:** 2026-09-24  
**Status:** Draft  
**Scope:** Refactor gamepad/gamepad-input handling from extension to ziomek server

## Motivation

- **Simplify extension:** Remove gamepad detection, state machine, and sprite loading. Extension becomes a pure canvas renderer.
- **Improve portability:** Extension no longer depends on `gamepad-node` (native addon) or TypeScript state machine code.
- **Better separation of concerns:** Gamepad polling + avatar logic lives in Python where it's tested. Extension stays thin and simple.

## Architecture

```
┌─────────────────────────────┐         HTTP GET          ┌──────────────────┐
│  Extension (Node.js)        │ ───── GET /avatar/state ──► │  ziomek serve    │
│                             │ ◄──── /avatar/state ─────  │  (single process)│
│  • Canvas rendering only    │         POST /avatar/input │                  │
│  • Sprite from disk         │         POST /tts/speak    │  ┌────────────┐  │
│  • TTS via HTTP             │         POST /avatar/input │  │ Player     │  │ ← gamepad source
│                             │         ───►               │  │ abstraction│  │    (swappable)
└─────────────────────────────┘                            │  └────────────┘  │
                                   ───►                    │  ┌────────────┐  │
                                                             │  │ TTS      │  │
                                                             │  │ Avatar   │  │
                                                             │  │ Health   │  │
                                                             │  └────────────┘  │
                                                              ───►             └──────────────────┘
```

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Single process | Gamepad polling runs in ziomek server, one Python process | Simpler deployment, zero IPC overhead |
| GIL concern | Background thread only for gamepad poll | Gamepad read is ~5-10μs, negligible CPU |
| Player abstraction | `PlayerBase` interface with `LocalPlayer`/`RelayPlayer` | Future-proof for remote server mode |
| Extension role | Pure canvas renderer + HTTP client | Minimal codebase, no gamepad deps |
| Communication | GET `/avatar/state` (extension polls 100ms) + POST `/avatar/input` (for external callers) | Clean separation of concerns |
| Sprite sheet | Extension loads from disk (unchanged) | No need to serialize PNG over HTTP |

## Component Design

### 1. Gamepad Module (`ziomek/avatar/gamepad.py`)
New module in `ziomek.avatar` package.

**`class GamepadManager`**
- `start()` — initialize pygame, discover gamepads
- `poll()` — read current gamepad state (buttons, axes)
- `stop()` — cleanup pygame resources
- Returns `GamepadState`: `{buttons: list[bool], axes: list[float], connected: bool}`

Polling runs in a background thread at 100Hz (10ms interval). Thread-safe state access via `threading.Lock`.

### 2. Player Abstraction (`ziomek/avatar/player.py`)
Defines the interface between gamepad detection and avatar state machine.

**`class PlayerBase`** (abstract)
- `start()` → `stop()` → `poll()` → `get_state()` → `dispose()`

**`class LocalPlayer(PlayerBase)`** — pygame-based implementation (current behavior)  
**`class RelayPlayer(PlayerBase)`** — HTTP relay implementation (future — for remote server mode)

Server initializes `LocalPlayer` by default. Holds reference to `PlayerBase` polymorphically.

### 3. Avatar API Changes
- **Existing:** `/api/avatar/input` (POST) — still works for external callers who push gamepad state
- **New:** `/avatar` (WebSocket) — persistent connection, ziomek pushes avatar state updates only when expression or cycleIndex changes
  - Messages: `{expression: str, cycleIndex: int}`
  - Extension tracks `lastExpression`/`lastCycleIndex` to skip duplicates
- **Unchanged:** `/api/avatar/sprite` (GET) — serves sprite sheet as base64 (one-time download)

### 4. Server Lifecycle Changes
- `ziomek/server.py` creates `LocalPlayer` on startup
- Background thread calls `player.poll()` every 10ms, feeds state to state machine
- HTTP endpoint `/api/avatar/state` queries state machine (tick with 16ms dt)

### 5. Extension Changes
- **Remove:** `GamepadService` class (~170 lines)
- **Remove:** gamepad polling loop in `extension.ts`
- **Remove:** state machine in extension (avatar state read from ziomek)
- **Remove:** `gamepad-node` from `package.json` dependencies
- **Remove:** sprite loading from avatar panel (ziomek serves it via API)
- **Keep:** `AvatarStateMachine` as a fallback/local computation (can be removed in v2)
- **Add:** WebSocket client connecting to `ws://localhost:5004/avatar` for avatar state updates

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `ziomek/ziomek/avatar/gamepad.py` | Create | Pygame gamepad polling |
| `ziomek/ziomek/avatar/player.py` | Create | Player abstraction |
| `ziomek/ziomek/api/avatar.py` | Modify | Add `/api/avatar/state` endpoint |
| `ziomek/ziomek/server.py` | Modify | Initialize `LocalPlayer`, start gamepad thread |
| `ziomek/tests/avatar/test_gamepad.py` | Create | Gamepad polling tests |
| `ziomek/tests/avatar/test_player.py` | Create | Player abstraction tests |
| `src/humanize/service.ts` | Delete | Remove `GamepadService` |
| `src/humanize/events.ts` | Delete | Remove gamepad event types |
| `src/humanize/avatar-panel.ts` | Modify | Remove sprite loading, use HTTP for state |
| `src/extension.ts` | Modify | Simplify, remove gamepad/state machine, add polling |
| `package.json` | Modify | Remove `gamepad-node` dependency |

## Testing Strategy
- **ziomek:** Unit tests for gamepad module, player abstraction, and new `/api/avatar/state` endpoint
- **Extension:** Integration tests for avatar polling loop and HTTP client

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GIL contention | Low | Medium | Gamepad read is ~5-10μs; benchmark if needed |
| pygame dependency | Low | Low | pygame is cross-platform, pip-installable |
| Extension breaks | Medium | High | Incremental migration: keep TypeScript state machine as fallback |
| Latency | Low | Low | WebSocket push — near-zero stale state, ziomek only sends when expression/cycleIndex changes |

## Open Questions
- None. WebSocket approach is cleaner, simpler, and more performant than polling.

## Future Work
- **Relay mode:** Replace `LocalPlayer` with `RelayPlayer` to talk to remote ziomek server
- **Sprite from server:** Remove local sprite loading entirely (already done via `/api/avatar/sprite`)
- **Audio in extension:** Add `AudioNode` for TTS playback (currently handled by ziomek)
