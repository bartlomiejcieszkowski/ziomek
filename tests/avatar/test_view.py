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

    def test_view_page_returns_html(self, client):
        resp = client.get("/api/avatar/view")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_page_connects_to_avatar_websocket(self, client):
        html = client.get("/api/avatar/view").text
        assert "/api/avatar/ws" in html
        assert "<canvas" in html


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
        notify_change("idle", 0)
