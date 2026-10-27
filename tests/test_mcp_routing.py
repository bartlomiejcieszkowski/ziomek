"""Tests for MCP port-based routing logic."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


class TestMcpPortRouting:
    """Tests for MCP port-based routing in run_server()."""

    @patch("ziomek.server.create_app")
    @patch("ziomek.server.setup_logging")
    @patch("ziomek.server.uvicorn.run")
    @patch("ziomek.server.Settings.compose")
    def test_mcp_http_on_same_port_integrated(
        self,
        mock_compose,
        mock_uvicorn,
        mock_logging,
        mock_create_app,
    ):
        """When mcp_http=True and mcp_port matches main port → integrated on main port."""
        from ziomek.server import run_server

        mock_settings = MagicMock()
        mock_settings.host = "localhost"
        mock_settings.port = 5004
        mock_settings.mcp_port = 5004
        mock_compose.return_value = mock_settings
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        run_server(
            port=5004,
            mcp_http=True,
            mcp_port=5004,
        )

        # Should call register_mcp_http_routes to integrate on main app
        mock_create_app.assert_called_once()
        # Verify the app was patched with MCP routes
        call_kwargs = mock_create_app.call_args[1]
        assert call_kwargs.get("mcp_http") is True
        # uvicorn.run should be called once on main port
        assert mock_uvicorn.call_count == 1
        mock_uvicorn.assert_called_with(mock_app, host="localhost", port=5004)

    @patch("ziomek.mcp.http.start_mcp_http_server")
    @patch("ziomek.server.create_app")
    @patch("ziomek.server.setup_logging")
    @patch("ziomek.server.uvicorn.run")
    @patch("ziomek.server.Settings.compose")
    def test_mcp_http_on_different_port_separate(
        self,
        mock_compose,
        mock_uvicorn,
        mock_logging,
        mock_create_app,
        mock_mcp_server,
    ):
        """When mcp_http=True and mcp_port differs → separate MCP server."""
        from ziomek.server import run_server

        mock_settings = MagicMock()
        mock_settings.host = "localhost"
        mock_settings.port = 5004
        mock_settings.mcp_port = 5005  # Different from main port
        mock_compose.return_value = mock_settings
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        class _ImmediateThread:
            def __init__(self, target=None, *args, **kwargs):
                self._target = target

            def start(self):
                if self._target:
                    self._target()

        # The MCP dispatch runs in a daemon thread; run it inline so this is deterministic.
        with patch("ziomek.server.threading.Thread", _ImmediateThread):
            run_server(
                port=5004,
                mcp_http=True,
                mcp_port=5005,
            )

        # MCP must be served on its own port, not merged into the main app.
        mock_mcp_server.assert_called_once_with(host="localhost", port=5005)
        # uvicorn.run should be called once for main server
        assert mock_uvicorn.call_count == 1
        mock_uvicorn.assert_called_with(mock_app, host="localhost", port=5004)

    @patch("ziomek.server.create_app")
    @patch("ziomek.server.setup_logging")
    @patch("ziomek.server.uvicorn.run")
    @patch("ziomek.server.Settings.compose")
    def test_mcp_http_not_enabled(
        self,
        mock_compose,
        mock_uvicorn,
        mock_logging,
        mock_create_app,
    ):
        """When mcp_http=False → no MCP routing."""
        from ziomek.server import run_server

        mock_settings = MagicMock()
        mock_settings.host = "localhost"
        mock_settings.port = 5004
        mock_compose.return_value = mock_settings
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        run_server(
            port=5004,
            mcp_http=False,
        )

        # Should call uvicorn.run once (no MCP)
        assert mock_uvicorn.call_count == 1
        mock_uvicorn.assert_called_with(mock_app, host="localhost", port=5004)

    @patch("ziomek.server.create_app")
    @patch("ziomek.server.setup_logging")
    @patch("ziomek.server.uvicorn.run")
    @patch("ziomek.server.Settings.compose")
    def test_mcp_stdio_enabled(
        self,
        mock_compose,
        mock_uvicorn,
        mock_logging,
        mock_create_app,
    ):
        """When mcp_stdio=True → MCP stdio server in background thread."""
        from ziomek.server import run_server

        mock_settings = MagicMock()
        mock_settings.host = "localhost"
        mock_settings.port = 5004
        mock_compose.return_value = mock_settings
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        run_server(
            port=5004,
            mcp_stdio=True,
        )

        # Should call uvicorn.run once (MCP stdio runs in thread)
        assert mock_uvicorn.call_count == 1
        mock_uvicorn.assert_called_with(mock_app, host="localhost", port=5004)
