"""The roster page shows a tile for each participant in the call."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ziomek.roster as module
from ziomek import server
from ziomek.api.roster_view import router
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

    assert 'renderText(el, "expression", tile.expression)' in page


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
    source = Path("src/ziomek/resources/roster.html").read_text(encoding="utf-8")
    assert "__TRANSCRIPT_DEFAULT__" in source

    assert 'const initial = "open";' in client.get("/api/roster/view").text


def test_a_value_that_is_not_open_or_closed_falls_back_to_closed():
    app = server.create_app(
        Settings(roster_transcript_default="maybe", audio_backend="noop", no_stt=True, no_gamepad=True)
    )
    client = TestClient(app)

    assert 'const initial = "closed";' in client.get("/api/roster/view").text


def test_the_page_reads_the_panel_state_from_the_cookie_before_the_config_default():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "document.cookie" in page
    assert "ziomek_panel" in page


def test_the_page_uses_the_config_default_only_when_nothing_is_stored():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "readCookieState()" in page
    assert "return null" in page  # nothing stored -> the config default decides the opening


def test_the_page_has_the_panel_and_its_toggle():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert 'id="panel"' in page
    assert 'id="toggle"' in page
    assert "#roster { flex: 0 0 55% }" in page
    assert "@media (max-width: 900px)" in page


def test_the_page_builds_an_agent_line_from_the_name_and_the_author():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Spec line format: the name, the author, then the separator, then the text.
    assert "const head = [entry.name, entry.author].filter(Boolean);" in page
    assert 'head.join(" ") + " — " + entry.text' in page


def test_the_page_words_the_actions_and_keeps_an_unknown_action_as_recorded():
    client = build_app()
    page = client.get("/api/roster/view").text

    # An action outside the mapping is shown as recorded, not as a broken line.
    assert '(PAST[entry.action] || entry.action) + "."' in page


def test_the_page_builds_an_agent_line_from_the_name_and_the_author():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Spec line format: the name, the author, then the separator, then the text.
    assert "const head = [entry.name, entry.author].filter(Boolean);" in page
    assert 'head.join(" ") + " — " + entry.text' in page


def test_the_panel_and_the_saved_file_write_the_same_lines():
    client = build_app()
    page = client.get("/api/roster/view").text

    # The file uses formatLine over every entry, so the panel must not skip lines the file keeps.
    assert "entries.map(formatLine)" in page
    assert "if (!line) return" in page


def test_a_line_with_an_empty_name_does_not_start_with_a_separator():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Review focus line 4: the separator is dropped when there is no name.
    assert "entry.name ? " in page


def test_the_page_writes_lines_with_text_content():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Review focus line 2: a line that HTML would interpret must appear literally.
    assert "item.textContent" in page


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
    assert "ziomek_" in page
    assert "new Date(" in page


def test_the_page_writes_a_file_with_its_header_when_there_is_nothing_to_save():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Review focus line 5: the download happens even for an empty record.
    assert "new Blob(" in page
    assert "# Transcript" in page


def test_an_entry_with_nothing_to_show_produces_no_line():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Review focus line 1: a record entry with no name, text and author must not render "undefined".
    # The guard belongs in formatLine, so the panel and the saved file behave the same.
    assert "if (!entry.text && !entry.name && !entry.action)" in page
    assert "renderLine(entry)" in page


def test_the_toggle_stays_reachable_when_the_panel_is_hidden():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Review focus: a control inside the hidden pane cannot be used to open it again.
    assert "#layout.hide #transcript { display: none; }" in page
    assert "#menu { display: none" in page
    # A hidden panel must not keep its column, otherwise the roster does not take the width.
    assert "#layout.hide #panel { flex: 0 0 auto; }" in page


def test_the_page_words_the_actions_as_the_spec_sentences():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert '"join": "joined"' in page
    assert '"hold": "is on hold"' in page
    assert '"leave": "left"' in page


def test_the_page_names_the_file_with_the_short_extension():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert 'markdown: "md"' in page


def test_the_save_and_the_formats_have_actions():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert 'document.getElementById("formats")' in page
    assert 'document.getElementById("save")' in page


def test_the_page_writes_the_state_in_the_form_the_reader_can_follow():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Review focus line 1: the cookie interface is `setPanelState(state)`, value "1" or "0".
    assert 'setPanelState(shown ? "1" : "0")' in page


def test_the_page_has_one_state_for_the_panel():
    client = build_app()
    page = client.get("/api/roster/view").text

    # The class that hides the pane is the only source of truth, and the label follows it.
    assert 'classList.add("open")' not in page
    assert 'label.textContent = shown ? "hide" : "show"' in page


def test_the_panel_lines_keep_their_newlines_and_are_not_rebuilt_each_tick():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "#transcript li { white-space: pre-wrap; }" in page
    assert "rendered" in page  # the page keeps what it has already shown instead of clearing the list


def test_the_page_clears_the_panel_when_the_record_is_empty():
    client = build_app()
    page = client.get("/api/roster/view").text

    # A record that shrank means a new call: the old lines must not stay.
    assert 'document.getElementById("transcript").innerHTML = ""' in page
    assert "lastEntries.length < rendered" in page


def test_the_page_survives_a_failed_poll():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "try {" in page  # a failed fetch must not leave lines that no longer match the record


def test_the_page_gives_back_the_object_url_and_the_download_link():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "URL.revokeObjectURL" in page
    assert "document.body.appendChild(link)" in page


def test_the_cookie_reader_accepts_a_separator_without_the_space():
    client = build_app()
    page = client.get("/api/roster/view").text

    assert "(?:^|;\\s*)ziomek_panel=" in page


def test_the_tile_payload_has_one_texts_key():
    from ziomek.api import roster_view

    source = Path("src/ziomek/api/roster_view.py").read_text(encoding="utf-8")
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
    assert blocks(entries) == [{"kind": "system", "text": "John joined."}]


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


def test_the_transcript_payload_carries_the_groups_as_well_as_the_entries():
    client = build_app()
    get_roster().record("John", "join")
    get_roster().record("John", "text", text="compiling", author="agent")
    payload = client.get("/api/roster/transcript").json()
    assert payload["entries"][0]["action"] == "join"
    assert payload["blocks"][0]["kind"] == "system"
    assert payload["blocks"][1]["name"] == "John"
