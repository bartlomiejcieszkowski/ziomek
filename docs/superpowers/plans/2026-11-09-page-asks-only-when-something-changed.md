# A Page That Asks Only When Something Changed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The roster page is told which part changed and asks only for that part, instead of asking for both parts every second.

**Architecture:** A signal path (`/api/roster/ws`) carries only the name of the part that changed. The app reports a change at the points where it makes one (a participant added, removed, or state-changed; an entry written to the record). A small rule module maps a signal to what to ask for, so that rule can be tested as values; the page part follows it and no longer asks on its own. The shapes the page reads stay in `src/ziomek/api/roster_view.py`.

**Tech Stack:** Python 3 (FastAPI, `starlette.testclient.TestClient` with `websocket_connect`), plain JavaScript in page parts, pytest, `node --test` for value tests.

**Spec:** `docs/superpowers/specs/2026-11-09-page-asks-only-when-something-changed-design.md`

## Global Constraints

- TDD, red test first; commit after each task with `--signoff`, no `Co-Authored-By`, subject ≤72 chars as `<type>(scope): description`; nothing pushed by the agent; `docs/internal/` is never committed.
- Run tests with `uv run python -m pytest`; plain `python` cannot import ziomek. Do not run whole test files that reach the model or the network offline.
- JavaScript value tests run per file: `node --test tests/ziomek/resources/static/<file>.test.mjs` (`node --test tests/` discovers nothing in this environment).
- Test names state behaviors, not code facts; one behavior per test; a test reads the part it is about. A string test is used only for what cannot be checked as a value.
- No test can see a render, so a rule that cannot be called as a value cannot be tested here — that is why the mapping lives in its own part.
- `uv run ruff format --check .` must be clean on the files touched; HTML and `.mjs` are not ruff-formatted, and `.gitattributes` line endings are respected (page parts in `src/ziomek/resources/static/` are CRLF).
- Feature commits do not touch `CHANGELOG.md` or `VERSION`.

## Review Focus

1. A page whose connection drops must get the whole picture when it comes back, not only the changes after that — a join while disconnected would otherwise never show. Test in Task 3, Step 1.
2. A signal that names nothing must leave the page asking for nothing, rather than asking for both parts. Test in Task 2, Step 1.
3. Every open page is told what changed, not only the last one that was connected. Test in Task 1, Step 1.
4. A change that happens while no page is listening must not raise, and the app must keep working. Test in Task 1, Step 1.
5. A signal arriving from a synchronous path (a join through the tools) must reach the page through the server's event loop, as `src/ziomek/api/avatar_ws.py` already does with `call_on_event_loop`. Test in Task 1, Step 1.

The look and the way the debug box updates less often (it prints only when the page draws, so it now updates on changes rather than every second) cannot be checked offline; they are confirmed by the person viewing the page.

## File structure

- `src/ziomek/api/roster_ws.py` — the signal path and the clients it tells; nothing about drawing.
- `src/ziomek/roster.py` — the hook that reports what changed, and the points where a change happens.
- `src/ziomek/resources/static/signal.mjs` — the rule that maps a signal to what to ask for; no DOM.
- `src/ziomek/resources/static/roster.mjs` — the page part: it asks once at load, then follows the rule; no timer.
- Tests: `tests/test_a_page_is_told_what_changed.py`, `tests/ziomek/resources/static/signal.test.mjs`, `tests/ziomek/resources/static/page_parts.test.mjs`.

---

### Task 1: The app reports what changed

**Files:**
- Create: `src/ziomek/api/roster_ws.py`
- Modify: `src/ziomek/roster.py` (`__init__` gains the hook; `join`, `release`, `drop_quiet`, `Participant.hold`, `Participant.resume`, and the append in `record` at `:325` report it), and `build_roster` at `src/ziomek/roster.py:346-362` wires it
- Modify: `src/ziomek/server.py:199` (include the new router next to the one for the single view)
- Test: `tests/test_a_page_is_told_what_changed.py`

**Interfaces:**
- Consumes: `call_on_event_loop` from `src/ziomek/event_loop.py` (as used at `src/ziomek/api/avatar_ws.py` — see Task 1 note); `TestClient.websocket_connect`.
- Produces: `Roster(changed=...)` with the hook called as `self.changed("room")` or `self.changed("record")`; `roster_ws.tell_page(kind: str) -> None`; a message to a connected page of the shape `{"kind": "room"}` or `{"kind": "record"}`; the path `/api/roster/ws`.

- [ ] **Step 1: Write the failing tests**

Names and what each asserts, one behavior per test:

- `test_a_page_is_told_that_the_room_changed_when_someone_joins` — connect, `roster.join("John")`, receive one message whose `kind` is `room`.
- `test_a_page_is_told_that_the_record_grew_when_a_line_is_written` — connect, `participant.add_text("compiling", author="agent")`, receive a message whose `kind` is `record`.
- `test_a_page_is_told_that_the_room_changed_when_a_participant_is_held` and `..._when_a_participant_leaves` — the same shape with `kind` `room`.
- `test_a_page_is_told_only_about_what_changed` — nothing is received when no participant and no line changed.
- `test_a_join_that_also_writes_to_the_record_is_told_as_two_changes` — both kinds arrive, and neither is combined into one message.
- `test_every_open_page_is_told_what_changed` — two clients connected, one change, both receive the same `kind`.
- `test_the_app_still_works_when_no_page_is_connected_to_be_told` — a join with no client raises nothing and the participant is still added.
- `test_a_change_that_comes_through_the_tools_reaches_a_connected_page` — the join through the tool path (the same entry point the running app uses), not through `Roster` directly.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run python -m pytest tests/test_a_page_is_told_what_changed.py -v`
Expected: FAIL — no `changed` hook, and no route for `/api/roster/ws`.

- [ ] **Step 3: Implement the path and the hook**

`src/ziomek/api/roster_ws.py`: `_connected_clients`, `register_client(websocket)`, `remove_client(websocket)`, `async def broadcast(message)`, and `def tell_page(kind: str) -> None` that schedules the broadcast on the event loop only when a client is connected (the same shape as `avatar_ws.notify_change`). The route accepts a connection and registers it; it sends nothing on connect, because the page asks for the picture itself.

`src/ziomek/roster.py`: `changed=None` in `__init__`, stored as `self.changed`; every call is guarded so that a roster built without the hook still works. `build_roster` passes `changed=roster_ws.tell_page`. The existing `push_hook` and `machine.on_change = self.push_hook` (`:216`) are not touched.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run python -m pytest tests/test_a_page_is_told_what_changed.py -v`
Expected: PASS. Then `uv run ruff format --check .` on the files touched.

- [ ] **Step 5: Commit**

`git add src/ziomek/api/roster_ws.py src/ziomek/roster.py src/ziomek/server.py tests/test_a_page_is_told_what_changed.py` and commit as `feat(app): a page is told which part changed` with the reason in the body: a page that asks every second costs requests even when nothing happened.

---

### Task 2: The rule that maps a signal to what to ask for

**Files:**
- Create: `src/ziomek/resources/static/signal.mjs`
- Test: `tests/ziomek/resources/static/signal.test.mjs`

**Interfaces:**
- Consumes: nothing but the signal object produced by Task 1 (`{kind}`).
- Produces: `what_to_ask_for(signal)` returning `["room"]`, `["record"]`, or `[]`; `what_to_ask_on_connection()` returning `["room", "record"]`. Both pure, no DOM, so the tests call them as values.

- [ ] **Step 1: Write the failing value tests**

Names, each calling the export:
- `test a signal that names the room asks for the room only` — `what_to_ask_for({kind: "room"})` equals `["room"]`.
- `test a signal that names the record asks for the record only` — equals `["record"]`.
- `test a signal that names nothing asks for nothing` — `what_to_ask_for({})` and `what_to_ask_for({kind: "expression"})` both equal `[]`.
- `test a page that connects is asked for both parts once` — `what_to_ask_on_connection()` equals `["room", "record"]`.

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/ziomek/resources/static/signal.test.mjs`
Expected: FAIL — the module does not exist.

- [ ] **Step 3: Implement the rule**

`src/ziomek/resources/static/signal.mjs` with the two exports, in the style of `numbers.mjs`: a comment line saying what the file holds, no DOM, no fetch. A signal with a kind outside `room` and `record` returns `[]` — the page must not ask for something it was not told about.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `node --test tests/ziomek/resources/static/signal.test.mjs`
Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

`git add src/ziomek/resources/static/signal.mjs tests/ziomek/resources/static/signal.test.mjs` and commit as `feat(page part): the rule that decides what to ask for is separate so it can be tested`.

---

### Task 3: The page follows the rule and stops asking on its own

**Files:**
- Modify: `src/ziomek/resources/static/roster.mjs` (`refresh()` at `:414` split into `draw_room()` and `draw_record()`; `start()` at `:459-461` keeps the first read and connects to `/api/roster/ws`; no `setInterval`)
- Test: `tests/ziomek/resources/static/page_parts.test.mjs`

**Interfaces:**
- Consumes: `what_to_ask_for(signal)` and `what_to_ask_on_connection()` from Task 2; the existing `render(tiles)` and `renderBlock(block)` stay as they are.
- Produces: nothing other tasks need.

- [ ] **Step 1: Write the failing tests**

In `tests/ziomek/resources/static/page_parts.test.mjs`:
- `test the page asks only for what it was told about` — the part calls `what_to_ask_for` and, for each name it returns, calls the matching drawer (`draw_room` for `room`, `draw_record` for `record`) and not the other; it must not call both after one signal.
- `test the page asks for the whole picture when its connection is open again` — the part calls `what_to_ask_on_connection()` when a connection is established, so a change made while it was away is not lost.
- `test the page does not ask on its own after the first picture` — no `setInterval(` in the part. A string test, because a timer is not something a value test can reach here.
- `test a page that cannot keep the connection asks again after three seconds` — the retry delay is the same value `debug.html:387` uses (`3000`), stated in the part rather than left to the browser default.

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/ziomek/resources/static/page_parts.test.mjs`
Expected: FAIL on the new tests; the existing ones in that file stay green.

- [ ] **Step 3: Implement the page side**

Split `refresh()` so each part can be asked for on its own, keeping the incremental append that is there today (the record grows by adding lines to the box already on screen). The connection is opened in `start()`, then: on a signal, ask for what the rule names; on a connection being established, ask for both once; on a drop, reconnect after 3000. No timer remains.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `node --test tests/ziomek/resources/static/page_parts.test.mjs` and `node --test tests/ziomek/resources/static/signal.test.mjs`
Expected: PASS. Then `uv run python -m pytest tests/test_roster_view.py tests/test_roster_debug.py tests/test_parts_are_answered_by_type.py -q` — the existing page tests must stay green, and any test that asserted the timer is replaced, not kept.

- [ ] **Step 5: Commit**

`git add src/ziomek/resources/static/roster.mjs tests/ziomek/resources/static/page_parts.test.mjs` and commit as `fix(page part): the page asks only for what it was told about`.

## What the plan cannot prove

The look of the page, and that a quiet room really costs zero requests in a browser, are checked by the person viewing it. The plan proves the rule: what a signal leads to, and that nothing is asked on a timer.
