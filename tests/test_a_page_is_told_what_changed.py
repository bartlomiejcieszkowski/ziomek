"""A page is told which part of the picture changed, so it asks only for that part."""

from __future__ import annotations

import asyncio
import logging

import pytest
from starlette.testclient import TestClient

from ziomek import event_loop, roster
from ziomek.api import roster_ws
from ziomek.config import Settings
from ziomek.mcp import tools as mcp_tools
from ziomek.server import create_app

SIGNAL_PATH = "/api/roster/ws"


@pytest.fixture(autouse=True)
def no_page_is_listening():
    """Each test starts with nobody connected, so a message is not left over from the last test."""
    roster_ws._connected_clients.clear()
    event_loop.set_event_loop(None)
    yield
    roster_ws._connected_clients.clear()
    event_loop.set_event_loop(None)


@pytest.fixture
def app_running():
    """The app as it runs, with its event loop captured at startup."""
    settings = Settings(no_gamepad=True, no_stt=True)
    app = create_app(settings=settings, dev_mode=False)
    with TestClient(app) as running:
        yield running


def test_a_page_is_told_that_the_room_changed_when_someone_joins(app_running):
    """A participant added to the call is a change to the room."""
    with app_running.websocket_connect(SIGNAL_PATH) as page:
        roster.get_roster().join("John")
        assert page.receive_json()["kind"] == "room"


def test_a_page_is_told_that_the_record_grew_when_a_line_is_written(app_running):
    """A line written for a participant is a change to the record."""
    with app_running.websocket_connect(SIGNAL_PATH) as page:
        participant = roster.get_roster().join("John")
        # The join itself is drained here so the message read next is the one this test is about.
        assert page.receive_json()["kind"] == "room"
        participant.add_text("compiling", author="agent")
        assert page.receive_json()["kind"] == "record"


def test_a_page_is_told_that_the_room_changed_when_a_participant_is_held(app_running):
    """A participant becoming quiet is a change to the room.

    A line is written for it too, so the message for the record comes as well; this test reads the
    room one, which is what its name is about.
    """
    with app_running.websocket_connect(SIGNAL_PATH) as page:
        participant = roster.get_roster().join("John")
        assert page.receive_json()["kind"] == "room"
        assert page.receive_json()["kind"] == "record"
        participant.hold()
        assert page.receive_json()["kind"] == "room"


def test_a_page_is_told_that_the_room_changed_when_a_participant_is_resumed(app_running):
    """A participant becoming active again is a change to the room."""
    with app_running.websocket_connect(SIGNAL_PATH) as page:
        participant = roster.get_roster().join("John")
        assert page.receive_json()["kind"] == "room"
        assert page.receive_json()["kind"] == "record"
        # Becoming quiet is told to the room, and writing the line for it is told to the record.
        participant.hold()
        assert page.receive_json()["kind"] == "room"
        assert page.receive_json()["kind"] == "record"
        # Becoming active again writes no line, so the message can only be about the room.
        participant.resume()
        assert page.receive_json()["kind"] == "room"


def test_a_page_is_told_that_the_room_changed_when_a_participant_leaves(app_running):
    """A participant going away is a change to the room."""
    with app_running.websocket_connect(SIGNAL_PATH) as page:
        participant = roster.get_roster().join("John")
        assert page.receive_json()["kind"] == "room"
        assert page.receive_json()["kind"] == "record"
        participant.leave()
        assert page.receive_json()["kind"] == "room"


def test_a_page_is_told_only_about_what_changed(app_running):
    """Nothing was added, removed or written, so the next message is the one for a real change.

    A read here waits for a message, so it cannot show that nothing was sent; what it can show is
    that the message it gets is for the change below the action that changed nothing.
    """
    with app_running.websocket_connect(SIGNAL_PATH) as page:
        participant = roster.get_roster().join("John")
        assert page.receive_json()["kind"] == "room"
        assert page.receive_json()["kind"] == "record"
        # Marking the participant active now changes nothing in the room or in the record.
        participant.seen()
        # So the next message can only come from the change below it.
        participant.hold()
        assert page.receive_json()["kind"] == "room"


def test_a_join_that_also_writes_to_the_record_is_told_as_two_changes(app_running):
    """A join adds a participant and writes a line, so both are told as separate changes."""
    with app_running.websocket_connect(SIGNAL_PATH) as page:
        roster.get_roster().join("John")
        first = page.receive_json()
        second = page.receive_json()
        assert len({first["kind"], second["kind"]}) == 2


def test_every_open_page_is_told_what_changed(app_running):
    """The change is for the room as a whole, so every page looking at it is told."""
    with (
        app_running.websocket_connect(SIGNAL_PATH) as first_page,
        app_running.websocket_connect(SIGNAL_PATH) as second_page,
    ):
        roster.get_roster().join("John")
        assert first_page.receive_json()["kind"] == "room"
        assert second_page.receive_json()["kind"] == "room"


def test_the_app_still_works_when_no_page_is_connected_to_be_told(app_running):
    """A call runs without a page listening, so telling nobody is not a failure."""
    running_roster = roster.get_roster()
    participant = running_roster.join("John")
    assert participant.name == "John"
    assert len(running_roster.participants) == 1


class PageThatCannotBeSentTo:
    """A page whose connection gives a failure when something is sent to it."""

    async def send_json(self, message):
        raise RuntimeError("the socket is closed")


def test_a_page_that_cannot_be_sent_to_is_no_longer_listened_for():
    """A page that cannot be sent to is not kept as a page to tell the next change to."""
    roster_ws._connected_clients.append(PageThatCannotBeSentTo())
    asyncio.run(roster_ws._broadcast({"kind": "room"}))
    assert roster_ws._connected_clients == []


def test_a_failure_to_tell_a_page_is_said_in_the_log():
    """A page dropped because nothing could be sent to it is not dropped without a trace."""
    records = []

    class Records(logging.Handler):
        def emit(self, record):
            records.append(record)

    log = logging.getLogger("ziomek.api.roster_ws")
    handler = Records()
    log.addHandler(handler)
    try:
        roster_ws._connected_clients.append(PageThatCannotBeSentTo())
        asyncio.run(roster_ws._broadcast({"kind": "room"}))
    finally:
        log.removeHandler(handler)
    assert records, "nothing was said about the failure"


def test_a_page_is_told_that_the_record_was_cleared_when_the_call_ends(app_running):
    """The record is cleared when the last participant goes away, so the page has to be told that changed too."""
    running_roster = roster.get_roster()
    with app_running.websocket_connect(SIGNAL_PATH) as page:
        participant = running_roster.join("John")
        assert page.receive_json()["kind"] == "room"
        assert page.receive_json()["kind"] == "record"
        # Past the quiet time the participant is dropped, and with it the call ends.
        running_roster.drop_quiet(participant.last_seen + running_roster.quiet_for)
        assert page.receive_json()["kind"] == "room"
        assert page.receive_json()["kind"] == "record"
        # The record itself was cleared, which is a change of its own.
        assert page.receive_json()["kind"] == "record"


def test_a_change_that_comes_through_the_tools_reaches_a_connected_page(app_running):
    """The tools join on the same roster the app built, so their change is told as well."""
    with app_running.websocket_connect(SIGNAL_PATH) as page:
        result = asyncio.run(mcp_tools._handle_join({"name": "John"}))
        assert not result.is_error
        assert page.receive_json()["kind"] == "room"
