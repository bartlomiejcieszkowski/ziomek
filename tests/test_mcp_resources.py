"""ziomek MCP resources tests — MCP SDK 2.x API."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest
from mcp.server import Server
from mcp.types import ReadResourceRequestParams, TextResourceContents

from ziomek.mcp import resources as mcp_resources_module


class TestMcpListResources:
    """Test the list_resources MCP endpoint."""

    def test_resources_list_has_all_resources(self):
        """RESOURCES list has all 4 resources."""
        uris = [r.uri for r in mcp_resources_module.RESOURCES]
        assert "voices://" in uris
        assert "models://" in uris
        assert "expressions://" in uris
        assert "config://" in uris
        assert len(uris) == 4

    def test_resources_have_correct_fields(self):
        """Each resource has uri, name, and description."""
        for resource in mcp_resources_module.RESOURCES:
            assert isinstance(resource.uri, str) and len(resource.uri) > 0
            assert isinstance(resource.name, str) and len(resource.name) > 0
            assert isinstance(resource.description, str) and len(resource.description) > 0


class TestMcpReadResources:
    """Test the read_resource MCP endpoint."""

    def test_read_voices_resource(self):
        """voices:// returns list of voices."""
        result = asyncio.run(mcp_resources_module._on_read_resource(None, ReadResourceRequestParams(uri="voices://")))
        assert len(result.contents) == 1
        content = result.contents[0]
        assert isinstance(content, TextResourceContents)
        assert content.uri == "voices://"
        data = json.loads(content.text)
        assert "voices" in data
        assert "default" in data
        assert "cosette" in data["voices"]

    def test_read_models_resource(self):
        """models:// returns list of models."""
        result = asyncio.run(mcp_resources_module._on_read_resource(None, ReadResourceRequestParams(uri="models://")))
        assert len(result.contents) == 1
        content = result.contents[0]
        assert isinstance(content, TextResourceContents)
        assert content.uri == "models://"
        data = json.loads(content.text)
        assert "models" in data
        assert "default" in data
        assert "tiny" in data["models"]

    def test_read_expressions_resource(self):
        """expressions:// returns list of expressions."""
        result = asyncio.run(
            mcp_resources_module._on_read_resource(None, ReadResourceRequestParams(uri="expressions://"))
        )
        assert len(result.contents) == 1
        content = result.contents[0]
        assert isinstance(content, TextResourceContents)
        assert content.uri == "expressions://"
        data = json.loads(content.text)
        assert "expressions" in data
        assert len(data["expressions"]) > 0

    def test_read_config_resource(self):
        """config:// returns server config."""
        with patch("ziomek.server._settings", None):
            result = asyncio.run(
                mcp_resources_module._on_read_resource(None, ReadResourceRequestParams(uri="config://"))
            )
            assert len(result.contents) == 1
            content = result.contents[0]
            assert isinstance(content, TextResourceContents)
            assert content.uri == "config://"
            data = json.loads(content.text)
            assert "error" in data

    def test_read_config_resource_with_settings(self):
        """config:// returns config when settings exist."""
        from ziomek.mcp import set_expose_full_config

        mock_settings = MagicMock()
        mock_settings.host = "localhost"
        mock_settings.port = 5003
        mock_settings.voice = "cosette"
        mock_settings.cache_dir = "/tmp/cache"
        mock_settings.log_level = "INFO"
        mock_settings.stt_engine = "faster_whisper"
        mock_settings.stt_model = "tiny.en"
        mock_settings.stt_model_dir = "/tmp/models"
        mock_settings.model_path = None

        set_expose_full_config(True)

        with patch("ziomek.server._settings", mock_settings):
            result = asyncio.run(
                mcp_resources_module._on_read_resource(None, ReadResourceRequestParams(uri="config://"))
            )
            assert len(result.contents) == 1
            content = result.contents[0]
            assert isinstance(content, TextResourceContents)
            assert content.uri == "config://"
            data = json.loads(content.text)
            assert data["host"] == "localhost"
            assert data["port"] == 5003
            assert data["voice"] == "cosette"
            assert data["stt_engine"] == "faster_whisper"
            assert data["stt_model"] == "tiny.en"
