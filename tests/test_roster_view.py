"""The roster page shows a tile for each participant in the call."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.roster_page_helpers import page_shell, page_source, part_of_page, served_page


def module_source():
    """The module as stored, for rules the page cannot reach without a browser."""
    return (Path(__file__).parent.parent / "src" / "ziomek" / "api" / "roster_view.py").read_text(encoding="utf-8")


import ziomek.roster as module
from ziomek import server
from ziomek.api.roster_view import blocks, markdown_text, router, sentence, transcript
from ziomek.config import Settings
from ziomek.roster import build_roster, get_roster


@pytest.fixture(autouse=True)
def fresh_roster():
    module._roster = None
    from ziomek.api import avatar_ws

    avatar_ws._shown = None
    build_roster(Settings())
    from ziomek.avatar.skins import build_registry

    # A registry is built where the app is created, so a test that reads the payload builds one.
    build_registry(Settings())


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
    page = part_of_page("roster.html", "roster.mjs")

    # Tiles are built per participant, and the text areas are filled from the tile data.
    assert 'className = "tile"' in page
    assert "status_text" in page


def test_the_roster_page_is_served_by_the_server():
    app = server.create_app(Settings(audio_backend="noop", no_stt=True, no_gamepad=True))
    client = TestClient(app)

    assert client.get("/api/roster").status_code == 200
    assert 'className = "tile"' in served_page(client)
    # A browser asks for an icon on its own when it renders a page, so a page names the path the
    # app answers for instead of the one nothing serves.
    assert '<link rel="icon" href="/favicon.svg"' in served_page(client)


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
    page = part_of_page("roster.html", "roster.mjs")

    assert 'renderText(top, "expression", tile.expression)' in page


def test_the_labels_at_the_top_of_a_tile_are_painted_above_its_avatar():
    page = part_of_page("roster.html", "roster.css")

    # An absolutely positioned box paints above content in normal flow, so the labels carry their own level.
    assert ".top { position: absolute;" in page and "z-index: 1;" in page


def test_the_panel_shows_the_text_attached_to_a_line_of_the_record():
    page = part_of_page("roster.html", "roster.mjs")

    # The tile shows what the participant is, not the lines; the panel is the record, so the text and its
    # author belong to a line there.
    assert "block.text" in page
    assert "block.author" in page


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

    assert 'start("open")' in served_page(client)


def test_a_value_that_is_not_open_or_closed_falls_back_to_closed():
    app = server.create_app(
        Settings(roster_transcript_default="maybe", audio_backend="noop", no_stt=True, no_gamepad=True)
    )
    client = TestClient(app)

    assert 'start("closed")' in served_page(client)


def test_the_page_reads_the_panel_state_from_storage_before_the_config_default():
    page = part_of_page("roster.html", "roster.mjs")

    assert "localStorage" in page
    assert 'readStored("ziomek_panel")' in page


def test_the_page_uses_the_config_default_only_when_nothing_is_stored():
    client = build_app()
    page = served_page(client)

    assert "function readStored(name)" in page
    assert "return null" in page  # nothing stored -> the config default decides the opening


def test_the_page_has_the_panel_and_its_toggle():
    client = build_app()
    page = served_page(client)

    assert 'id="panel"' in page
    assert 'id="toggle"' in page
    assert "#roster { max-height: 100vh; overflow: auto; }" in page
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
    assert sentence({"action": "wave"}) == "wave."


def test_the_panel_and_the_saved_file_write_the_same_lines():
    # One rule builds the lines: the panel shows them, the file writes the same ones.
    from ziomek.api.roster_view import blocks, format_line, markdown_text

    assert "for (const line of block.lines)" in part_of_page("roster.html", "roster.mjs")
    entry = {"name": "John", "action": "text", "text": "compiling", "author": "agent"}
    group = {"kind": "group", "name": entry["name"], "author": entry["author"], "lines": [format_line(entry)]}
    blocks_result = blocks([entry])
    assert blocks_result[0]["lines"] == group["lines"]
    file = markdown_text([group], "2026-10-31T14:20:04Z")
    # Task 5 Step 1: the same content must keep the markers a markdown viewer needs.
    assert "compiling  " in file  # two spaces, the hard break a viewer reads
    assert "### John (agent)" in file  # the heading keeps name and author
    quote = markdown_text([{"kind": "system", "name": "John", "text": "left."}], "2026-10-31T14:20:04Z")
    assert "> John — left." in quote
    # The markers, so a viewer can read the same lines the panel shows.
    assert "### John (agent)" in file
    assert "compiling  " in file  # two spaces: a markdown hard break
    quoted = markdown_text([{"kind": "system", "name": "John", "text": "joined."}], "2026-10-31T14:20:04Z")
    assert "> John — joined." in quoted


def test_a_group_without_a_name_keeps_the_author_and_the_text():
    # Review focus line 4: nothing is added for a name that is not there.
    from ziomek.api.roster_view import blocks

    entries = [{"action": "text", "text": "compiling", "author": "agent"}]
    block = blocks(entries)[0]
    assert block["name"] == ""
    assert block["lines"] == ["compiling"]


def test_the_page_writes_lines_with_text_content():
    page = part_of_page("roster.html", "roster.mjs")

    # Review focus line 2: a line that HTML would interpret must appear literally.
    assert "p.textContent = line" in page


def test_the_page_has_save_with_the_two_formats():
    client = build_app()
    page = served_page(client)

    assert 'id="save"' in page
    assert 'data-format="markdown"' in page
    assert 'data-format="json"' in page


def test_the_saved_file_is_named_with_the_project_and_the_download_time():
    page = part_of_page("roster.html", "roster.mjs")

    # ziomek_{YYYY-MM-DD}_{HHMM}_transcript.{md|json}, built from the browser clock
    assert 'return "ziomek_" + nameStamp(at) + "_transcript." + ext' in page
    assert "new Date(" in page


def test_the_file_keeps_its_header_when_there_is_nothing_to_save():
    client = build_app()

    # Review focus line 5: an empty record still gets a file, and the download happens in the browser.
    assert client.get("/api/roster/transcript/markdown?at=2026-10-31T14:20:04Z").text.startswith(
        "# transcript — 2026-10-31T14:20:04Z"
    )
    page = part_of_page("roster.html", "roster.mjs")
    assert "new Blob(" in page


def test_an_entry_with_nothing_to_show_produces_no_line():
    # Review focus line 1: an entry with no name, action or text produces nothing.
    # The guard belongs in the rule that builds lines, so the panel and the file behave the same.
    from ziomek.api.roster_view import blocks, format_line

    assert format_line({"name": "", "action": "", "text": "", "author": ""}) == ""
    assert blocks([{"name": "", "action": "", "text": "", "author": ""}]) == []
    assert format_line({"name": "John", "action": "", "text": "", "author": ""}) == ""


def test_the_toggle_stays_reachable_when_the_panel_is_hidden():
    page = part_of_page("roster.html", "roster.css")

    # Review focus: a control inside the hidden pane cannot be used to open it again.
    assert "#layout.hide #transcript { display: none; }" in page
    assert "#menu { display: none" in page
    # A hidden panel must not keep its column, otherwise the roster does not take the width.
    assert "#layout.hide #panel { flex: 0 0 auto; }" in page


def test_the_words_of_the_actions_are_the_sentences_the_spec_asks_for():
    from ziomek.api.roster_view import sentence

    # The name belongs to the block that holds it, so a line carries only what happened.
    assert sentence({"action": "join"}) == "joined."
    assert sentence({"action": "hold"}) == "is on hold."
    assert sentence({"action": "leave"}) == "left."


def test_an_action_line_does_not_repeat_the_name_of_the_block_that_holds_it():
    from ziomek.api.roster_view import format_line

    # On the page the block name is its own element, so a line that names it again is read twice.
    assert format_line({"name": "John", "action": "join"}) == "joined."


def test_an_entry_that_carries_the_voice_and_face_produces_their_text():
    from ziomek.api.roster_view import assignment_text

    assert assignment_text({"voice": "cosette", "skin": "single-frame"}) == "(cosette, single-frame)"
    assert assignment_text({"action": "join", "voice": "cosette"}) == "(cosette)"
    assert assignment_text({"action": "join"}) == ""


def test_a_block_keeps_the_assignment_apart_from_the_action():
    from ziomek.api.roster_view import blocks

    block = blocks([{"name": "John", "action": "join", "voice": "cosette", "skin": "single-frame"}])[0]
    # The action stays the line, so the part naming what was drawn can be shown in its own color.
    assert block["text"] == "joined."
    assert block["assignment"] == "(cosette, single-frame)"


def test_a_block_for_an_entry_that_drew_nothing_keeps_no_assignment():
    from ziomek.api.roster_view import blocks

    assert "assignment" not in blocks([{"name": "John", "action": "join"}])[0]


def test_the_saved_file_writes_the_assignment_as_text_like_the_author_does():
    from ziomek.api.roster_view import markdown_text

    block = {"kind": "system", "name": "John", "text": "joined.", "assignment": "(cosette, single-frame)"}
    assert "> John — joined. (cosette, single-frame)" in markdown_text([block], "2026-10-31T14:20:04Z")
    without = {"kind": "system", "name": "John", "text": "joined."}
    assert "> John — joined." in markdown_text([without], "2026-10-31T14:20:04Z")


def test_the_page_shows_the_assignment_in_its_own_colour():
    client = build_app()
    page = served_page(client)

    # A colour can only be put on something kept apart from the rest of the line.
    assert ".assignment { color: #c586c0; }" in page
    assert 'const drawn = el_class("assignment");' in page
    assert 'drawn.textContent = " " + block.assignment;' in page


def test_the_page_names_the_file_with_the_short_extension():
    page = part_of_page("roster.html", "roster.mjs")

    assert 'markdown: "md"' in page


def test_the_save_and_the_formats_have_actions():
    page = part_of_page("roster.html", "roster.mjs")

    assert 'document.getElementById("formats")' in page
    assert 'document.getElementById("save")' in page


def test_the_page_stores_each_toggle_under_its_own_name():
    page = part_of_page("roster.html", "roster.mjs")

    # Review focus line 1: the stored value is "1" or "0", one name per toggle.
    assert 'readStored("ziomek_panel")' in page
    assert 'readStored("ziomek_text")' in page
    assert 'setStored("ziomek_panel", shown ? "1" : "0")' in page
    assert 'setStored("ziomek_text", on ? "1" : "0")' in page
    assert "document.cookie" not in page  # storage replaces the cookie


def test_the_page_has_one_state_for_the_panel():
    page = part_of_page("roster.html", "roster.mjs")

    # The class that hides the pane is the only source of truth, and the label follows it.
    assert 'classList.add("open")' not in page
    assert 'label.textContent = shown ? "hide" : "show"' in page


def test_the_panel_lines_keep_their_newlines():
    """The rule must reach the elements the panel actually builds."""
    stylesheet = part_of_page("roster.html", "roster.css")

    assert "#transcript { list-style: none; padding: 0; }" in stylesheet
    assert "#transcript li, #transcript .box p { white-space: pre-wrap; }" in stylesheet


def test_the_panel_is_not_rebuilt_on_every_poll():
    """The page keeps what it has already shown instead of clearing the list each tick."""
    script = part_of_page("roster.html", "roster.mjs")

    assert "let rendered = 0;" in script
    assert "for (const block of lastBlocks.slice(rendered))" in script


def test_a_long_run_of_characters_breaks_inside_the_panel_box_instead_of_running_past_it():
    page = part_of_page("roster.html", "roster.css")

    # Wrapping at spaces is not enough: a run with no space in it keeps going past the box.
    assert "#transcript li, #transcript .box p { overflow-wrap: break-word; }" in page


def test_a_tile_does_not_list_events_because_the_panel_already_shows_them():
    page = part_of_page("roster.html", "roster.mjs")

    # The tile keeps what the participant is; join, hold and text lines belong to the record in the panel,
    # so the same list is not built twice for the same call.
    assert 'className = "events"' not in page


def test_a_long_run_of_characters_breaks_inside_the_tile_text_so_the_page_does_not_scroll_sideways():
    page = part_of_page("roster.html", "roster.css")

    # The same run reaches the text a tile shows, so the rule covers it.
    assert ".text {" in page and "overflow-wrap: break-word;" in page


def test_the_page_clears_the_panel_when_the_record_is_empty():
    page = part_of_page("roster.html", "roster.mjs")

    # A record that shrank means a new call: the old lines must not stay.
    assert 'document.getElementById("transcript").innerHTML = ""' in page
    assert "lastBlocks.length < rendered" in page


def test_the_panel_follows_a_new_line_only_when_the_viewer_is_at_the_end():
    page = part_of_page("roster.html", "roster.mjs")

    # Being at the end is measured against the box, and a position this close counts as being there.
    assert "const END_TOLERANCE = 4;" in page
    assert "function was_at_the_end(" in page
    assert "panel.scrollTop + panel.clientHeight >= panel.scrollHeight - END_TOLERANCE" in page


def test_a_viewer_reading_above_the_end_is_not_pulled_down_by_a_new_line():
    page = part_of_page("roster.html", "roster.mjs")

    # The position is read before the line is added, and the move only follows from that reading.
    added_before = page.index('document.getElementById("transcript").append(row)')
    assert page.index("const follow = was_at_the_end()") < added_before
    assert "if (follow) panel.scrollTop = panel.scrollHeight;" in page
    assert page.count("panel.scrollTop =") == 1


def test_a_line_that_joins_the_block_already_shown_is_still_shown():
    page = part_of_page("roster.html", "roster.mjs")

    # A run of text from one participant grows inside the block that is already on screen, so counting
    # blocks is not enough: the page has to know what it drew inside that block.
    assert "let shown_block = null;" in page and "let shown_lines = 0;" in page
    assert "shown_block = box;" in page and "shown_lines = block.lines.length;" in page
    assert "last.lines.length > shown_lines" in page


def test_a_line_that_joins_a_block_is_added_to_that_block_and_not_as_a_new_item():
    page = part_of_page("roster.html", "roster.mjs")

    # The line belongs to the box the run is shown in, so it is added there instead of starting
    # another item of the record.
    guard = page.index('if (shown_block && last && last.kind === "group" && last.lines.length > shown_lines)')
    after = page[guard:]
    assert "shown_block.append(p);" in after
    assert 'document.getElementById("transcript").append(row)' not in after


def test_a_new_call_forgets_the_block_the_panel_had_been_adding_lines_to():
    page = part_of_page("roster.html", "roster.mjs")

    # A record that shrank starts from nothing, so the box kept for the call that ended cannot be
    # written into by the new one.
    cleared = page.index('document.getElementById("transcript").innerHTML = "";')
    branch = page[cleared : page.index("for (const block of lastBlocks.slice(rendered))")]
    assert "shown_block = null;" in branch and "shown_lines = 0;" in branch


def test_the_page_asks_for_the_file_content_and_keeps_the_download_in_the_browser():
    page = part_of_page("roster.html", "roster.mjs")

    # The file text comes from the server; the download stays a browser action.
    assert 'fetch("/api/roster/transcript/markdown?at="' in page
    assert "new Blob" in page and "link.download = name" in page
    assert "revokeObjectURL" in page


def test_the_page_survives_a_failed_poll():
    page = part_of_page("roster.html", "roster.mjs")

    assert "try {" in page  # a failed fetch must not leave lines that no longer match the record


def test_the_page_gives_back_the_object_url_and_the_download_link():
    page = part_of_page("roster.html", "roster.mjs")

    assert "URL.revokeObjectURL" in page
    assert "document.body.appendChild(link)" in page


def test_the_reader_is_one_rule_for_both_names():
    """Storage keeps the value as it is, so there is no decoding step to fail."""
    client = build_app()
    page = served_page(client)

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
    assert blocks(entries) == [{"kind": "system", "name": "John", "text": "joined."}]


def test_the_system_line_is_a_sentence_with_the_word_from_the_record():
    from ziomek.api.roster_view import sentence

    # A word the list does not know is written as it was recorded.
    assert sentence({"action": "something"}) == "something."


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

    get_roster().join("John")

    def clock():
        return "2026-10-31T14:20:04Z"

    monkeypatch.setattr(roster_view, "clock", clock)
    page = part_of_page("roster.html", "roster.mjs")
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
    page = part_of_page("roster.html", "roster.mjs")
    assert '" (" + block.author + ")"' in page


def test_the_panel_renders_a_system_block_as_its_own_line():
    page = part_of_page("roster.html", "roster.mjs")

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
        {"kind": "system", "name": "John", "text": "joined."}
    ]


def test_a_nameless_entry_has_no_leading_space_in_its_line():
    from ziomek.api.roster_view import sentence

    assert sentence({"name": "", "action": "join"}) == "joined."


def test_the_two_clocks_use_the_same_shape():
    from ziomek.api import roster_view

    # The header and the name use one shape, so the file says what the page passed.
    assert 'strftime("%Y-%m-%dT%H%M%SZ")' in (
        Path(__file__).parent.parent / "src" / "ziomek" / "api" / "roster_view.py"
    ).read_text(encoding="utf-8")
    assert "getUTCHours()" in part_of_page("roster.html", "roster.mjs")


def test_the_file_name_follows_the_shape_the_spec_gives():
    page = part_of_page("roster.html", "roster.mjs")

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
    page = part_of_page("roster.html", "roster.mjs")

    # The dead map is gone: the words exist in one place.
    assert "const PAST = {" not in page


def test_a_cut_line_keeps_the_full_text_on_hover():
    """The ellipsis comes from the clamp, so nothing is written by JavaScript; hover still shows the whole text, and the panel has it too."""
    page = page_source()
    assert (
        ".text { color: #ddd; background: rgba(12,12,18,0.7); border-radius: 8px; padding: 6px; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; line-height: 20px; max-height: 50%; margin-top: auto; min-height: 0; overflow: hidden; overflow-wrap: break-word; }"
        in page
    )
    assert "el.title = value" in page
    assert "markTruncated" not in page


def test_a_cell_that_cannot_be_measured_keeps_the_size_the_stylesheet_gives_it():
    """The stacked layout under a narrow window has no room to measure, so the stylesheet default still applies."""
    page = page_source()
    assert "grid-template-columns: repeat(auto-fill, minmax(180px, 1fr))" in page
    assert 'state_sizes.report?.("cannot be measured", room, null, null, null, []);' in page
    # nothing taken from the area measured means nothing was read, so a tile is left with the size the stylesheet gives it
    assert "if (!room.taken) {" in page


def test_the_grid_is_written_as_whole_frames_on_both_edges():
    """A block is a whole number of frames on each axis, so the grid is written in frames, not in shares of the room, and a picture can be placed in such a cell."""
    page = part_of_page("roster.html", "roster.mjs")
    assert 'root.style.gridTemplateColumns = "repeat(" + grid.cols + ", " + frame + "px)"' in page
    assert 'root.style.gridTemplateRows = "repeat(" + grid.rows + ", " + frame + "px)"' in page


def test_a_tile_that_is_capped_stays_in_the_middle_of_its_cell():
    """A capped tile is smaller than the cell it was measured for, so it sits in the middle of the cell instead of at its corner."""
    page = part_of_page("roster.html", "roster.css")
    assert ".tile { justify-self: center; align-self: center; }" in page


def test_a_tile_is_sized_by_the_block_it_fills():
    """The size of a block is known when the grid is counted in whole frames, so a tile takes that size instead of an upper limit that a box falls back from."""
    page = part_of_page("roster.html", "roster.mjs")
    assert 'el.style.width = place.tile.width + "px";' in page
    assert 'el.style.height = place.tile.height + "px";' in page
    # the picture is placed inside the size the block was given, so nothing caps it
    assert "--largest-tile" not in page


def test_a_skin_that_was_not_read_cannot_set_a_size_for_the_tile():
    page = part_of_page("roster.html", "roster.mjs")
    assert "if (!skin || !skin.frameWidth || !skin.frameHeight) continue;" in page
    guard = page.split("function apply_largest_tile(")[1].split("if (!frame) {")[1].split("}")[0]
    assert "return;" in guard


def test_the_division_is_made_before_the_tiles_are_written():
    """A tile is placed in the block it was given, so the grid has to be named before the tiles are written."""
    page = part_of_page("roster.html", "roster.mjs")
    body = page.split("function render(tiles)")[1]
    assert body.index("apply_largest_tile(root, room, tiles)") < body.index("for (const tile of tiles)")


def test_the_tiles_use_the_height_available_to_the_grid_as_well_as_its_width():
    """Rows can only fill the page when the grid is given the height it is asked for."""
    page = part_of_page("roster.html", "roster.css")
    assert "#main > #roster { flex: 1 1 auto; min-height: 0; }" in page


def test_a_tile_fills_the_cell_it_was_divided_into_instead_of_keeping_a_square_shape():
    page = part_of_page("roster.html", "roster.css")
    assert ".tile { position: relative; overflow: hidden; }" in page
    assert "aspect-ratio" not in page


def test_the_roster_box_is_bounded_and_scrolls_inside_it():
    """B+D: the box does not move the page; the tiles inside it scroll."""
    page = part_of_page("roster.html", "roster.css")
    assert "#roster { max-height: 100vh; overflow: auto; }" in page


def test_the_page_shows_the_number_of_participants_in_the_call():
    """D: the number comes from the participants that joined, not from what is drawn."""
    page = part_of_page("roster.html", "roster.mjs")
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
    page = part_of_page("roster.html", "roster.css")
    assert (
        ".text { color: #ddd; background: rgba(12,12,18,0.7); border-radius: 8px; padding: 6px; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; line-height: 20px; max-height: 50%; margin-top: auto; min-height: 0; overflow: hidden; overflow-wrap: break-word; }"
        in page
    )
    assert page.count(".text {") == 1
    assert ".status_text {" not in page


def test_the_reader_takes_the_name_it_is_asked_for():
    """One rule for both toggles, so nothing is keyed to one name."""
    page = part_of_page("roster.html", "roster.mjs")

    assert "function readStored(name)" in page
    assert "function setStored(name, value)" in page


def test_the_formats_button_shows_the_arrow_before_the_list_of_formats():
    """The label is the marker for the list, not a name for the control."""
    client = build_app()
    page = served_page(client)

    assert 'id="formats">▼' in page
    assert 'id="menu"' in page  # the list is what the marker opens


def test_the_sidebar_has_a_fixed_width():
    """It does not grow with the window; the grid takes the rest."""
    page = part_of_page("roster.html", "roster.css")
    assert (
        "#panel { flex: 0 0 320px; max-height: 100vh; overflow: auto; border-left: 1px solid #444; padding-left: 12px; }"
        in page
    )
    assert "#panel { flex: 1;" not in page


def test_the_group_box_uses_the_same_round_as_the_tile():
    """Same corner radius as the tile, so both sides look like the same shape."""
    page = part_of_page("roster.html", "roster.css")
    assert (
        ".box { background: #2a2a30; border: 1px solid #4a4a52; margin-bottom: 14px; border-radius: 6px; padding: 12px; }"
        in page
    )
    assert ".tile { padding: 12px; margin: 8px 0; background: #1b1b22; border-radius: 6px; }" in page


def test_the_buttons_use_the_shape_of_the_rest_of_the_page():
    """Not the browser default: same surface, same corner, same font."""
    page = part_of_page("roster.html", "roster.css")
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


def test_the_tile_payload_carries_the_default_skin_and_the_frame_for_its_expression():
    # The default is the only skin that exists, so a join with no entry of its own is drawn with it.
    from ziomek.api.roster_view import tiles

    get_roster().join("John")
    assert Settings().roster_avatar == "single-frame"
    avatar = tiles()[0]["avatar"]
    assert avatar["skin"] == "single-frame"
    # An expression the definition does not cover is read through what it falls back to, which is row 1.
    frame = avatar["frame"]
    assert (frame["kind"], frame["row"], frame["column"]) == ("cell", 1, 0)
    assert (frame["width"], frame["height"]) == (100, 100)  # the size the default skin declares
    assert frame["fit"] == "contain"  # nothing states a setting, so the default is used


def test_a_skin_that_is_not_registered_draws_no_avatar_and_leaves_a_warning(caplog):
    # A name is read through the registry, never as a path, so an unknown name can only show nothing.
    from ziomek.api.roster_view import tiles

    settings = Settings(roster_pool=[("John", "", "not-a-skin")])
    build_roster(settings)
    get_roster().join("John")
    assert tiles(settings=settings)[0]["avatar"] is None
    assert "not-a-skin" in caplog.text


def test_the_skin_named_by_a_pool_entry_is_used_for_that_participant():
    from ziomek.api.roster_view import tiles

    settings = Settings(roster_pool=[("cosette", "", "single-frame")])
    build_roster(settings)
    get_roster().join("cosette")
    assert tiles(settings=settings)[0]["avatar"]["skin"] == "single-frame"


def test_the_page_builds_the_name_on_the_left_and_the_expression_on_the_right():
    # The block is the avatar, so these are corners of the block, not elements inside a card.
    page = page_source()
    assert "display: flex; justify-content: space-between;" in page
    assert 'el_class("top")' in page and 'el_class("bottom")' in page


def test_nothing_is_written_for_a_participant_who_is_not_on_hold():
    # The row that carries the marker is built inside the check for that state, so a page for
    # participants who are not on hold carries no element for them, not an empty one.
    page = part_of_page("roster.html", "roster.mjs")
    assert 'if (tile.state === "held") {\n      const middle = el_class("middle");' in page
    assert "renderText(middle," in page
    assert 'renderText(el, "on_hold"' not in page


def test_the_time_a_participant_has_been_on_hold_is_stated_on_its_own_line():
    """The state and how long it has lasted are two things a reader takes in separately, so they are not written as one sentence."""
    page = part_of_page("roster.html", "roster.mjs")
    assert 'renderText(middle, "on_hold", "on hold\\n" + held(tile));' in page


def test_the_held_marker_is_shown_in_the_quiet_color():
    """A held participant has no expression of their own, so what says they are held is not read as one."""
    page = part_of_page("roster.html", "roster.css")
    assert (
        ".middle .on_hold { background: rgba(12,12,18,0.7); border-radius: 6px; padding: 3px 6px; color: #999; }"
        in page
    )
    assert ".system_text { color: #7fb069; }" in page


def test_the_text_stays_at_the_bottom_of_the_block():
    page = part_of_page("roster.html", "roster.css")
    assert ".bottom { position: absolute; left: 8px; right: 8px; bottom: 8px; }" in page


def test_the_corner_labels_are_placed_from_the_block_as_the_text_is():
    # Both corners sit at the same inset, so the labels line up with the text.
    page = part_of_page("roster.html", "roster.css")
    assert ".top { position: absolute; top: 8px; left: 8px; right: 8px;" in page


def test_the_expression_uses_a_monotype_font_and_is_smaller_than_name():
    # An expression is a state name, not an emotion: "playing darts" is not an emotion.
    # It is set in a monotype font and kept smaller than the name.
    page = part_of_page("roster.html", "roster.css")
    assert (
        ".expression { color: #d2a9ff; font-family: monospace; font-size: 11px; background: rgba(12,12,18,0.7); border-radius: 6px; padding: 4px 6px; }"
        in page
    )
    assert ".name { color: #8ab4f8; background: rgba(12,12,18,0.7); border-radius: 6px; padding: 4px 6px; }" in page


def test_the_page_places_a_frame_inside_the_box_of_the_tile_it_draws():
    """A frame is drawn at its own size inside the box it was given, so the picture is placed from the middle of that box."""
    page = part_of_page("roster.html", "roster.mjs")
    assert "(boxWidth - frame.width * scaleWidth) / 2" in page
    assert "(boxHeight - frame.height * scaleHeight) / 2" in page


def test_the_page_uses_the_image_address_the_server_answered_with():
    # The API answers with a data address, so the page must not build one again.
    page = part_of_page("roster.html", "roster.mjs")
    assert 'block.style.backgroundImage = "url(" + image + ")"' in page
    assert '"url(data:image/png;base64,"' not in page


def test_the_page_gets_one_mapping_per_skin_and_reads_a_file_as_its_own_picture():
    # One place answers for a skin, so the page asks once per name and keeps what it got.
    page = part_of_page("roster.html", "roster.mjs")
    assert 'fetch("/api/avatar/sprite?skin="' in page
    assert "fetch(url)\n    .then((response) => (response.ok ? response.json() : null))" in page
    assert "if (!name || skins[name]) continue" in page
    assert "await load_skins(tiles)" in page
    # A frame that names a file cannot be cut from a sheet, so it is read one at a time and cached by its name.
    assert '"/api/avatar/image?skin="' in page
    assert 'const key = frame.kind === "cell" ? skin_name : skin_name + "/" + frame.file;' in page


def test_a_tile_that_has_no_avatar_is_left_as_it_is():
    # A skin that is not registered has no payload entry, so there is nothing to draw and no request for it.
    page = part_of_page("roster.html", "roster.mjs")
    assert "if (!skin) return" in page
    assert "if (!name || skins[name]) continue" in page


def test_the_record_items_are_list_items_with_the_markers_and_indent_removed():
    # Option A: a real list item, with the markers and the default indent taken away.
    page = page_source()
    assert "#transcript { list-style: none; padding: 0; }" in page
    assert 'document.createElement("li")' in page


def test_the_text_block_can_actually_clamp_three_lines():
    # -webkit-line-clamp only clamps when the element is a box; display: block is not enough.
    page = part_of_page("roster.html", "roster.css")

    assert (
        ".text { color: #ddd; background: rgba(12,12,18,0.7); border-radius: 8px; padding: 6px; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; line-height: 20px; max-height: 50%; margin-top: auto; min-height: 0; overflow: hidden; overflow-wrap: break-word; }"
        in page
    )


def test_the_clamp_is_the_only_marker_and_the_full_text_stays_on_hover():
    # Browser ellipsis wins, so there is no marker written by JavaScript; hover still works through title.
    page = page_source()

    assert (
        ".text { color: #ddd; background: rgba(12,12,18,0.7); border-radius: 8px; padding: 6px; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; line-height: 20px; max-height: 50%; margin-top: auto; min-height: 0; overflow: hidden; overflow-wrap: break-word; }"
        in page
    )
    assert "markTruncated" not in page
    assert "el.title = value" in page


def test_the_three_layers_are_the_three_separate_panels():
    # Group 2 from the mock: each layer keeps its own panel, so the name, the expression and the text each get their own rounded background.
    page = part_of_page("roster.html", "roster.css")

    assert ".name { color: #8ab4f8; background: rgba(12,12,18,0.7); border-radius: 6px; padding: 4px 6px; }" in page
    assert (
        ".expression { color: #d2a9ff; font-family: monospace; font-size: 11px; background: rgba(12,12,18,0.7); border-radius: 6px; padding: 4px 6px; }"
        in page
    )


def test_text_in_the_name_and_expression_lines_up_in_the_middle_of_their_boxes():
    """A box exactly as wide as its text has nothing to center against, so centering is written once on the row that holds the boxes rather than on each box."""
    page = part_of_page("roster.html", "roster.css")
    assert (
        ".top { position: absolute; top: 8px; left: 8px; right: 8px; z-index: 1; display: flex; justify-content: space-between; align-items: center; text-align: center; }"
        in page
    )
    assert "text-align" not in page.split(".name {")[1].split("}")[0]
    assert "text-align" not in page.split(".expression {")[1].split("}")[0]
    assert (
        ".text { color: #ddd; background: rgba(12,12,18,0.7); border-radius: 8px; padding: 6px; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; line-height: 20px; max-height: 50%; margin-top: auto; min-height: 0; overflow: hidden; overflow-wrap: break-word; }"
        in page
    )


def test_the_roster_page_answers_at_the_root_path():
    # A page is not an API endpoint, so the HTML is answered at /roster, not under /api.
    client = build_app()
    response = client.get("/roster")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div id="roster">' in response.text


def test_the_page_urls_use_the_root_paths():
    from ziomek.browser import avatar_page_url, view_page_url
    from ziomek.config import Settings

    settings = Settings()
    assert view_page_url(settings) == "http://localhost:5004/roster"
    assert avatar_page_url(settings) == "http://localhost:5004/avatar"


def test_the_roster_takes_the_rest_of_the_window_and_the_sidebar_stays_on_the_right():
    """The window is split by a fixed column on the right, so the roster grows into what is left."""
    page = part_of_page("roster.html", "roster.css")
    assert "#layout { display: flex; gap: 12px; min-height: 100vh; }" in page
    assert "#main { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; }" in page
    assert "#roster { max-height: 100vh; overflow: auto; }" in page
    assert "#roster { flex: 0 0 55%" not in page


def test_the_stacked_fallback_below_narrow_width_is_left_as_it_was():
    """On a narrow window the sidebar is not bound to the edge, it stacks above the roster."""
    page = part_of_page("roster.html", "roster.css")
    assert "@media (max-width: 900px)" in page
    assert "#layout { display: block; }" in page
    assert "#roster, #panel { flex: none; }" in page


def test_the_values_a_page_states_name_the_blocks_it_counted_not_the_shares_it_divided():
    """A page that cannot state values on its own still names what it measured, so the part added in dev mode can carry it."""
    drawing = part_of_page("roster.html", "roster.mjs")
    assert 'state_sizes.report?.("measured", room, grid, frame, 1, stated_blocks);' in drawing
    assert 'state_sizes.report?.("cannot be measured", room, null, null, null, []);' in drawing
    assert 'state_sizes.report?.("no frame size was read for these skins", room, null, null, null, []);' in drawing
    guard = drawing.split("if (!frame) {")[1].split("}")[0]
    assert "return;" in guard
    body = drawing[drawing.index("function apply_largest_tile") : drawing.index("function render(tiles)")]
    assert body.index("stated_blocks = blocks_in_frames(grid, parts.length, frame);") < body.index(
        'state_sizes.report?.("measured"'
    )


def test_a_page_can_only_be_given_what_a_part_provides():
    """A name a part does not provide makes the whole request fail, so a page asks for a part for what that part provides."""
    for page in ("roster.html", "roster_debug.html"):
        asked = [line for line in page_shell(page).splitlines() if "import {" in line]
        for line in asked:
            names = [name.strip() for name in line.split("{")[1].split("}")[0].split(",")]
            part = line.split("/static/")[1].split('"')[0]
            source = part_of_page(page, part)
            for name in names:
                assert (
                    f"export function {name}(" in source
                    or f"export async function {name}(" in source
                    or f"export const {name} " in source
                ), f"{page} asks for {name}, which {part} does not provide"
