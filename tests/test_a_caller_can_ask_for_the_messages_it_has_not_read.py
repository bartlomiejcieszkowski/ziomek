"""A caller outside the app asks which messages it has not been answered with."""

from __future__ import annotations

import asyncio
import json

from mcp.types import CallToolRequestParams

from ziomek.mcp import tools as mcp_tools
from ziomek.roster import Roster


def _call_tool(name, arguments):
    return asyncio.run(mcp_tools._on_call_tool(None, CallToolRequestParams(name=name, arguments=arguments)))


def test_a_caller_can_ask_for_the_messages_it_has_not_been_answered_with(monkeypatch):
    roster = Roster()
    speaker = roster.join("John A.")
    caller = roster.join("Maria B.")
    speaker.add_text("the kettle is on", author=speaker.name)
    speaker.add_text("a word kept for later", author=speaker.name)
    caller.set_read_up_to(roster.events[0]["time"])
    monkeypatch.setattr("ziomek.mcp.tools.get_roster", lambda: roster)

    result = _call_tool("read_messages", {"name": caller.name})
    data = json.loads(result.content[0].text)
    assert [entry["text"] for entry in data["messages"]] == ["a word kept for later"]


def test_the_caller_is_answered_through_the_one_definition_of_which_messages_are_new(monkeypatch):
    """A different answer from the definition shows up, so the tool does not keep its own check."""

    roster = Roster()
    speaker = roster.join("John A.")
    speaker.add_text("a line that is not a message", author=speaker.name)
    speaker.add_text("the kettle is on", author=speaker.name)
    monkeypatch.setattr("ziomek.mcp.tools.get_roster", lambda: roster)
    monkeypatch.setattr(
        "ziomek.messages.answer_new_messages_for",
        lambda participant, entries: [entry for entry in entries if entry["text"] != "a line that is not a message"],
    )

    result = _call_tool("read_messages", {"name": speaker.name})
    data = json.loads(result.content[0].text)
    assert [entry["text"] for entry in data["messages"]] == ["the kettle is on"]
