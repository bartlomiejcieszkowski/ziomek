"""What a run serves for MCP, and on which port."""

from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient

from ziomek.config import Settings


def quiet_settings(**over) -> Settings:
    """Settings that start nothing real: no audio device, no speech engine, no gamepad."""
    base = dict(audio_backend="noop", no_stt=True, no_gamepad=True)
    base.update(over)
    return Settings(**base)


def served_page(settings: Settings) -> TestClient:
    """The app as it is built for a run, read on localhost so the origin is accepted."""
    from ziomek.server import create_app

    return TestClient(create_app(settings), base_url="http://localhost")


class RunsInline:
    """A thread stand-in that runs its work at once, so a test can see what it did."""

    def __init__(self, target=None, *args, **kwargs):
        self._target = target

    def start(self):
        if self._target:
            self._target()


def test_the_page_is_served_the_tools_when_nothing_is_stated():
    """MCP is on by default, so a plain run answers the tools on the main port."""
    answer = served_page(quiet_settings()).get("/mcp/health")
    assert answer.status_code == 200


def test_the_page_is_not_served_the_tools_when_the_run_turns_them_off():
    """Turning MCP off is what decides, and the default does not override it."""
    answer = served_page(quiet_settings(no_mcp=True)).get("/mcp/health")
    assert answer.status_code == 404


def test_the_stdio_server_runs_when_stdio_is_stated():
    """Stating stdio chooses that transport instead of the one taken by default."""
    settings = quiet_settings(mcp_transport="stdio")
    with (
        patch("ziomek.server.Settings.compose", return_value=settings),
        patch("ziomek.server.setup_logging"),
        patch("ziomek.server.uvicorn.run"),
        patch("threading.Thread", RunsInline),
        patch("ziomek.mcp.start_mcp_server", new=MagicMock()) as started_stdio,
    ):
        from ziomek.server import run_server

        run_server(port=5004, mcp_transport="stdio")

    started_stdio.assert_called_once()


def test_the_tools_are_served_on_their_own_process_when_an_other_port_is_stated():
    """A port that is not the main one means a server of its own, on that port."""
    settings = quiet_settings(port=5004, mcp_port=5005)
    with (
        patch("ziomek.server.Settings.compose", return_value=settings),
        patch("ziomek.server.setup_logging"),
        patch("ziomek.server.uvicorn.run"),
        patch("threading.Thread", RunsInline),
        patch("ziomek.mcp.http.start_mcp_http_server") as started_http,
    ):
        from ziomek.server import run_server

        run_server(port=5004)

    served_on = started_http.call_args.kwargs
    assert served_on["host"] == "localhost"
    assert served_on["port"] == 5005


def test_nothing_is_served_when_the_run_turns_them_off_even_if_stdio_is_stated():
    """Turning something off is a stronger statement than choosing how it is served."""
    settings = quiet_settings(no_mcp=True, mcp_transport="stdio")
    with (
        patch("ziomek.server.Settings.compose", return_value=settings),
        patch("ziomek.server.setup_logging"),
        patch("ziomek.server.uvicorn.run"),
        patch("threading.Thread", RunsInline),
        patch("ziomek.mcp.start_mcp_server", new=MagicMock()) as started_stdio,
        patch("ziomek.mcp.http.start_mcp_http_server") as started_http,
    ):
        from ziomek.server import run_server

        run_server(port=5004, no_mcp=True, mcp_transport="stdio")

    started_stdio.assert_not_called()
    started_http.assert_not_called()
