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
