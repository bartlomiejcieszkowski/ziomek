# Transcript sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a toggleable transcript panel to the roster page that shows what happened in the call in order, and a Save menu that downloads it as Markdown or JSON.

**Architecture:** The call record (`roster.events`) is already one chronological stream across participants, so the panel reads it as-is: a new function in `src/ziomek/api/roster_view.py` exposes those entries, and the page formats them (agent line vs system sentence). The open/closed default is a settings value substituted into the served HTML at serve time; the download happens in the browser, so nothing is written by the server.

**Tech Stack:** Python 3 (FastAPI, Pydantic settings), one HTML page with plain JavaScript, pytest.

**Spec:** `docs/superpowers/specs/2026-10-31-transcript-sidebar-design.md`

## Global Constraints

- TDD, red test first; commit only after explicit user acknowledgment, with `--signoff`, no `Co-Authored-By`; nothing pushed by the agent; `docs/internal/` is never committed.
- Run tests with `uv run python -m pytest` (plain `uv run pytest` fails on this setup).
- The roster page writes text with `textContent`, never `innerHTML`.
- Config keys stay in the existing `roster_*` group in `src/ziomek/config.py`; the existing default is `open`.
- Page tests assert on the served HTML string (the pattern already used in `tests/test_roster_view.py`), no browser engine.

## Review Focus

1. An entry with no text and no author (a plain join, hold, leave) must render as the system sentence, not as `undefined` or an empty line.
2. Text that HTML would interpret (`<b>plan</b>`, an apostrophe) must appear literally on the page — `textContent`, never `innerHTML`.
3. A settings value that is not `open` or `closed` must fall back to closed, not throw.
4. A participant whose name is empty (pool empty, `join()` without a name) must not produce a line that starts with a stray separator.
5. The download must work when the record is empty — the file still downloads, with its header and no lines.

---

## Flagged decision

`/api/roster` currently returns a list of tiles; adding a `transcript` key to it would break `tests/test_roster_view.py::test_the_roster_view_lists_the_participants_of_the_call`. I chose a second endpoint (`GET /api/roster/transcript`) so the existing payload shape stays. If you want the transcript inside one payload instead, say so before Task 1 runs.

## File structure

- Modify `src/ziomek/api/roster_view.py` — transcript data + its route + the settings substitution at serve time.
- Modify `src/ziomek/resources/roster.html` — panel, toggle, line rendering, Save menu.
- Modify `src/ziomek/config.py` — one settings key.
- Tests in `tests/test_roster_view.py` and `tests/test_config.py`.

---

### Task 1: Transcript data and its route

**Files:**
- Modify: `src/ziomek/api/roster_view.py` (add `transcript()` and a route; do not change `tiles()`)
- Test: `tests/test_roster_view.py`

**Interfaces:**
- Consumes: `get_roster().events` — entries as stored by `Roster.record()` (`{"name", "action"}`, plus `"text"` and `"author"` when something is attached).
- Produces: `transcript() -> list[dict]` (the entries in order, verbatim); `GET /api/roster/transcript` returning `JSONResponse(content=transcript())`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_transcript_lists_the_call_in_order():
    client = build_app()
    roster = get_roster()
    first = roster.join("John")
    first.add_text("compiling", author="agent")
    second = roster.join("Donald", voice="bob")
    second.hold()

    entries = client.get("/api/roster/transcript").json()

    assert [(e["name"], e["action"]) for e in entries] == [
        ("John", "join"),
        ("John", "text"),
        ("Donald", "join"),
        ("Donald", "hold"),
    ]


def test_the_transcript_keeps_the_text_and_its_author():
    client = build_app()
    entry = client.get("/api/roster/transcript").json()[1]  # the join is recorded first, the text entry second

    assert entry["text"] == "compiling"
    assert entry["author"] == "agent"
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run python -m pytest tests/test_roster_view.py::test_the_transcript_lists_the_call_in_order -v`
Expected: FAIL (404 for the route, no `transcript()`).

- [ ] **Step 3: Implement `transcript() -> list[dict]` and the route** in `src/ziomek/api/roster_view.py`: `return list(get_roster().events)`, then `JSONResponse(content=transcript())`.

- [ ] **Step 4: Run the tests to verify they pass** — `uv run python -m pytest tests/test_roster_view.py -q`, all existing tests still pass.

- [ ] **Step 5: Commit**

```bash
git add src/ziomek/api/roster_view.py tests/test_roster_view.py
git commit --signoff -m "feat(api): expose the call record as one ordered stream"
```

Review focus line 1 gets its test here: an entry with no text and no author must be served unchanged (`"text"` absent, not `None`). Add `test_transcript_entries_without_text_have_no_text_key` asserting `"text" not in entries[0]`.

---

### Task 2: The default for opening the panel

**Files:**
- Modify: `src/ziomek/config.py` (`Settings`, the `roster_*` block, after `roster_check_interval`)
- Modify: `src/ziomek/api/roster_view.py:60` (`get_roster_page`)
- Test: `tests/test_config.py`, `tests/test_roster_view.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Settings.roster_transcript_default: str = "open"` (values `open`, `closed`); the token `__TRANSCRIPT_DEFAULT__` in `src/ziomek/resources/roster.html`, replaced at serve time by `get_roster_page()`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
def test_the_transcript_panel_defaults_to_open():
    assert Settings().roster_transcript_default == "open"

# tests/test_roster_view.py
def test_the_served_page_carries_the_configured_default():
    app = server.create_app(Settings(roster_transcript_default="closed", audio_backend="noop", no_stt=True, no_gamepad=True))
    client = TestClient(app)

    page = client.get("/api/roster/view").text
    assert "const initial = \"closed\";" in page
    assert "__TRANSCRIPT_DEFAULT__" not in page
```

- [ ] **Step 2:** Run both, expect FAIL.
- [ ] **Step 3:** Add the settings key; in `get_roster_page()` read `_settings` from `ziomek.server` and substitute the token, `"closed"` when the value is not `open` or `closed` (review focus line 3). Page test for that: `test_a_value_that_is_not_open_or_closed_falls_back_to_closed`.
- [ ] **Step 4:** Run the tests, expect PASS.
- [ ] **Step 5:** Commit — `git commit --signoff -m "feat(config): set the transcript panel default from config"`

---

### Task 3: The panel, its toggle, and the lines

**Files:**
- Modify: `src/ziomek/resources/roster.html`

**Interfaces:**
- Consumes: `GET /api/roster/transcript` from Task 1, `const initial` from Task 2.
- Produces: page markup with `id="roster"` (left pane) and `id="panel"` (right pane), a toggle in the panel header; JS functions `renderLine(entry)` and `formatLine(entry) -> string`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_page_has_the_panel_and_its_toggle():
    page = client.get("/api/roster/view").text
    assert 'id="panel"' in page
    assert 'id="toggle"' in page
    assert "#roster { flex: 0 0 55% }" in page
    assert "@media (max-width: 900px)" in page

def test_the_page_formats_an_agent_line():
    page = client.get("/api/roster/view").text
    assert '"entry.name, entry.author, entry.text"' in page
    assert '" — "' in page

def test_the_page_formats_a_system_line():
    page = client.get("/api/roster/view").text
    assert '(PAST[entry.action] || entry.action) + "."' in page

def test_the_page_renders_lines_with_text_content():
    # Review focus lines 2 and 4: nothing is put through innerHTML for panel lines,
    # and a line without an author keeps the sentence form.
    page = client.get("/api/roster/view").text
    assert "item.textContent" in page
    assert '"entry.name, entry.author, entry.text"' in page  # the name, the author, then the text
```

- [ ] **Step 2:** Run, expect FAIL.
- [ ] **Step 3:** Implement the grid, the toggle, `formatLine(entry) -> string` and `renderLine(entry)`; `formatLine` returns `name + " — " + text` when the entry has text and an author, otherwise `name + " " + action + "."`. For an empty name (review focus line 4) it drops the separator, so a line without a name never starts with a stray separator. The toggle hides only the transcript list, never the controls used to open it again; `#roster` takes the full width when the list is hidden. The panel opens from `const initial`; the click is then remembered by Task 5, and the label follows the current state.
- [ ] **Step 4:** Run the tests, expect PASS.
- [ ] **Step 5:** Commit — `git commit --signoff -m "feat(api): show the transcript on the roster page"`

---

### Task 4: Save with a format menu

**Files:**
- Modify: `src/ziomek/resources/roster.html`
- Test: `tests/test_roster_view.py`

**Interfaces:**
- Consumes: the formatted lines from Task 3 (same order, same wording), `formatLine`.
- Produces: `buildFilename(ext: str) -> str` using a map of the format to its extension, `markdownFile(entries) -> Blob` and `jsonFile(entries) -> Blob`, a Save control that acts on a click and a `(...)` control that opens the format menu (closed until clicked), with the two formats in the page.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_page_has_save_with_the_two_formats():
    page = client.get("/api/roster/view").text
    assert 'id="save"' in page
    assert 'data-format="markdown"' in page
    assert 'data-format="json"' in page

def test_the_saved_file_is_named_with_the_project_and_the_download_time():
    page = client.get("/api/roster/view").text
    assert "ziomek_" in page          # the pattern is ziomek_{YYYY-MM-DD}_{HHMM}_transcript.{md|json}
    assert "new Date(" in page          # the name is built from the browser clock at download time
    assert "json" in page
```

- [ ] **Step 2:** Run, expect FAIL.
- [ ] **Step 3:** Implement `buildFilename(ext)` as `"ziomek_" + date_part + "_" + time_part + "_transcript." + ext` (no `:` in the name), `formatFile()` writing the same lines the panel shows for Markdown and `JSON.stringify(entries)` for JSON, and `download(blob, name)` from an anchor. A download with no lines still writes the file header (review focus line 5): test `test_the_page_writes_a_file_with_only_its_header_when_there_is_nothing_to_save` asserting `new Blob` is used with the lines produced by `formatLine`.
- [ ] **Step 4:** Run the tests, expect PASS.
- [ ] **Step 5:** Commit — `git commit --signoff -m "feat(api): save the transcript as markdown or json"`
---

### Task 5: Remember the panel state in a cookie

**Files:**
- Modify: `src/ziomek/resources/roster.html`
- Test: `tests/test_roster_view.py`

**Interfaces:**
- Consumes: `initial` from Task 2, the toggle from Task 3.
- Produces: `readCookieState() -> str | None` and `setPanelState(state: str) -> None`, which writes `ziomek_panel=open|closed`. `initial` is used only when the cookie has nothing to read.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_page_reads_the_panel_state_from_the_cookie_before_the_config_default():
    page = client.get("/api/roster/view").text
    assert "document.cookie" in page
    assert 'ziomek_panel' in page

def test_the_page_uses_the_config_default_only_when_nothing_is_stored():
    page = client.get("/api/roster/view").text
    assert "readCookieState()" in page   # returns null when nothing is stored, and the page then uses initial
```

- [ ] **Step 2:** Run, expect FAIL.
- [ ] **Step 3:** Implement `readCookieState()` (returns `null` when `ziomek_panel` is not in the cookie) and `setPanelState(state)` on the toggle click; the opening decision is `readCookieState() || initial`, so a click survives a reload and an empty cookie follows config; the reader rejects anything that is not `open` or `closed` and a malformed escape falls back instead of throwing.
- [ ] **Step 4:** Run the tests, expect PASS.
- [ ] **Step 5:** Commit — `git commit --signoff -m "feat(api): remember the panel state in the cookie"`

Task 3's "the click is not remembered" line defers to this task. `localStorage` was weighed and left as an idea in `docs/internal/IDEAS.md` (item 11) — cookie stays the choice here because it survives reloads within the browser session.
