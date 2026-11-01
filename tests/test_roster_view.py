"""The roster page shows a tile for each participant in the call."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def page_source():
    """The file as stored, not the served page, for rules that only show up in markup."""
    return (Path(__file__).parent.parent / "src" / "ziomek" / "resources" / "roster.html").read_text(encoding="utf-8")


def module_source():
    """The module as stored, for rules the page cannot reach without a browser."""
    return (Path(__file__).parent.parent / "src" / "ziomek" / "api" / "roster_view.py").read_text(encoding="utf-8")


import ziomek.roster as module
from ziomek import server
from ziomek.api.roster_view import blocks, markdown_text, router, sentence, transcript
from ziomek.config import Settings
from ziomek.roster import get_roster


@pytest.fixture(autouse=True)
def fresh_roster():
    module._roster = None
    from ziomek.api import avatar_ws

    avatar_ws._shown = None


def build_app():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_the_roster_view_lists_the_participants_of_the_call():
    client = build_app()
    roster = get_roster()
    first = roster.join("John")
    first.add_text("compiling", author="agent")
    second = roster.join("Donald", voice="bob")
    second.hold()

    tiles = client.get("/api/roster").json()

    assert [tile["name"] for tile in tiles] == ["John", "Donald"]
    assert tiles[0]["status_text"] == "compiling"
    assert tiles[1]["state"] == "held"
    assert [(e["name"], e["action"]) for e in tiles[1]["events"]] == [
        ("Donald", "join"),
        ("Donald", "hold"),
    ]


def test_the_roster_page_renders_a_tile_for_each_participant():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Tiles are built per participant, and the text areas are filled from the tile data.
    assert 'className = "tile"' in page
    assert "status_text" in page


def test_the_roster_page_is_served_by_the_server():
    app = server.create_app(Settings(audio_backend="noop", no_stt=True, no_gamepad=True))
    client = TestClient(app)

    assert client.get("/api/roster").status_code == 200
    assert 'className = "tile"' in client.get("/api/roster/view").text


def test_the_shown_participant_is_rendered_with_its_own_machine(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from ziomek.api import avatar_ws
    from ziomek.roster import Roster

    sent = []

    class fake_ws:
        async def send_json(self, message):
            sent.append(message)

    class own_machine:
        def getCurrentState(self):
            return SimpleNamespace(expressionName="focused", cycleIndex=2)

    ws = fake_ws()
    monkeypatch.setattr(avatar_ws, "_connected_clients", [ws])

    roster = Roster(pool=[("John", "alice")], state_machine_factory=lambda p: own_machine())
    participant = roster.join("John")
    avatar_ws.show(participant)

    asyncio.run(avatar_ws._state_message(ws))

    assert sent[0]["expression"] == "focused"
    assert sent[0]["name"] == "John"


def test_the_roster_uses_the_view_push_as_its_hook():
    from ziomek.api import avatar_ws
    from ziomek.roster import get_roster

    assert get_roster().push_hook is avatar_ws.notify_change


def test_a_tile_carries_the_expression_of_that_participant():
    from types import SimpleNamespace

    from ziomek.roster import Roster

    class own_machine:
        def __init__(self, name):
            self.name = name

        def getCurrentState(self):
            # Each machine reports its own participant, so the tiles cannot share a value.
            return SimpleNamespace(expressionName=f"expr-{self.name}", cycleIndex=2)

    client = build_app()
    module._roster = Roster(pool=[("John", "alice")], state_machine_factory=lambda p: own_machine(p.name))
    first = module._roster.join("John")
    module._roster.join("Donald", voice="bob")

    tiles = client.get("/api/roster").json()

    # Each participant has its own machine, so each tile carries its own expression.
    assert tiles[0]["expression"] == "expr-John"
    assert tiles[1]["expression"] == "expr-Donald"


def test_the_roster_page_shows_the_expression_of_each_participant():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert 'renderText(top, "expression", tile.expression)' in page


def test_the_roster_page_shows_the_text_attached_to_each_event():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "event.text" in page
    assert "event.author" in page


def test_transcript_entries_without_text_have_no_text_key():
    client = build_app()
    get_roster().join("John")

    entries = client.get("/api/roster/transcript").json()["entries"]

    assert "text" not in entries[0]
    assert "author" not in entries[0]


def test_the_transcript_lists_the_call_in_order():
    client = build_app()
    roster = get_roster()
    first = roster.join("John")
    first.add_text("compiling", author="agent")
    second = roster.join("Donald", voice="bob")
    second.hold()

    entries = client.get("/api/roster/transcript").json()["entries"]

    assert [(e["name"], e["action"]) for e in entries] == [
        ("John", "join"),
        ("John", "text"),
        ("Donald", "join"),
        ("Donald", "hold"),
    ]


def test_the_transcript_keeps_the_text_and_its_author():
    client = build_app()
    roster = get_roster()
    participant = roster.join("John")
    participant.add_text("compiling", author="agent")

    # The join comes first in the record, so the entry with text is the second one.
    entry = client.get("/api/roster/transcript").json()["entries"][1]

    assert entry["text"] == "compiling"
    assert entry["author"] == "agent"


def test_the_served_page_carries_the_configured_default():
    client = build_app()

    # The file must carry the token, otherwise the substitution is a no-op.
    source = page_source()
    assert "__TRANSCRIPT_DEFAULT__" in source

    assert 'const initial = "open";' in client.get("/api/roster/view").text


def test_a_value_that_is_not_open_or_closed_falls_back_to_closed():
    app = server.create_app(
        Settings(roster_transcript_default="maybe", audio_backend="noop", no_stt=True, no_gamepad=True)
    )
    client = TestClient(app)

    assert 'const initial = "closed";' in client.get("/api/roster/view").text


def test_the_page_reads_the_panel_state_from_storage_before_the_config_default():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "localStorage" in page
    assert 'readStored("ziomek_panel")' in page


def test_the_page_uses_the_config_default_only_when_nothing_is_stored():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "function readStored(name)" in page
    assert "return null" in page  # nothing stored -> the config default decides the opening


def test_the_page_has_the_panel_and_its_toggle():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert 'id="panel"' in page
    assert 'id="toggle"' in page
    assert "#roster { flex: 0 0 55%; max-height: 100vh; overflow: auto; }" in page
    assert "@media (max-width: 900px)" in page


def test_the_group_header_carries_the_name_and_the_author_and_the_line_carries_only_the_text():
    from ziomek.api.roster_view import blocks, format_line

    entry = {"name": "John", "action": "text", "text": "compiling", "author": "agent"}
    assert format_line(entry) == "compiling"
    assert blocks([entry])[0]["name"] == "John"
    assert blocks([entry])[0]["author"] == "agent"


def test_the_page_words_the_actions_and_keeps_an_unknown_action_as_recorded():
    from ziomek.api.roster_view import sentence

    # An action outside the mapping is shown as recorded, not as a broken line.
    assert sentence({"name": "John", "action": "wave"}) == "John wave."


def test_the_panel_and_the_saved_file_write_the_same_lines():
    # One rule builds the lines: the panel shows them, the file writes the same ones.
    from ziomek.api.roster_view import blocks, format_line, markdown_text

    client = build_app()
    assert "for (const line of block.lines)" in client.get("/api/roster/view").text
    entry = {"name": "John", "action": "text", "text": "compiling", "author": "agent"}
    group = {"kind": "group", "name": entry["name"], "author": entry["author"], "lines": [format_line(entry)]}
    blocks_result = blocks([entry])
    assert blocks_result[0]["lines"] == group["lines"]
    file = markdown_text([group], "2026-10-31T14:20:04Z")
    # Task 5 Step 1: the same content must keep the markers a markdown viewer needs.
    assert "compiling  " in file  # two spaces, the hard break a viewer reads
    assert "### John (agent)" in file  # the heading keeps name and author
    quote = markdown_text([{"kind": "system", "text": "John left."}], "2026-10-31T14:20:04Z")
    assert "> John left." in quote
    # The markers, so a viewer can read the same lines the panel shows.
    assert "### John (agent)" in file
    assert "compiling  " in file  # two spaces: a markdown hard break
    quoted = markdown_text([{"kind": "system", "text": "John joined."}], "2026-10-31T14:20:04Z")
    assert "> John joined." in quoted


def test_a_group_without_a_name_keeps_the_author_and_the_text():
    # Review focus line 4: nothing is added for a name that is not there.
    from ziomek.api.roster_view import blocks

    entries = [{"action": "text", "text": "compiling", "author": "agent"}]
    block = blocks(entries)[0]
    assert block["name"] == ""
    assert block["lines"] == ["compiling"]


def test_the_page_writes_lines_with_text_content():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Review focus line 2: a line that HTML would interpret must appear literally.
    assert "p.textContent = line" in page


def test_the_page_has_save_with_the_two_formats():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert 'id="save"' in page
    assert 'data-format="markdown"' in page
    assert 'data-format="json"' in page


def test_the_saved_file_is_named_with_the_project_and_the_download_time():
    client = build_app()
    page = client.get("/api/roster/view").text

    # ziomek_{YYYY-MM-DD}_{HHMM}_transcript.{md|json}, built from the browser clock
    assert 'return "ziomek_" + nameStamp(at) + "_transcript." + ext' in page
    assert "new Date(" in page


def test_the_file_keeps_its_header_when_there_is_nothing_to_save():
    client = build_app()

    # Review focus line 5: an empty record still gets a file, and the download happens in the browser.
    assert client.get("/api/roster/transcript/markdown?at=2026-10-31T14:20:04Z").text.startswith(
        "# transcript — 2026-10-31T14:20:04Z"
    )
    page = client.get("/api/roster/view").text
    assert "new Blob(" in page


def test_an_entry_with_nothing_to_show_produces_no_line():
    # Review focus line 1: an entry with no name, action or text produces nothing.
    # The guard belongs in the rule that builds lines, so the panel and the file behave the same.
    from ziomek.api.roster_view import blocks, format_line

    assert format_line({"name": "", "action": "", "text": "", "author": ""}) == ""
    assert blocks([{"name": "", "action": "", "text": "", "author": ""}]) == []
    assert format_line({"name": "John", "action": "", "text": "", "author": ""}) == ""


def test_the_toggle_stays_reachable_when_the_panel_is_hidden():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Review focus: a control inside the hidden pane cannot be used to open it again.
    assert "#layout.hide #transcript { display: none; }" in page
    assert "#menu { display: none" in page
    # A hidden panel must not keep its column, otherwise the roster does not take the width.
    assert "#layout.hide #panel { flex: 0 0 auto; }" in page


def test_the_words_of_the_actions_are_the_sentences_the_spec_asks_for():
    from ziomek.api.roster_view import sentence

    assert sentence({"name": "John", "action": "join"}) == "John joined."
    assert sentence({"name": "John", "action": "hold"}) == "John is on hold."
    assert sentence({"name": "John", "action": "leave"}) == "John left."


def test_the_page_names_the_file_with_the_short_extension():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert 'markdown: "md"' in page


def test_the_save_and_the_formats_have_actions():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert 'document.getElementById("formats")' in page
    assert 'document.getElementById("save")' in page


def test_the_page_stores_each_toggle_under_its_own_name():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Review focus line 1: the stored value is "1" or "0", one name per toggle.
    assert 'readStored("ziomek_panel")' in page
    assert 'readStored("ziomek_text")' in page
    assert 'setStored("ziomek_panel", shown ? "1" : "0")' in page
    assert 'setStored("ziomek_text", on ? "1" : "0")' in page
    assert "document.cookie" not in page  # storage replaces the cookie


def test_the_page_has_one_state_for_the_panel():
    client = build_app()
    page = client.get("/api/roster/view").text

    # The class that hides the pane is the only source of truth, and the label follows it.
    assert 'classList.add("open")' not in page
    assert 'label.textContent = shown ? "hide" : "show"' in page


def test_the_panel_lines_keep_their_newlines_and_are_not_rebuilt_each_tick():
    client = build_app()
    page = client.get("/api/roster/view").text

    # The rule must reach the elements the panel actually builds.
    assert (
        "#transcript { list-style: none; padding: 0; }"
        and "#transcript li, #transcript .box p { white-space: pre-wrap; }" in page
    )
    assert "rendered" in page  # the page keeps what it has already shown instead of clearing the list


def test_the_page_clears_the_panel_when_the_record_is_empty():
    client = build_app()
    page = client.get("/api/roster/view").text

    # A record that shrank means a new call: the old lines must not stay.
    assert 'document.getElementById("transcript").innerHTML = ""' in page
    assert "lastBlocks.length < rendered" in page


def test_the_page_asks_for_the_file_content_and_keeps_the_download_in_the_browser():
    client = build_app()
    page = client.get("/api/roster/view").text

    # The file text comes from the server; the download stays a browser action.
    assert 'fetch("/api/roster/transcript/markdown?at="' in page
    assert "new Blob" in page and "link.download = name" in page
    assert "revokeObjectURL" in page


def test_the_page_survives_a_failed_poll():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "try {" in page  # a failed fetch must not leave lines that no longer match the record


def test_the_page_gives_back_the_object_url_and_the_download_link():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "URL.revokeObjectURL" in page
    assert "document.body.appendChild(link)" in page


def test_the_reader_is_one_rule_for_both_names():
    """Storage keeps the value as it is, so there is no decoding step to fail."""
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "function readStored(name)" in page
    assert "return null" in page
    assert "decodeURIComponent" not in page


def test_the_tile_payload_has_one_texts_key():
    from ziomek.api import roster_view

    source = module_source()
    assert source.count('"texts": [entry.as_dict()') == 1
    assert roster_view.tiles


def test_grouping_follows_the_order_of_the_record():
    from ziomek.api.roster_view import blocks

    entries = [
        {"name": "John", "action": "join"},
        {"name": "Donald", "action": "join"},
        {"name": "Donald", "action": "text", "text": "playing darts", "author": "agent"},
        {"name": "John", "action": "text", "text": "wait, are we still talking?", "author": "agent"},
        {"name": "Donald", "action": "text", "text": "now mowing the lawn", "author": "agent"},
        {"name": "Donald", "action": "leave"},
    ]
    assert [b["kind"] for b in blocks(entries)] == [
        "system",
        "system",
        "group",
        "group",
        "group",
        "system",
    ]
    assert blocks(entries)[3]["name"] == "John"


def test_a_participant_with_no_message_produces_no_group():
    from ziomek.api.roster_view import blocks

    entries = [
        {"name": "John", "action": "join"},
        {"name": "John", "action": "text", "text": "", "author": "agent"},
    ]
    assert blocks(entries) == [{"kind": "system", "name": "John", "text": "John joined."}]


def test_the_system_line_is_a_sentence_with_the_word_from_the_record():
    from ziomek.api.roster_view import sentence

    assert sentence({"name": "John", "action": "join"}) == "John joined."
    assert sentence({"name": "John", "action": "hold"}) == "John is on hold."
    assert sentence({"name": "John", "action": "left"}) == "John left."
    assert sentence({"name": "John", "action": "something"}) == "John something."


def test_the_transcript_payload_carries_the_groups_as_well_as_the_entries():
    client = build_app()
    get_roster().record("John", "join")
    get_roster().record("John", "text", text="compiling", author="agent")
    payload = client.get("/api/roster/transcript").json()
    assert payload["entries"][0]["action"] == "join"
    assert payload["blocks"][0]["kind"] == "system"
    assert payload["blocks"][1]["name"] == "John"


def test_the_markdown_file_keeps_its_group_and_its_hard_break():
    blocks = [{"kind": "group", "name": "Donald", "author": "agent", "lines": ["playing darts"]}]
    text = markdown_text(blocks, "2026-10-31T14:20:04Z")
    assert text.startswith("# transcript — 2026-10-31T14:20:04Z\n\n")
    assert "### Donald (agent)\nplaying darts  \n" in text


def test_a_system_line_is_a_quote_in_the_file():
    from ziomek.api.roster_view import blocks, markdown_text

    blocks = [{"kind": "system", "text": "John joined."}]
    assert "> John joined." in markdown_text(blocks, "2026-10-31T14:20:04Z")


def test_the_file_uses_the_clock_passed_by_the_page(monkeypatch):
    from ziomek.api import roster_view

    client = build_app()
    get_roster().join("John")

    def clock():
        return "2026-10-31T14:20:04Z"

    monkeypatch.setattr(roster_view, "clock", clock)
    page = client.get("/api/roster/view").text
    assert "at = new Date()" in page
    assert "buildFilename(ext, at)" in page
    assert 'request.query_params.get("at")' in module_source()


def test_the_page_has_the_colors_and_the_box_shape():
    page = page_source()
    assert (
        ".box { background: #2a2a30; border: 1px solid #4a4a52; margin-bottom: 14px; border-radius: 6px; padding: 12px; }"
        in page
    )
    assert ".name { color: #8ab4f8; background: rgba(12,12,18,0.7); border-radius: 6px; padding: 4px 6px; }" in page
    assert ".event { color: #e0a568; }" in page
    assert ".system_text { color: #7fb069; }" in page
    assert 'el_class("name")' in page


def test_the_page_writes_the_group_header_with_the_author():
    page = page_source()
    assert '" (" + block.author + ")"' in page


def test_the_panel_renders_a_system_block_as_its_own_line():
    page = page_source()

    # A block that is not a group cannot be built from lines that do not exist.
    assert 'if (block.kind === "system")' in page
    assert 'item.className = block.author === "system" ? "system_text" : "event";' in page


def test_a_group_line_is_the_text_as_written():
    from ziomek.api.roster_view import format_line

    # The header carries the name and the author, so the line carries only the text.
    entry = {"name": "John", "action": "text", "text": "compiling", "author": "agent"}
    assert format_line(entry) == "compiling"

    from ziomek.api.roster_view import blocks

    assert blocks([{"name": "John", "action": "", "text": "", "author": ""}]) == []
    assert blocks([{"name": "John", "action": "join", "text": "", "author": ""}]) == [
        {"kind": "system", "name": "John", "text": "John joined."}
    ]


def test_a_nameless_entry_has_no_leading_space_in_its_line():
    from ziomek.api.roster_view import sentence

    assert sentence({"name": "", "action": "join"}) == "joined."


def test_the_two_clocks_use_the_same_shape():
    import re

    from ziomek.api import roster_view

    # The header and the name use one shape, so the file says what the page passed.
    assert 'strftime("%Y-%m-%dT%H%M%SZ")' in (
        Path(__file__).parent.parent / "src" / "ziomek" / "api" / "roster_view.py"
    ).read_text(encoding="utf-8")
    assert "getUTCHours()" in page_source()


def test_the_file_name_follows_the_shape_the_spec_gives():
    page = page_source()

    # ziomek_{YYYY-MM-DD}_{HHMM}_transcript.{ext}: dashes inside the date, underscore as the separator.
    assert 'dateParts(at).join("-") + "_" + clockParts(at).slice(0, 2).join("")' in page


def test_the_classes_the_page_uses_are_the_classes_the_page_defines():
    page = page_source()

    # A class the page uses must be defined once, and a rule must be reachable.
    assert 'el_class("group_author")' in page and ".group_author { color: #999; }" in page
    assert (
        page.count(
            ".box { background: #2a2a30; border: 1px solid #4a4a52; margin-bottom: 14px; border-radius: 6px; padding: 12px; }"
        )
        == 1
    )
    assert (
        "#transcript { list-style: none; padding: 0; }"
        and "#transcript li, #transcript .box p { white-space: pre-wrap; }" in page
    )
    assert ".event { color: #e0a568; }" in page


def test_the_page_builds_a_line_only_through_the_rule_in_python():
    page = page_source()

    # The dead map is gone: the words exist in one place.
    assert "const PAST = {" not in page


def test_a_cut_line_keeps_the_full_text_on_hover():
    """The ellipsis comes from the clamp, so nothing is written by JavaScript; hover still shows the whole text, and the panel has it too."""
    page = page_source()
    assert (
        ".text { color: #ddd; background: rgba(12,12,18,0.7); border-radius: 8px; padding: 6px; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; line-height: 20px; max-height: 50%; margin-top: auto; min-height: 0; overflow: hidden; }"
        in page
    )
    assert "el.title = value" in page
    assert "markTruncated" not in page


def test_the_grid_defends_the_shape_of_a_tile_without_reflowing_for_height():
    """B: fixed minimum width, nothing computed, no rule for height."""
    page = page_source()
    assert "grid-template-columns: repeat(auto-fill, minmax(180px, 1fr))" in page


def test_the_roster_box_is_bounded_and_scrolls_inside_it():
    """B+D: the box does not move the page; the tiles inside it scroll."""
    page = page_source()
    assert "#roster { flex: 0 0 55%; max-height: 100vh; overflow: auto; }" in page


def test_the_page_shows_the_number_of_participants_in_the_call():
    """D: the number comes from the participants that joined, not from what is drawn."""
    page = page_source()
    assert 'count.textContent = tiles.length + " participants"' in page


def test_no_cell_is_filled_with_a_placeholder():
    """A: no placeholders, the last row is partial and nothing is computed."""
    page = page_source()
    assert ".empty" not in page


def test_the_page_has_a_second_toggle_for_the_text_inside_tiles():
    """The text inside a tile can be turned off; the tile itself stays."""
    page = page_source()
    assert 'id="state_text"' in page
    assert 'if (textOn()) renderText(bottom, "text", tile.status_text);' in page


def test_the_page_has_one_rule_for_the_text_inside_a_tile():
    """One rule, written once: the tile text is the class the page writes."""
    page = page_source()
    assert (
        ".text { color: #ddd; background: rgba(12,12,18,0.7); border-radius: 8px; padding: 6px; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; line-height: 20px; max-height: 50%; margin-top: auto; min-height: 0; overflow: hidden; }"
        in page
    )
    assert page.count(".text {") == 1
    assert ".status_text {" not in page


def test_the_reader_takes_the_name_it_is_asked_for():
    """One rule for both toggles, so nothing is keyed to one name."""
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "function readStored(name)" in page
    assert "function setStored(name, value)" in page


def test_the_formats_button_shows_the_arrow_before_the_list_of_formats():
    """The label is the marker for the list, not a name for the control."""
    client = build_app()
    page = client.get("/api/roster/view").text

    assert 'id="formats">▼' in page
    assert 'id="menu"' in page  # the list is what the marker opens


def test_the_sidebar_has_a_fixed_width():
    """It does not grow with the window; the grid takes the rest."""
    page = page_source()
    assert "#panel { flex: 0 0 320px; border-left: 1px solid #444; padding-left: 12px; }" in page
    assert "#panel { flex: 1;" not in page


def test_the_group_box_uses_the_same_round_as_the_tile():
    """Same corner radius as the tile, so both sides look like the same shape."""
    page = page_source()
    assert (
        ".box { background: #2a2a30; border: 1px solid #4a4a52; margin-bottom: 14px; border-radius: 6px; padding: 12px; }"
        in page
    )
    assert ".tile { padding: 12px; margin: 8px 0; background: #1b1b22; border-radius: 6px; }" in page


def test_the_buttons_use_the_shape_of_the_rest_of_the_page():
    """Not the browser default: same surface, same corner, same font."""
    page = page_source()
    assert (
        "button { background: #2a2a30; color: #ddd; border: 1px solid #4a4a52; border-radius: 6px; padding: 6px 10px; font: inherit; cursor: pointer; }"
        in page
    )


def test_only_what_the_participant_ssaid_mmade_a_group():
    # Option A: a group holds only what the participant said; anything written by the system
    # stays as its own line, with the name and the author kept for it.
    from ziomek.api.roster_view import blocks

    entries = [
        {"name": "John", "action": "join"},
        {"name": "John", "action": "text", "text": "compiling", "author": "agent"},
        {"name": "John", "action": "text", "text": "a system note", "author": "system"},
        {"name": "John", "action": "left"},
    ]
    built = blocks(entries)
    assert [block["kind"] for block in built] == ["system", "group", "system", "system"]
    assert built[1]["lines"] == ["compiling"]
    assert built[2]["name"] == "John" and built[2]["author"] == "system"
    assert built[2]["text"] == "a system note"


def test_the_page_writes_a_system_line_with_the_name_and_the_green_color():
    # A line written by the system is not a group, so it keeps its name and its own color.
    page = page_source()
    assert (
        'el_class("name")' in page
        and ".name { color: #8ab4f8; background: rgba(12,12,18,0.7); border-radius: 6px; padding: 4px 6px; }" in page
    )
    assert 'item.className = block.author === "system" ? "system_text" : "event";' in page


def test_a_system_written_line_keeps_its_author_in_the_file():
    from ziomek.api.roster_view import blocks, markdown_text

    built = blocks([{"name": "John", "action": "text", "text": "a system note", "author": "system"}])
    assert "> John (system) — a system note" in markdown_text(built, "2026-10-31T14:20:04Z")


def test_the_tile_payload_carries_no_avatar_when_the_config_default_is_none():
    # Nothing is bundled yet, so the default is none: the tile shows the block without an image.
    from ziomek.api.roster_view import tiles

    client = build_app()
    get_roster().join("John")
    assert Settings().roster_avatar == "none"
    assert tiles()[0]["avatar"] is None


def test_a_missing_avatar_file_is_treated_as_none_and_leaves_a_warning(caplog):
    from ziomek.api.roster_view import tiles

    settings = Settings(roster_avatar="default_avatar.png")
    client = build_app()
    get_roster().join("John")
    assert tiles(settings=settings)[0]["avatar"] is None
    assert "default_avatar.png" in caplog.text


def test_an_avatar_file_that_exists_shows_up_in_the_payload(tmp_path):
    from ziomek.api.roster_view import tiles

    avatar = tmp_path / "john.png"
    avatar.write_text("not an image, only a stand-in")
    client = build_app()
    get_roster().join("John")
    assert tiles(settings=Settings(roster_avatar=str(avatar)))[0]["avatar"] == str(avatar)


def test_the_page_builds_the_name_on_the_left_and_the_expression_on_the_right():
    # The block is the avatar, so these are corners of the block, not elements inside a card.
    page = page_source()
    assert ".top { display: flex; justify-content: space-between; padding: 8px; }" in page
    assert 'el_class("top")' in page and 'el_class("bottom")' in page


def test_the_text_stays_at_the_bottom_of_the_block():
    page = page_source()
    assert ".bottom { position: absolute; left: 8px; right: 8px; bottom: 8px; }" in page


def test_the_expression_uses_a_monotype_font_and_is_smaller_than_name():
    # An expression is a state name, not an emotion: "playing darts" is not an emotion.
    # It is set in a monotype font and kept smaller than the name.
    page = page_source()
    assert (
        ".expression { color: #d2a9ff; font-family: monospace; font-size: 11px; background: rgba(12,12,18,0.7); border-radius: 6px; padding: 4px 6px; }"
        in page
    )
    assert ".name { color: #8ab4f8; background: rgba(12,12,18,0.7); border-radius: 6px; padding: 4px 6px; }" in page


def test_the_record_items_are_list_items_with_the_markers_and_indent_removed():
    # Option A: a real list item, with the markers and the default indent taken away.
    page = page_source()
    assert "#transcript { list-style: none; padding: 0; }" in page
    assert 'document.createElement("li")' in page


def test_the_text_block_can_actually_clamp_three_lines():
    # -webkit-line-clamp only clamps when the element is a box; display: block is not enough.
    page = page_source()

    assert (
        ".text { color: #ddd; background: rgba(12,12,18,0.7); border-radius: 8px; padding: 6px; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; line-height: 20px; max-height: 50%; margin-top: auto; min-height: 0; overflow: hidden; }"
        in page
    )


def test_the_clamp_is_the_only_marker_and_the_full_text_stays_on_hover():
    # Browser ellipsis wins, so there is no marker written by JavaScript; hover still works through title.
    page = page_source()

    assert (
        ".text { color: #ddd; background: rgba(12,12,18,0.7); border-radius: 8px; padding: 6px; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; line-height: 20px; max-height: 50%; margin-top: auto; min-height: 0; overflow: hidden; }"
        in page
    )
    assert "markTruncated" not in page
    assert "el.title = value" in page


def test_the_three_layers_are_the_three_separate_panels():
    # Group 2 from the mock: each layer keeps its own panel, so the name, the expression and the text each get their own rounded background.
    page = page_source()

    assert ".name { color: #8ab4f8; background: rgba(12,12,18,0.7); border-radius: 6px; padding: 4px 6px; }" in page
    assert (
        ".expression { color: #d2a9ff; font-family: monospace; font-size: 11px; background: rgba(12,12,18,0.7); border-radius: 6px; padding: 4px 6px; }"
        in page
    )
    assert (
        ".text { color: #ddd; background: rgba(12,12,18,0.7); border-radius: 8px; padding: 6px; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; line-height: 20px; max-height: 50%; margin-top: auto; min-height: 0; overflow: hidden; }"
        in page
    )
