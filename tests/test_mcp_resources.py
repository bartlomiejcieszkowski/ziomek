"""ziomek MCP resources tests — MCP SDK 2.x API."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.lowlevel import Server
from mcp.types import (
    ListResourcesRequest,
    ReadResourceRequest,
    ReadResourceRequestParams,
)

from ziomek.mcp import resources as mcp_resources_module


class TestMcpVoicesResource:
    """Test the voices MCP resource."""

    def test_voices_returns_list(self):
        """Voices resource returns voice list."""
        mock_model = MagicMock()

        with patch("ziomek.server._tts_model", mock_model):

            server = Server("test")
            mcp_resources_module.register_resources(server)

            # Call on_list_resources first
            list_result = asyncio.run(
                server.on_list_resources(None, ListResourcesRequest())
            )
            voices_resource = None
            for r in list_result.resources:
                if r.uri == "voices://":
                    voices_resource = r
                    break

            assert voices_resource is not None

            # Call on_read_resource
            read_result = asyncio.run(
                server.on_read_resource(
                    None, ReadResourceRequest(
                        method="resources/read",
                        params=ReadResourceRequestParams(uri="voices://"),
                    )
                )
            )

            data = json.loads(read_result.contents[0].text)
            assert "voices" in data
            assert "cosette" in data["voices"]
            assert "default" in data
            assert data["default"] == "cosette"


class TestMcpModelsResource:
    """Test the models MCP resource."""

    def test_models_returns_list(self):
        """Models resource returns model list."""
        server = Server("test")
        mcp_resources_module.register_resources(server)

        list_result = asyncio.run(
            server.on_list_resources(None, ListResourcesRequest())
        )
        models_resource = None
        for r in list_result.resources:
            if r.uri == "models://":
                models_resource = r
                break

        assert models_resource is not None

        read_result = asyncio.run(
            server.on_read_resource(
                None, ReadResourceRequest(
                    method="resources/read",
                    params=ReadResourceRequestParams(uri="models://"),
                )
            )
        )

        data = json.loads(read_result.contents[0].text)
        assert "models" in data
        assert "tiny" in data["models"]
        assert "base" in data["models"]
        assert "default" in data
        assert data["default"] == "tiny.en"


class TestMcpExpressionsResource:
    """Test the expressions MCP resource."""

    def test_expressions_returns_list(self):
        """Expressions resource returns expression list."""
        server = Server("test")
        mcp_resources_module.register_resources(server)

        list_result = asyncio.run(
            server.on_list_resources(None, ListResourcesRequest())
        )
        expr_resource = None
        for r in list_result.resources:
            if r.uri == "expressions://":
                expr_resource = r
                break

        assert expr_resource is not None

        read_result = asyncio.run(
            server.on_read_resource(
                None, ReadResourceRequest(
                    method="resources/read",
                    params=ReadResourceRequestParams(uri="expressions://"),
                )
            )
        )

        data = json.loads(read_result.contents[0].text)
        assert "expressions" in data
        assert len(data["expressions"]) > 0


class TestMcpConfigResource:
    """Test the config MCP resource."""

    def test_config_returns_readonly(self):
        """Config resource returns read-only config by default."""
        mock_settings = MagicMock()
        mock_settings.host = "localhost"
        mock_settings.port = 5003
        mock_settings.voice = "cosette"
        mock_settings.cache_dir = "/tmp/cache"
        mock_settings.log_level = "INFO"
        mock_settings.stt_engine = "faster_whisper"
        mock_settings.stt_model = "tiny"
        mock_settings.stt_model_dir = None
        mock_settings.model_path = None

        with patch("ziomek.server._settings", mock_settings):

            server = Server("test")
            mcp_resources_module.register_resources(server, expose_full_config=False)

            list_result = asyncio.run(
                server.on_list_resources(None, ListResourcesRequest())
            )
            config_resource = None
            for r in list_result.resources:
                if r.uri == "config://":
                    config_resource = r
                    break

            assert config_resource is not None

            read_result = asyncio.run(
                server.on_read_resource(
                    None, ReadResourceRequest(
                        method="resources/read",
                        params=ReadResourceRequestParams(uri="config://"),
                    )
                )
            )

            data = json.loads(read_result.contents[0].text)
            assert data["host"] == "localhost"
            assert data["port"] == 5003
            assert data["voice"] == "cosette"
            assert "full_config" not in data

    def test_config_returns_full_with_flag(self):
        """Config resource returns full config with --mcp-config flag."""
        mock_settings = MagicMock()
        mock_settings.host = "localhost"
        mock_settings.port = 5003
        mock_settings.voice = "cosette"
        mock_settings.cache_dir = "/tmp/cache"
        mock_settings.log_level = "INFO"
        mock_settings.stt_engine = "faster_whisper"
        mock_settings.stt_model = "tiny"
        mock_settings.stt_model_dir = None
        mock_settings.model_path = None

        with patch("ziomek.server._settings", mock_settings):

            server = Server("test")
            mcp_resources_module.register_resources(server, expose_full_config=True)

            list_result = asyncio.run(
                server.on_list_resources(None, ListResourcesRequest())
            )
            config_resource = None
            for r in list_result.resources:
                if r.uri == "config://":
                    config_resource = r
                    break

            assert config_resource is not None

            read_result = asyncio.run(
                server.on_read_resource(
                    None, ReadResourceRequest(
                        method="resources/read",
                        params=ReadResourceRequestParams(uri="config://"),
                    )
                )
            )

            data = json.loads(read_result.contents[0].text)
            assert data["full_config"] is True

    def test_config_not_initialized(self):
        """Config resource returns error when settings not initialized."""
        with patch("ziomek.server._settings", None):

            server = Server("test")
            mcp_resources_module.register_resources(server)

            list_result = asyncio.run(
                server.on_list_resources(None, ListResourcesRequest())
            )
            config_resource = None
            for r in list_result.resources:
                if r.uri == "config://":
                    config_resource = r
                    break

            assert config_resource is not None

            read_result = asyncio.run(
                server.on_read_resource(
                    None, ReadResourceRequest(
                        method="resources/read",
                        params=ReadResourceRequestParams(uri="config://"),
                    )
                )
            )

            data = json.loads(read_result.contents[0].text)
            assert "error" in data
