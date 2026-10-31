# Transcript groups and markdown shape Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the record as runs of consecutive messages from the same participant, in the panel and in the saved markdown file, with the colors and markers decided in the spec.

**Architecture:** Grouping and the system-line wording move to Python in `src/ziomek/api/roster_view.py`, because they are rules a test can check; the page renders what the payload gives it as boxes, and the markdown text is assembled from the same blocks. The browser still performs the download, so nothing is written on disk.

**Tech Stack:** Python 3.12 with FastAPI (no routes for the file), Pydantic settings, pytest; page-side JavaScript with `textContent` only.

**Spec:** `docs/superpowers/specs/2026-10-31-transcript-sidebar-design.md` (Decided parts: grouping by consecutive runs, colors, box style, file shape with blockquote)

## Global Constraints

- TDD, red test first; commit with `--signoff`, no co-author trailer, nothing pushed, `docs/internal/` is never committed, ruff format only on files touched.
- The roster page reads values with `textContent`, never `innerHTML`.
- Page tests assert served HTML strings — there is no browser engine in this repo's tests; behavior-only checks are flagged as weak tripwires, and rules that can be tested in Python are moved there.
- Config keys stay in the existing `roster_*` group.
- A hard line break in markdown needs two trailing spaces; the writer must not trim them.

## Review Focus

- A message line written by our own file builder must keep its two trailing spaces — without them a markdown viewer joins the messages back into one paragraph.
- A record whose entries are interleaved across participants must still show the order — grouping is by run, not by participant block.
- A group with no lines produces no box, and a group with no lines produces nothing at all (a test in Task 1 checks the empty group is dropped).
- An action word outside the mapping keeps the word from the record instead of an invented sentence.
- A failed poll must not clear what the panel already showed — `tests/test_roster_view.py::test_the_page_survives_a_failed_poll` already covers this, so Task 3 keeps it rather than adding a new test.

---

### Task 1: Grouping and wording on the server

**Files:**
- Create: `src/ziomek/api/roster_view.py` additions (`blocks`, `sentence`)
- Modify: `src/ziomek/api/roster_view.py` (`transcript()` stays as the ordered entry list; the served payload gains `blocks`)
- Test: `tests/test_roster_view.py`

**Interfaces:**
- Consumes: the record entries as returned by `Roster.events` (`name`, `action`, optional `text`, optional `author`).
- Produces:
  - `def sentence(entry: dict) -> str` — returns the system line, e.g. `"John joined."`; an unknown action uses the word stored in the record.
  - `def blocks(entries: list[dict]) -> list[dict]` — the ordered stream, where each item is either `{"kind": "system", "text": ...}` or `{"kind": "group", "name": ..., "author": ..., "lines": [...]}`. A group is the consecutive text entries of one participant; system lines stay as their own items in place.

- [ ] **Step 1: Write the failing test**

```python
def test_grouping_follows_the_order_of_the_record():
    entries = [
        {"name": "John", "action": "join"},
        {"name": "Donald", "action": "join"},
        {"name": "Donald", "action": "text", "text": "playing darts", "author": "agent"},
        {"name": "John", "action": "text", "text": "wait, are we still talking?", "author": "agent"},
        {"name": "Donald", "action": "text", "text": "now mowing the lawn", "author": "agent"},
        {"name": "Donald", "action": "leave"},
    ]
    assert [b["kind"] for b in blocks(entries)] == [
        "system", "system", "group", "group", "group", "system"
    ]
    assert blocks(entries)[3]["name"] == "John"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_roster_view.py::test_grouping_follows_the_order_of_the_record -q`
Expected: FAIL

- [ ] **Step 3: Add the failing test for an empty group**

```python
def test_a_participant_with_no_message_produces_no_group():
    entries = [{"name": "John", "action": "join"}, {"name": "John", "action": "text", "text": "", "author": "agent"}]
    assert blocks(entries) == [{"kind": "system", "text": "John joined."}]
```

Run: `uv run python -m pytest tests/test_roster_view.py::test_a_participant_with_no_message_produces_no_group -q`
Expected: FAIL

- [ ] **Step 4: Implement `blocks` in `src/ziomek/api/roster_view.py`**

Walk the entries in order; consecutive text entries with the same `name` and an author that is not `system` form one group; anything else stays as its own item. Do not merge a later run into an earlier group of the same participant.

- [ ] **Step 5: Write the failing test for the wording**

```python
def test_the_system_line_is_a_sentence_with_the_word_from_the_record():
    assert sentence({"name": "John", "action": "join"}) == "John joined."
    assert sentence({"name": "John", "action": "hold"}) == "John is on hold."
    assert sentence({"name": "John", "action": "left"}) == "John left."
    assert sentence({"name": "John", "action": "something"}) == "John something."
```

- [ ] **Step 6: Run and implement `sentence`, then pass both tests**

Run: `uv run python -m pytest tests/test_roster_view.py -q`
Expected: FAIL for the new tests, PASS after the implementation.

- [ ] **Step 7: Commit**

```bash
git add src/ziomek/api/roster_view.py tests/test_roster_view.py
git commit -m "feat(api): group the record into runs of the same participant" --signoff
```

### Task 2: The markdown text, with its markers

**Files:**
- Modify: `src/ziomek/api/roster_view.py` (`markdown_text`)
- Test: `tests/test_roster_view.py`

**Interfaces:**
- Consumes: `blocks()` and `sentence()` from Task 1.
- Produces: `def markdown_text(blocks: list[dict], timestamp: str) -> str` — the file content: a title line, then a heading per group with its message lines, and a blockquote for each system line. `timestamp` is the clock the page sends (`?at=...`), which is what the spec decides.

- [ ] **Step 1: Write the failing test**

```python
def test_the_markdown_file_keeps_its_group_and_its_hard_break():
    blocks = [{"kind": "group", "name": "Donald", "author": "agent", "lines": ["playing darts"]}]
    text = markdown_text(blocks, "2026-10-31T14:20:04Z")
    assert text.startswith("# transcript — 2026-10-31T14:20:04Z\n\n")
    assert "### Donald (agent)\nplaying darts  \n" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_roster_view.py::test_the_markdown_file_keeps_its_group_and_its_hard_break -q`
Expected: FAIL

- [ ] **Step 3: Implement `markdown_text`**

One heading per group, the message lines with two trailing spaces, and a blockquote line for each system item. No line is rewritten; the order is the order in `blocks`.

- [ ] **Step 4: Write the test for the blockquote form**

```python
def test_a_system_line_is_a_quote_in_the_file():
    blocks = [{"kind": "system", "text": "John joined."}]
    assert "> John joined." in markdown_text(blocks, "2026-10-31T14:20:04Z")
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `uv run python -m pytest tests/test_roster_view.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/ziomek/api/roster_view.py tests/test_roster_view.py
git commit -m "feat(api): write the transcript as markdown with groups and quotes" --signoff

### Task 3: The page renders groups as boxes with the colors

**Files:**
- Modify: `src/ziomek/resources/roster.html` (panel markup, group boxes, color classes)
- Test: `tests/test_roster_view.py`

**Interfaces:**
- Consumes: the payload from `GET /api/roster/transcript`, which now carries `blocks`.
- Produces: a panel that shows each block as one box; system items as their own lines; the group header is `name (agent)`.

- [ ] **Step 1: Write the failing tests (contract strings, which are the strong ones)**

```python
def test_the_page_has_the_colors_and_the_box_shape():
    page = served_page()
    assert "#box { background: #2a2a30; border: 1px solid #4a4a52; margin-bottom: 14px; }" in page
    assert ".name { color: #8ab4f8; }" in page
    assert ".event { color: #e0a568; }" in page
    assert ".system_text { color: #7fb069; }" in page
    assert 'nameEl.append(el_class("name"))' in page

def test_the_page_writes_the_group_header_with_the_author():
    assert 'name + " (agent)"' in page
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_roster_view.py -q`
Expected: FAIL — the page currently builds one flat list without boxes or colors.

- [ ] **Step 3: Implement the panel render from `blocks`**

One box per group, in order; system items as their own lines between boxes. The name and the author part are separate elements with the classes above, and their content is set with `textContent` — a colored name needs its own element, which is markup for styling while the record text stays in `textContent`. The name on the tile uses the same `.name` class. A group with no lines produces no box. The weak behavior-only checks left in this file are flagged in the tests as tripwires, not as proof.

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run python -m pytest tests/test_roster_view.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ziomek/resources/roster.html tests/test_roster_view.py
git commit -m "feat(api): show the transcript as groups with the decided colors" --signoff
```

### Task 4: The download uses the markdown text that the server builds

**Files:**
- Modify: `src/ziomek/api/roster_view.py` (add `GET /api/roster/transcript/markdown`)
- Modify: `src/ziomek/resources/roster.html` (`buildFilename`, `markdownFile`, `download`)
- Test: `tests/test_roster_view.py`

**Interfaces:**
- Consumes: `markdown_text()` from Task 2.
- Produces: `GET /api/roster/transcript/markdown` returning the file content as text; the page keeps a `Blob` download, and the timestamp it passes is the browser clock at download time. JSON stays `JSON.stringify` of the payload.

- [ ] **Step 1: Write the failing test**

```python
def test_the_page_asks_for_the_file_content_and_keeps_the_download_in_the_browser():
    page = served_page()
    assert 'fetch("/api/roster/transcript/markdown?at="' in page
    # The code names the file through the function and downloads the text it is given.
    assert "async def save(format, at)" in page and 'link.download = name' in page
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_roster_view.py -q`
Expected: FAIL

- [ ] **Step 3: Implement the route and change the page to fetch the text instead of building it**

The route returns `markdown_text(blocks(...), at)` with `at` taken from the query value the page sends, so the clock in the filename stays the browser clock at download time. Keep the existing guard for a failed fetch, and keep revoking the object URL on the next tick.

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run python -m pytest tests/test_roster_view.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ziomek/api/roster_view.py src/ziomek/resources/roster.html tests/test_roster_view.py
git commit -m "feat(api): build the markdown file from the server and download it in the browser" --signoff
```

### Task 5: Update the tests that describe the old flat line

**Files:**
- Modify: `tests/test_roster_view.py` (`test_the_page_words_the_actions_as_the_spec_sentences`, `test_the_page_builds_each_line_the_other_way`)

- [ ] **Step 1: Change those tests to the block form**

`test_the_page_words_the_actions_as_the_spec_sentences` moves to `sentence()` in Python; `test_the_page_builds_each_line_the_other_way` asserts the group header with the author and that a message line is its own entry, not a joined flat line; `test_the_panel_and_the_saved_file_write_the_same_lines` gains the markers (`### name (agent)`, the two trailing spaces, the `>` for a quoted line).

- [ ] **Step 2: Run the whole suite**

Run: `uv run python -m pytest . -q`
Expected: PASS (432 or more tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_roster_view.py
git commit -m "test(api): read the transcript as groups, not as flat lines" --signoff
```
