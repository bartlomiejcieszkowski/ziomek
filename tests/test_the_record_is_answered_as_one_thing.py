"""What a client is shown when it reads the record as one thing."""

from __future__ import annotations

import asyncio
import json

import pytest
from mcp.types import ReadResourceRequestParams

from ziomek.mcp import resources as mcp_resources
from ziomek.roster import Roster

RECORD_URI = "message://"


@pytest.fixture
def call_with_one_line(monkeypatch):
    """A call holding one line written by someone else, reached through the record."""
    roster = Roster()
    speaker = roster.join("John A.")
    listener = roster.join("Maria B.")
    speaker.add_text("the kettle is on", author=speaker.name)
    monkeypatch.setattr("ziomek.roster.get_roster", lambda: roster)
    return listener


def read_record():
    return asyncio.run(mcp_resources._on_read_resource(None, ReadResourceRequestParams(uri=RECORD_URI)))


def test_the_record_is_shown_to_a_client_as_something_it_can_read():
    """The registration is what a client is shown as available, so this reads the list."""
    shown = asyncio.run(mcp_resources._on_list_resources(None, None))
    assert RECORD_URI in [resource.uri for resource in shown.resources]


def test_the_record_a_client_reads_carries_only_the_lines_that_were_written(call_with_one_line):
    result = read_record()
    data = json.loads(result.contents[0].text)
    assert [entry["text"] for entry in data["messages"]] == ["the kettle is on"]


def test_the_record_is_answered_through_the_one_definition_of_what_a_message_is(call_with_one_line, monkeypatch):
    """Nothing here may decide on its own what a message is, so a different answer must show up."""

    def answers_only_lines_by_this_author(entry):
        return entry.get("author") == "Maria B."

    monkeypatch.setattr("ziomek.messages.is_message", answers_only_lines_by_this_author)

    result = read_record()
    data = json.loads(result.contents[0].text)
    assert data["messages"] == []
