"""Tests for the avatar view page and its WebSocket updates."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from ziomek.api.avatar_ws import _connected_clients, router


@pytest.fixture(autouse=True)
def clear_ws_clients():
    """Clear WebSocket clients before each test."""
    _connected_clients.clear()
    yield
    _connected_clients.clear()


@pytest.fixture
def client():
    """Create a test client with the avatar WebSocket route."""
    from ziomek.config import Settings
    from ziomek.server import create_app

    settings = Settings(no_gamepad=True, no_stt=True, no_browser=True)
    app = create_app(settings=settings, dev_mode=False)
    app.include_router(router)
    with TestClient(app) as test_client:
        yield test_client


class TestAvatarViewPage:
    """The served page must exist and connect to the WebSocket route."""

    def test_the_page_for_the_faces_is_answered_as_a_document(self, client):
        resp = client.get("/avatar")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_the_page_names_an_address_an_icon_can_be_answered_from(self, client):
        # A browser asks for an icon on its own when it renders a page, so the page names the
        # path the app answers for instead of the one nothing serves.
        resp = client.get("/avatar")
        assert '<link rel="icon" href="/favicon.svg">' in resp.text

    def test_page_has_separate_areas_for_name_and_text(self, client):
        html = client.get("/avatar").text
        for element in ("name", "status_text", "system_text"):
            assert f'id="{element}"' in html

    def test_page_shows_the_fields_from_a_state_message(self, client):
        html = client.get("/avatar").text
        # The message carries the three areas, so the page must render all of them.
        for field in ("name", "status_text", "system_text"):
            assert f"msg.{field}" in html

    def test_page_shows_a_participant_as_on_hold(self, client):
        html = client.get("/avatar").text
        assert 'id="on_hold"' in html
        # The duration counts up on the client, not only in the message.
        assert "On hold" in html

    def test_page_shows_the_events_of_the_call(self, client):
        html = client.get("/avatar").text
        assert 'id="events"' in html
        assert "msg.events" in html


class TestAvatarWebSocket:
    """The WebSocket pushes state: first on connect, then on every change."""

    def test_initial_state_on_connect(self, client):
        with client.websocket_connect("/api/avatar/ws") as ws:
            message = ws.receive_json()
            assert message["type"] == "state"
            assert isinstance(message["expression"], str)
            assert isinstance(message["cycleIndex"], int)

    def test_update_after_expression_change(self, client):
        from ziomek.server import _state_machine

        with client.websocket_connect("/api/avatar/ws") as ws:
            initial = ws.receive_json()
            assert initial["type"] == "state"

            _state_machine.setExpression("happy")
            message = ws.receive_json()
            assert message["type"] == "state"
            assert message["expression"] == "happy"

    def test_initial_state_comes_from_the_participant_record(self, client, monkeypatch):
        from ziomek.api import avatar_ws
        from ziomek.roster import Roster
        from ziomek.server import _state_machine

        participant = Roster().join("John D.")
        participant.add_text("compiling", author="agent")
        # The single view renders the shown participant, not the global machine's record.
        monkeypatch.setattr(avatar_ws, "_shown", participant)
        monkeypatch.setattr(participant, "state_machine", _state_machine)

        with client.websocket_connect("/api/avatar/ws") as ws:
            message = ws.receive_json()
            assert message["name"] == "John D."
            assert message["status_text"] == "compiling"

    def test_disconnected_client_is_removed(self, client):
        with client.websocket_connect("/api/avatar/ws") as ws:
            ws.receive_json()
            assert len(_connected_clients) == 1
        assert not _connected_clients


class TestChangeHook:
    """The state machine notifies the WebSocket instead of being polled."""

    def test_hook_is_registered_on_the_state_machine(self, client):
        from ziomek.server import _state_machine

        assert _state_machine.on_change is not None

    def test_hook_fails_without_a_state_machine(self):
        from ziomek.api.avatar_ws import notify_change

        # No state machine registered -> the hook must not raise.
        notify_change(None, "neutral", 0)

    def test_hook_receives_the_participant_record(self):
        from ziomek.avatar.state_machine import AvatarStateMachine
        from ziomek.roster import Roster

        participant = Roster().join("John C.")
        seen = []
        machine = AvatarStateMachine(participant=participant)
        machine.on_change = lambda record, expression, cycle_index: seen.append((record, expression, cycle_index))
        machine.setExpression("happy")

        assert seen[0][0] is participant
