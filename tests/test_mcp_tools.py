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
from mcp.server.lowlevel import Server
from mcp.types import CallToolRequest, CallToolRequestParams, ListToolsRequest

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

    def test_list_tools_returns_all_tools(self):
        """List tools returns all 8 tools."""
        server = Server("test")
        mcp_tools_module.register_tools(server)

        result = asyncio.run(
            server.on_list_tools(None, ListToolsRequest())
        )

        tool_names = [t.name for t in result.tools]
        assert "speak" in tool_names
        assert "transcribe" in tool_names
        assert "start_listening" in tool_names
        assert "get_transcription" in tool_names
        assert "stop_listening" in tool_names
        assert "set_expression" in tool_names
        assert "get_expression" in tool_names
        assert "status" in tool_names
        assert len(result.tools) == 8


class TestMcpSpeakTool:
    """Test the speak MCP tool."""

    def test_speak_calls_generate_wav_and_play(self):
        """Speak calls generate_wav and audio_player.play."""
        mock_model = MagicMock()
        mock_model.ready = True
        mock_cache = MagicMock()
        mock_player = MagicMock()
        mock_settings = MagicMock()

        with patch("ziomek.server._tts_model", mock_model), \
             patch("ziomek.server._voice_cache", mock_cache), \
             patch("ziomek.server._audio_player", mock_player), \
             patch("ziomek.server._settings", mock_settings), \
             patch("ziomek.tts.generate.generate_wav") as mock_gen:

            mock_gen.return_value = (base64.b64encode(b"fake_wav").decode(), 0.5, 16000)

            server = Server("test")
            mcp_tools_module.register_tools(server)

            params = CallToolRequest(
                method="tools/call",
                params=CallToolRequestParams(
                    name="speak",
                    arguments={"text": "hello", "voice": "cosette"},
                ),
            )
            result = asyncio.run(
                server.on_call_tool(None, params.params)
            )

            data = json.loads(result.content[0].text)
            assert data["status"] == "playing"
            assert data["voice"] == "cosette"
            mock_gen.assert_called_once()
            mock_player.play.assert_called_once()

    def test_speak_model_not_ready(self):
        """Speak returns error when TTS model is not loaded."""
        mock_model = MagicMock()
        mock_model.ready = False

        with patch("ziomek.server._tts_model", mock_model), \
             patch("ziomek.server._settings", None):

            server = Server("test")
            mcp_tools_module.register_tools(server)

            params = CallToolRequest(
                method="tools/call",
                params=CallToolRequestParams(
                    name="speak",
                    arguments={"text": "hello"},
                ),
            )
            result = asyncio.run(
                server.on_call_tool(None, params.params)
            )

            data = json.loads(result.content[0].text)
            assert "error" in data


class TestMcpTranscribeTool:
    """Test the transcribe MCP tool."""

    def test_transcribe_calls_stt_engine(self):
        """Transcribe calls STTEngine.transcribe_chunk."""
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "transcribed text"
        mock_result.is_final = True
        mock_engine.transcribe_chunk.return_value = mock_result

        with patch("ziomek.server._stt_engine", mock_engine):

            server = Server("test")
            mcp_tools_module.register_tools(server)

            wav_bytes = _make_wav_bytes()
            audio_b64 = base64.b64encode(wav_bytes).decode()

            params = CallToolRequest(
                method="tools/call",
                params=CallToolRequestParams(
                    name="transcribe",
                    arguments={"audio_b64": audio_b64},
                ),
            )
            result = asyncio.run(
                server.on_call_tool(None, params.params)
            )

            data = json.loads(result.content[0].text)
            assert data["text"] == "transcribed text"
            assert data["is_final"] is True
            mock_engine.transcribe_chunk.assert_called_once()

    def test_transcribe_invalid_base64(self):
        """Transcribe returns error for invalid base64."""
        mock_engine = MagicMock()

        with patch("ziomek.server._stt_engine", mock_engine):

            server = Server("test")
            mcp_tools_module.register_tools(server)

            params = CallToolRequest(
                method="tools/call",
                params=CallToolRequestParams(
                    name="transcribe",
                    arguments={"audio_b64": "not_valid_base64!!!"},
                ),
            )
            result = asyncio.run(
                server.on_call_tool(None, params.params)
            )

            data = json.loads(result.content[0].text)
            assert "error" in data

    def test_transcribe_engine_not_initialized(self):
        """Transcribe returns error when STT engine not initialized."""
        with patch("ziomek.server._stt_engine", None):

            server = Server("test")
            mcp_tools_module.register_tools(server)

            params = CallToolRequest(
                method="tools/call",
                params=CallToolRequestParams(
                    name="transcribe",
                    arguments={"audio_b64": "dGVzdA=="},
                ),
            )
            result = asyncio.run(
                server.on_call_tool(None, params.params)
            )

            data = json.loads(result.content[0].text)
            assert "error" in data


class TestMcpAvatarTools:
    """Test avatar MCP tools."""

    def test_set_expression_calls_state_machine(self):
        """Set expression calls state machine."""
        mock_sm = MagicMock()
        mock_sm.setExpression.return_value = True

        with patch("ziomek.server._state_machine", mock_sm):

            server = Server("test")
            mcp_tools_module.register_tools(server)

            params = CallToolRequest(
                method="tools/call",
                params=CallToolRequestParams(
                    name="set_expression",
                    arguments={"expression": "happy"},
                ),
            )
            result = asyncio.run(
                server.on_call_tool(None, params.params)
            )

            data = json.loads(result.content[0].text)
            assert data["ok"] is True
            assert data["expression"] == "happy"
            mock_sm.setExpression.assert_called_once_with("happy", None)

    def test_get_expression_returns_state(self):
        """Get expression returns current state."""
        mock_sm = MagicMock()
        mock_state = MagicMock()
        mock_state.expressionName = "happy"
        mock_state.cycleIndex = 0
        mock_state.message = ""
        mock_state.messageExpiry = 0
        mock_sm.tick.return_value = mock_state

        with patch("ziomek.server._state_machine", mock_sm):

            server = Server("test")
            mcp_tools_module.register_tools(server)

            params = CallToolRequest(
                method="tools/call",
                params=CallToolRequestParams(
                    name="get_expression",
                    arguments={},
                ),
            )
            result = asyncio.run(
                server.on_call_tool(None, params.params)
            )

            data = json.loads(result.content[0].text)
            assert data["expression"] == "happy"
            assert data["cycleIndex"] == 0
            mock_sm.tick.assert_called_once_with(16)


class TestMcpStatusTool:
    """Test the status MCP tool."""

    def test_status_returns_combined_info(self):
        """Status returns TTS, STT, and audio info."""
        mock_model = MagicMock()
        mock_model.ready = True

        mock_engine = MagicMock()
        mock_engine.stats.state.value = "idle"
        mock_engine.stats.engine_name = "faster_whisper"
        mock_engine.stats.model_name = "tiny"

        mock_player = MagicMock()
        mock_player.backend_name = "sounddevice"
        mock_player.device_name = "default"

        with patch("ziomek.server._tts_model", mock_model), \
             patch("ziomek.server._stt_engine", mock_engine), \
             patch("ziomek.server._audio_player", mock_player), \
             patch("ziomek.server.get_uptime", return_value=123.45):

            server = Server("test")
            mcp_tools_module.register_tools(server)

            params = CallToolRequest(
                method="tools/call",
                params=CallToolRequestParams(
                    name="status",
                    arguments={},
                ),
            )
            result = asyncio.run(
                server.on_call_tool(None, params.params)
            )

            data = json.loads(result.content[0].text)
            assert data["tts_ready"] is True
            assert data["stt_state"] == "idle"
            assert data["stt_engine"] == "faster_whisper"
            assert data["audio_backend"] == "sounddevice"
            assert data["uptime_seconds"] == 123.5
