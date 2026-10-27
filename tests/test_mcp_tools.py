"""ziomek MCP tools tests — MCP SDK 2.x API."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import wave
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from mcp.server import Server
from mcp.types import CallToolRequestParams, TextContent

from ziomek.mcp import tools as mcp_tools_module


def _make_wav_bytes(duration_s: float = 0.1, sample_rate: int = 16000) -> bytes:
    """Generate minimal WAV bytes for testing."""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s))
    samples = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    samples = (samples * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


class TestMcpListTools:
    """Test the list_tools MCP endpoint."""

    def test_tools_list_has_all_tools(self):
        """TOOLS list has all 8 tools."""
        tool_names = [t.name for t in mcp_tools_module.TOOLS]
        assert "speak" in tool_names
        assert "transcribe" in tool_names
        assert "start_listening" in tool_names
        assert "get_transcription" in tool_names
        assert "stop_listening" in tool_names
        assert "set_expression" in tool_names
        assert "get_expression" in tool_names
        assert "status" in tool_names
        assert len(tool_names) == 8

    def test_tools_have_correct_schema(self):
        """Each tool has name, description, and inputSchema."""
        for tool in mcp_tools_module.TOOLS:
            assert isinstance(tool.name, str) and len(tool.name) > 0
            assert isinstance(tool.description, str) and len(tool.description) > 0
            assert isinstance(tool.input_schema, dict)
            assert tool.input_schema.get("type") == "object"


class TestMcpCallTool:
    """Test the call_tool MCP endpoint."""

    def test_call_unknown_tool(self):
        """Unknown tool returns error."""
        result = asyncio.run(
            mcp_tools_module._on_call_tool(None, CallToolRequestParams(name="nonexistent", arguments={}))
        )
        assert result.is_error is True
        content = result.content[0]
        assert isinstance(content, TextContent)
        assert "nonexistent" in content.text

    def test_call_status_tool(self):
        """Status tool returns dict with expected fields."""
        with patch("ziomek.mcp.tools._get_listening_session", return_value=MagicMock()):
            with patch("ziomek.server._state_machine", None):
                with patch("ziomek.server._stt_engine", None):
                    with patch("ziomek.server._audio_player", None):
                        with patch("ziomek.server._tts_model", None):
                            with patch("ziomek.server.get_uptime", return_value=123.45):
                                result = asyncio.run(mcp_tools_module._handle_status())
                                assert result.is_error is False
                                data = json.loads(result.content[0].text)
                                assert "tts_ready" in data
                                assert "stt_state" in data
                                assert "uptime_seconds" in data

    def test_call_speak_tool_no_model(self):
        """Speak returns error when TTS model not loaded."""
        mock_model = MagicMock()
        mock_model.ready = False
        with patch("ziomek.server._tts_model", mock_model):
            with patch("ziomek.server._settings", None):
                result = asyncio.run(mcp_tools_module._handle_speak({"text": "hello"}))
                assert result.is_error is True
                data = json.loads(result.content[0].text)
                assert "error" in data

    def test_call_transcribe_tool_no_engine(self):
        """Transcribe returns error when STT engine not initialized."""
        with patch("ziomek.server._stt_engine", None):
            result = asyncio.run(mcp_tools_module._handle_transcribe({"audio_b64": "dGVzdA=="}))
            assert result.is_error is True
            data = json.loads(result.content[0].text)
            assert "error" in data

    def test_call_transcribe_tool_invalid_base64(self):
        """Transcribe returns error for invalid base64."""
        with patch("ziomek.server._stt_engine", None):
            result = asyncio.run(mcp_tools_module._handle_transcribe({"audio_b64": "not-valid-base64!!!"}))
            assert result.is_error is True
            data = json.loads(result.content[0].text)
            assert "error" in data

    def test_call_set_expression_tool_no_machine(self):
        """Set expression returns error when state machine not initialized."""
        with patch("ziomek.server._state_machine", None):
            result = asyncio.run(mcp_tools_module._handle_set_expression({"expression": "happy"}))
            assert result.is_error is True
            data = json.loads(result.content[0].text)
            assert "error" in data

    def test_call_get_expression_tool_no_machine(self):
        """Get expression returns error when state machine not initialized."""
        with patch("ziomek.server._state_machine", None):
            result = asyncio.run(mcp_tools_module._handle_get_expression())
            assert result.is_error is True
            data = json.loads(result.content[0].text)
            assert "error" in data
