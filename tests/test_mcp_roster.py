"""MCP tools for taking part in one call."""

import asyncio
import json
from unittest.mock import patch

import pytest
from mcp.types import CallToolRequestParams

from ziomek.config import Settings
from ziomek.mcp import tools as mcp_tools_module
from ziomek.mcp.tools import _get_roster


@pytest.fixture(autouse=True)
def _fresh_roster():
    """Each test sees its own call, not the one the previous test made."""
    import ziomek.roster

    ziomek.roster._roster = None
    from ziomek.api import avatar_ws

    avatar_ws._shown = None
    yield
    ziomek.roster._roster = None
    from ziomek.api import avatar_ws

    avatar_ws._shown = None


def _call(name, arguments, settings):
    """Call one of the tools as an agent would, and read the reply text."""
    with patch("ziomek.server._settings", settings):
        result = asyncio.run(
            mcp_tools_module._on_call_tool(None, CallToolRequestParams(name=name, arguments=arguments))
        )
    return result, json.loads(result.content[0].text)


def test_join_tool_is_declared_with_the_reserved_call_id():
    names = [t.name for t in mcp_tools_module.TOOLS]
    assert "join" in names
    assert "hold" in names
    assert "leave" in names

    tool = next(t for t in mcp_tools_module.TOOLS if t.name == "join")
    assert "call_id" in tool.input_schema["properties"]
    assert tool.input_schema.get("required") == []


def test_calling_join_assigns_from_the_configured_pool():
    settings = Settings(roster_pool=[("John A.", "alice"), ("Mary S.", "bob")])
    result, data = _call("join", {"name": None, "voice": None}, settings)

    assert result.is_error is False
    assert data["name"] in ("John A.", "Mary S.")
    assert data["voice"] in ("alice", "bob")


def test_the_second_join_gets_the_remaining_entry():
    settings = Settings(roster_pool=[("John A.", "alice"), ("Mary S.", "bob")])
    _, first = _call("join", {}, settings)
    _, second = _call("join", {}, settings)

    assert first["name"] != second["name"]
    assert first["voice"] != second["voice"]


def test_hold_marks_the_participant_as_being_on_hold():
    settings = Settings(roster_pool=[("John A.", "alice")], roster_quiet_for=1234)
    _, joined = _call("join", {}, settings)
    _, held = _call("hold", {"name": joined["name"]}, settings)

    assert held["state"] == "held"
    assert held["quiet_for"] == settings.roster_quiet_for


def test_the_timer_drops_a_participant_that_stays_quiet():
    settings = Settings(roster_pool=[("John A.", "alice")], roster_quiet_for=10)
    roster = _get_roster(settings)
    participant = roster.join()
    participant.last_seen = 0.0

    dropped = roster.drop_quiet(now=10.0)

    assert [p.name for p in dropped] == [participant.name]
    assert roster.participants == []


def test_leave_releases_the_entry_so_it_can_be_assigned_again():
    settings = Settings(roster_pool=[("John A.", "alice")])
    _, joined = _call("join", {}, settings)
    _call("leave", {"name": joined["name"]}, settings)
    _, again = _call("join", {}, settings)

    assert again["name"] == joined["name"]


def test_the_record_kept_through_the_tools_is_for_this_call():
    settings = Settings(roster_pool=[("John A.", "alice")])
    _, joined = _call("join", {}, settings)
    _call("hold", {"name": joined["name"]}, settings)

    assert [entry["action"] for entry in _get_roster(settings).events] == ["join", "hold"]


def test_the_first_join_shows_that_participant_in_the_single_view():
    from ziomek.api import avatar_ws

    settings = Settings(roster_pool=[("John A.", "alice")])
    _, joined = _call("join", {}, settings)

    assert avatar_ws._shown.name == joined["name"]

    # The single view shows one participant, so a later join does not change it.
    _, other = _call("join", {}, settings)
    assert avatar_ws._shown.name == joined["name"]


def test_joining_a_name_that_is_already_in_the_call_reports_a_duplicate():
    settings = Settings(roster_pool=[("John A.", "alice")])
    _, joined = _call("join", {"name": "John A."}, settings)
    result, payload = _call("join", {"name": "John A."}, settings)

    assert result.is_error is True
    assert "duplicate" in payload["error"]


class recording_machine:
    def __init__(self):
        self.sets = []

    def setExpression(self, expression, duration_ms=None):
        self.sets.append((expression, duration_ms))
        return True

    def tick(self, dt_ms):
        return {"expression": None, "cycleIndex": 0}


def test_setting_an_expression_acts_on_the_named_participant():
    settings = Settings(roster_pool=[("John", "alice")])
    _, joined = _call("join", {}, settings)
    fallback = recording_machine()
    participant = _get_roster(settings).participants[0]
    participant.state_machine = recording_machine()

    with patch("ziomek.server._state_machine", fallback):
        result, data = _call("set_expression", {"expression": "happy", "name": joined["name"]}, settings)

    assert result.is_error is False
    assert participant.state_machine.sets == [("happy", None)]
    # The global machine is the fallback, it is not used when a participant is named.
    assert fallback.sets == []
    assert data["expression"] == "happy"


def test_the_global_machine_is_the_fallback_when_nobody_has_joined():
    settings = Settings(roster_pool=[("John", "alice")])
    fallback = recording_machine()

    with patch("ziomek.server._state_machine", fallback):
        result, data = _call("set_expression", {"expression": "happy"}, settings)

    assert result.is_error is False
    assert fallback.sets == [("happy", None)]
    assert data["expression"] == "happy"


def test_the_expression_tools_take_an_optional_name():
    for tool_name in ("set_expression", "get_expression"):
        tool = next(t for t in mcp_tools_module.TOOLS if t.name == tool_name)
        assert "name" in tool.input_schema["properties"]

    # The name stays optional, so an agent that does not name itself still works.
    set_tool = next(t for t in mcp_tools_module.TOOLS if t.name == "set_expression")
    assert set_tool.input_schema.get("required") == ["expression"]
    get_tool = next(t for t in mcp_tools_module.TOOLS if t.name == "get_expression")
    assert not get_tool.input_schema.get("required")


def test_speaking_for_a_participant_uses_the_voice_assigned_to_it():
    settings = Settings(roster_pool=[("John A.", "alice")])
    _call("join", {"name": "John A."}, settings)

    spoken = []

    def fake_generate_wav(model, cache, text, voice):
        spoken.append(voice)
        return (b"", 0.0, 24000)

    class ready_model:
        ready = True
        model_path = None

    with (
        patch("ziomek.server._settings", settings),
        patch("ziomek.server._tts_model", ready_model()),
        patch("ziomek.server._voice_cache", object()),
        patch("ziomek.server._audio_player", None),
        patch("ziomek.tts.generate.generate_wav", fake_generate_wav),
    ):
        asyncio.run(
            mcp_tools_module._on_call_tool(
                None, CallToolRequestParams(name="say", arguments={"name": "John A.", "text": "hi"})
            )
        )

    assert spoken == ["alice"]


def test_saying_text_records_what_was_said_for_that_participant():
    """The text said for a participant is kept with the participant."""
    settings = Settings(roster_pool=[("John A.", "alice")])

    class ready_model:
        ready = True
        model_path = None

    _, joined = _call("join", {"name": "John A."}, settings)

    def fake_generate_wav(model, cache, text, voice):
        return (b"", 0.0, 24000)

    with (
        patch("ziomek.server._settings", settings),
        patch("ziomek.server._tts_model", ready_model()),
        patch("ziomek.server._voice_cache", object()),
        patch("ziomek.server._audio_player", None),
        patch("ziomek.tts.generate.generate_wav", fake_generate_wav),
    ):
        _, data = _call("say", {"name": "John A.", "text": "compiling"}, settings)

    record = _get_roster(settings)
    entry = record.events[-1]
    assert entry["name"] == "John A."
    assert entry["action"] == "text"
    assert entry["author"] == "agent"


def test_write_records_text_without_speaking_it():
    """The write tool records text for a participant without producing audio."""
    settings = Settings(roster_pool=[("John A.", "alice")])
    tool = next(t for t in mcp_tools_module.TOOLS if t.name == "write")
    assert tool.input_schema["required"] == ["name", "text"]

    _, joined = _call("join", {"name": "John A."}, settings)

    class ready_model:
        ready = True
        model_path = None

    spoken = []

    def fake_generate_wav(model, cache, text, voice):
        spoken.append(voice)
        return (b"", 0.0, 24000)

    with (
        patch("ziomek.server._settings", settings),
        patch("ziomek.server._tts_model", ready_model()),
        patch("ziomek.server._voice_cache", object()),
        patch("ziomek.server._audio_player", None),
        patch("ziomek.tts.generate.generate_wav", fake_generate_wav),
    ):
        _, data = _call("write", {"name": "John A.", "text": "note to self"}, settings)

    entry = _get_roster(settings).events[-1]
    assert entry["action"] == "text"
    assert entry["text"] == "note to self"
    assert entry["author"] == "agent"
    assert spoken == []


def test_saying_text_is_recorded_by_default():
    """The say tool records the text unless the caller says not to record it."""
    settings = Settings(roster_pool=[("John A.", "alice")])
    tool = next(t for t in mcp_tools_module.TOOLS if t.name == "say")
    assert tool.input_schema["required"] == ["name", "text"]
    assert "record" in tool.input_schema["properties"]
    assert "record" not in tool.input_schema.get("required", [])

    _call("join", {"name": "John A."}, settings)

    class ready_model:
        ready = True
        model_path = None

    with (
        patch("ziomek.server._settings", settings),
        patch("ziomek.server._tts_model", ready_model()),
        patch("ziomek.server._voice_cache", object()),
        patch("ziomek.server._audio_player", None),
        patch("ziomek.tts.generate.generate_wav", lambda *a: (b"", 0.0, 24000)),
    ):
        _call("say", {"name": "John A.", "text": "thinking"}, settings)

    entry = _get_roster(settings).events[-1]
    assert entry["text"] == "thinking"


def test_saying_text_with_record_false_only_spoken_without_writing_it_down():
    """When record is false the call is spoken but nothing is written to the record."""
    settings = Settings(roster_pool=[("John A.", "alice")])
    _call("join", {"name": "John A."}, settings)

    class ready_model:
        ready = True
        model_path = None

    with (
        patch("ziomek.server._settings", settings),
        patch("ziomek.server._tts_model", ready_model()),
        patch("ziomek.server._voice_cache", object()),
        patch("ziomek.server._audio_player", None),
        patch("ziomek.tts.generate.generate_wav", lambda *a: (b"", 0.0, 24000)),
    ):
        _call("say", {"name": "John A.", "text": "not written", "record": False}, settings)

    record = _get_roster(settings)
    assert [entry for entry in record.events if entry["action"] == "text"] == []
    assert record.participants[0].texts == []
