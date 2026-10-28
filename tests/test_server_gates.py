"""Tests for the gamepad gate and for opening the served page on successful startup."""

import asyncio
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


class TestSttGate:
    """STT is gated by settings.no_stt, not by other flags."""

    def test_stt_not_started_when_disabled(self):
        from ziomek.config import Settings
        from ziomek.server import create_app

        settings = Settings(no_gamepad=True, no_stt=True)
        with (
            patch("ziomek.server.stt_installed", return_value=True),
            patch("ziomek.server.STTEngine") as engine,
        ):
            app = create_app(settings)

        assert app is not None
        engine.assert_not_called()

    def test_stt_started_when_enabled(self):
        from ziomek.config import Settings
        from ziomek.server import create_app

        settings = Settings(no_gamepad=True)
        with (
            patch("ziomek.server.stt_installed", return_value=True),
            patch("ziomek.server.STTEngine") as engine,
        ):
            create_app(settings)

        engine.assert_called_once()

    def test_run_server_passes_no_stt_to_settings(self):
        from ziomek.config import Settings
        from ziomek.server import run_server

        with (
            patch("ziomek.server.Settings.compose", return_value=Settings()) as compose,
            patch("ziomek.server.create_app") as created,
            patch("ziomek.server.uvicorn.run"),
            patch("ziomek.server.setup_logging"),
        ):
            run_server(no_stt=True)

        assert compose.call_args.kwargs["no_stt"] is True
        assert created.call_args.kwargs["open_browser"] is True


class TestEventLoopRegistration:
    """The app hands its event loop to the STT engine so worker-thread callbacks can run."""

    def test_loop_is_registered_on_startup(self):
        settings = Settings(no_gamepad=True, no_browser=True)
        captured = {}

        with (
            patch("ziomek.server.STTEngine") as engine_cls,
            patch("ziomek.server.stt_installed", return_value=True),
        ):
            app = create_app(settings)
            engine = engine_cls.return_value

            def fake_set_event_loop(loop):
                captured["loop"] = loop

            engine.set_event_loop = fake_set_event_loop

            # Entering the TestClient context runs the startup handler.
            with TestClient(app):
                assert captured.get("loop") is not None
                assert isinstance(captured["loop"], asyncio.AbstractEventLoop)

    def test_nothing_registered_when_the_engine_was_not_created(self):
        settings = Settings(no_gamepad=True, no_browser=True, no_stt=True)
        with patch("ziomek.server.STTEngine") as engine_cls:
            app = create_app(settings)
            engine_cls.assert_not_called()
            with TestClient(app):
                pass
