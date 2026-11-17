"""A caller outside the app asks which messages it has not been answered with."""

from __future__ import annotations

import asyncio
import json

from mcp.types import CallToolRequestParams

from ziomek.mcp import tools as mcp_tools
from ziomek.roster import Roster


def _call_tool(name, arguments):
    return asyncio.run(mcp_tools._on_call_tool(None, CallToolRequestParams(name=name, arguments=arguments)))


def test_the_caller_is_answered_through_the_one_definition_of_which_messages_are_new(monkeypatch):
    """The tool answers what the definition says, not what it works out on its own."""

    roster = Roster()
    speaker = roster.join("John A.")
    speaker.add_text("a word the speaker wrote for themselves", author=speaker.name)
    monkeypatch.setattr("ziomek.mcp.tools.get_roster", lambda: roster)
    # A definition that does not skip a line its own author wrote, so the answer differs from what
    # the tool would have built for itself.
    monkeypatch.setattr(
        "ziomek.messages.answer_new_messages_for",
        lambda participant, entries: [entry for entry in entries if entry.get("text") is not None],
    )

    result = _call_tool("read_messages", {"name": speaker.name})
    data = json.loads(result.content[0].text)
    assert [entry.get("text") for entry in data["messages"]] == ["a word the speaker wrote for themselves"]


def test_the_tool_records_what_a_caller_said_it_read_on_the_participant_it_names(monkeypatch):
    """Saying what was read changes what the next reading answers, so the tool has to reach the participant."""

    roster = Roster()
    speaker = roster.join("John A.")
    listener = roster.join("Ada")
    speaker.add_text("the line the caller read", author=speaker.name)
    speaker.add_text("the line the caller did not read", author=speaker.name)
    monkeypatch.setattr("ziomek.mcp.tools.get_roster", lambda: roster)

    # A caller can only say what it was answered with, so the entries it names are the ones the reading gave it.
    answered = json.loads(_call_tool("read_messages", {"name": listener.name}).content[0].text)["messages"]
    _call_tool("mark_as_read", {"name": listener.name, "entries": [answered[0]]})

    data = json.loads(_call_tool("read_messages", {"name": listener.name}).content[0].text)
    assert [entry.get("text") for entry in data["messages"]] == ["the line the caller did not read"]
