# Call mode — roster design

## Context

Two things exist today:

- `src/ziomek/api/avatar.py` serves `src/ziomek/resources/renderer.html` and pushes state over WebSocket (`src/ziomek/api/avatar_ws.py`). The payload carries expression and cycle info in `status`; nothing carries a name or the message text. The renderer draws on messages only (`FRAME_DURATION = 200`) and has no clock of its own.
- `src/ziomek/avatar/state_machine.py` is instantiated once in `src/ziomek/server.py:150` as a global `_state_machine`, and `src/ziomek/mcp/tools.py` writes into it. The gamepad thread (`src/ziomek/server.py:57`) feeds inputs into that same machine.

The goal is a "call" — agents take turns, like a Teams call. An agent can join, take a name and a voice, keep its own expression, and show text below its tile (a status line, and an on-hold area).

Two capabilities, independent, in that order:

1. **Single view** — the existing page gains a name and a status text. Small change, no new project.
2. **Roster** — the call page. Separate feature; the single view stays as it is (it shows the agent itself, no human tile).

Names below follow `docs/superpowers/specs/2026-09-17-gamify-ai-design.md` (`RosterView`, `RosterControl`). There is no `features.py` module in the repo yet, so these are vocabulary for code we would write, not existing structures. `Join` is the name I propose for the MCP capability.

## Shape

The value lives in a roster because it needs multiple participants, and each participant needs its own state machine — the single global machine cannot serve two agents on one PC. So `Roster` is the core capability, and both the single view and `RosterView` are renderers of it. The small change to the single view does not need a roster: it needs fields in the payload.

That is why part 1 ships first and part 2 builds on it.

## Part 1 — single view

- WebSocket payload gains two separate fields: `name` and `status_text`. Existing fields stay as they are so clients and tests keep working; new fields are `None` when not provided.
- The renderer shows the tile name from the payload (never a hardcoded string), and text below the tile for `status_text`.
- The single view is the simplified rendering of one participant: the first one to join. Name, text, and expression come from that participant's record and its own machine, so it is not a second renderer of a shared machine.
- No audio change: `mix_play` in `src/ziomek/tts/playback.py` already plays overlapping sounds for the backends that support mixing.

## Part 2 — roster

### Participants

A participant record holds: name, display name, voice, expression, status text, on-hold text, and its own `AvatarStateMachine` created at join. Expression comes from tool calls that name the participant they are for; the global avatar is the fallback when nothing is named. The gamepad does not drive expressions — it is inert for now and is meant to become a control method later, so polled input is applied to nothing.

Identity is the agent's responsibility: it states a name at join. First assignment wins **within a session only**; nothing persists across calls, and a name stated in a later session is used as-is with no lookup. Connection id is only a hint — the MCP transport drops quiet sessions before our timer would, so participant records must be our own, keyed by name, with a last-seen time.

### Pool

The pool is a configurable list of name-and-voice pairs in `ziomek_config.yaml`, you adjust it. A name without a voice draws from an unused entry; if nothing is unused, from the least used — and the same rule in reverse for a voice without a name. The rule applies across calls, so entries need usage counts kept separately from participants.

Duplicate base names are disambiguated by suffix (`John A.`, `John B.`). A participant's display name stays fixed for its whole presence in the call, so taken suffixes must be tracked per base name. If the agent names itself as `John` with no suffix, that is a different record from `John A.` — not a rename, so the page can show both.

Within a call, names must be unique: joining with a name already in the call is rejected as a duplicate. A second agent on the same PC gets its own record, so two agents on one machine are distinct participants.

Names are optional at join; if none is given we generate one from the pool.

### Call lifecycle and hold

One call at a time, opened by the first join; closing it clears participants and resets usage counts. Tool calls take an optional `call_id` argument that is reserved but unused: the client does not have to fill it, and there is a default. Nothing reads it yet — accepting it is all that exists, so multi-call support is not implied by it. A participant is dropped by a configurable inactivity timer set in config — your example was 3000 seconds — which releases its name and voice.

Agents manage their own membership through tool calls: join, leave, and **hold** — "I'm going to be quiet for a while", which suspends the timer. So each record needs a state, active or held.

### Page

Live tiles plus a record of what happened (join, hold, leave, and the text attached to each). The record lives only for this call: it is cleared with the call, same lifetime as the usage counts. Nothing here is written to disk — the pool and its voice mappings live in config, which you write; runtime assignments for generated names are not stored anywhere.

Each tile has two text areas: a status line and an on-hold area that may carry its own messages. Text needs provenance — what the agent typed vs what the system wrote — so the page can tell them apart. A held participant looks visibly distinct: a pause indicator with elapsed hold time (`On hold XX:XX`), as Teams shows. That needs join time and hold-start time, and a client-side tick — the current renderer only redraws on messages, so an elapsed duration cannot come from the server push.

### Tests (TDD, three behaviors)

1. The payload carries `name` and `status_text` when provided, and `None` when not.
2. Join without a name draws from unused pool entries; when all are taken it draws from the least used; duplicate base names get the suffix, and the display name stays fixed for that participant.
3. The inactivity timer drops a participant and releases its name and voice, while a held participant is exempt until it resumes.

## Out of scope

- No persistence, no cross-call memory, nothing written to disk.
- No second call at the same time, no human tile on the roster page, no feature-flag system for the roster.
- No changes to STT, no new audio backend, no session-level state in MCP (the transport keeps one global `_listening_session` in `src/ziomek/mcp/tools.py`; per-participant listening would be new work, not assumed here).
- No voice model choice: `src/ziomek/tts/voice.py` picks the default voice from the catalog; the pool maps names to voices, which is separate from selecting a model.
