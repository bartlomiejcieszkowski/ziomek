"""Tests for the gamepad gate and for opening the served page on successful startup."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ziomek.config import Settings
from ziomek.server import create_app


@pytest.fixture
def client():
    settings = Settings(no_gamepad=True, no_browser=True)
    app = create_app(settings)
    return TestClient(app)


class TestGamepadGate:
    """--no-gamepad gates gamepad polling; it is the only thing that flag controls now."""

    def test_gamepad_thread_not_started_when_no_gamepad(self):
        settings = Settings(no_gamepad=True)
        with patch("ziomek.server._start_gamepad_thread") as start:
            create_app(settings)
            start.assert_not_called()

    def test_gamepad_thread_started_by_default(self):
        settings = Settings(no_gamepad=True.__class__(False))  # no_gamepad=False
        with patch("ziomek.server._start_gamepad_thread") as start:
            create_app(settings)
            start.assert_called_once()


class TestBrowserOpeningOnStartup:
    """The page is opened only after the server has started, unless --no-browser is set."""

    def test_not_opened_by_default(self):
        settings = Settings(no_gamepad=True, no_browser=True)
        app = create_app(settings)
        with patch("webbrowser.open") as opened:
            with TestClient(app):  # entering the context fires startup handlers
                pass
            opened.assert_not_called()

    def test_opened_when_server_requests_it(self):
        settings = Settings(no_gamepad=True, no_browser=False)
        app = create_app(settings, open_browser=True)
        with patch("webbrowser.open") as opened:
            with TestClient(app):
                pass
            opened.assert_called_once_with("http://localhost:5004/api/avatar/view")

    def test_run_server_requests_opening_when_browser_not_disabled(self):
        from ziomek.server import run_server

        with (
            patch("ziomek.server.create_app") as created,
            patch("ziomek.server.uvicorn.run"),
            patch("ziomek.server.setup_logging"),
        ):
            run_server(no_gamepad=True, no_browser=False)

        assert created.call_args.kwargs["open_browser"] is True

    def test_run_server_does_not_request_opening_with_no_browser(self):
        from ziomek.server import run_server

        with (
            patch("ziomek.server.create_app") as created,
            patch("ziomek.server.uvicorn.run"),
            patch("ziomek.server.setup_logging"),
        ):
            run_server(no_gamepad=True, no_browser=True)

        assert created.call_args.kwargs["open_browser"] is False
