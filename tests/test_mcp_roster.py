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
    mcp_tools_module._roster = None
    yield
    mcp_tools_module._roster = None


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


def test_join_runs_the_timer_before_it_assigns():
    settings = Settings(roster_pool=[("John A.", "alice")], roster_quiet_for=10)
    roster = _get_roster(settings)
    quiet = roster.join()
    quiet.last_seen = 0.0

    _, second = _call("join", {}, settings)

    # The quiet participant was dropped first, so its entry was free to hand out.
    assert [p for p in roster.participants][0].name == second["name"]
    assert quiet.state == "left"


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

    assert [entry.action for entry in _get_roster(settings).events] == ["join", "hold"]


def test_the_first_join_links_the_participant_to_the_single_view():
    from ziomek.avatar.state_machine import AvatarStateMachine

    seen = []

    def hook(participant, expression, cycle_index):
        seen.append((participant, expression, cycle_index))

    machine = AvatarStateMachine(participant=None)
    machine.on_change = hook
    settings = Settings(roster_pool=[("John A.", "alice")])
    with patch("ziomek.server._state_machine", machine):
        _, joined = _call("join", {}, settings)

    assert machine.participant.name == joined["name"]

    _, other = _call("join", {}, settings)
    assert machine.participant.name == joined["name"]
