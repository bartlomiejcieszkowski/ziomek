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

from tests.avatar.morda_helpers import make_bundle, make_folder, sheet_definition
from ziomek import debug_report
from ziomek.avatar.skins import SkinRegistry
from ziomek.mcp import set_dev_mode
from ziomek.mcp import tools as mcp_tools_module
from ziomek.roster import Roster


@pytest.fixture(autouse=True)
def no_report_yet():
    """The report is kept for the life of the server, so a test starts from nothing."""
    debug_report.clear()
    set_dev_mode(False)


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
        """TOOLS list answers the tools for reading what a call holds, not only for acting in it."""
        tool_names = [t.name for t in mcp_tools_module.TOOLS]
        assert "say" in tool_names
        assert "play" in tool_names
        assert "write" in tool_names
        assert "speak" not in tool_names
        assert "transcribe" in tool_names
        assert "start_listening" in tool_names
        assert "get_transcription" in tool_names
        assert "stop_listening" in tool_names
        assert "set_expression" in tool_names
        assert "get_expression" in tool_names
        assert "join" in tool_names
        assert "hold" in tool_names
        assert "leave" in tool_names
        assert "status" in tool_names
        assert "read_participants" in tool_names
        assert "read_participant" in tool_names
        assert "read_available_skins" in tool_names
        assert len(tool_names) == 17

    def test_tools_have_correct_schema(self):
        """Each tool has name, description, and inputSchema."""
        for tool in mcp_tools_module.TOOLS:
            assert isinstance(tool.name, str) and len(tool.name) > 0
            assert isinstance(tool.description, str) and len(tool.description) > 0
            assert isinstance(tool.input_schema, dict)
            assert tool.input_schema.get("type") == "object"

    def test_a_debug_tool_is_not_listed_when_the_server_runs_without_dev_mode(self):
        """A tool that cannot answer should not appear in a client's tool list."""
        result = asyncio.run(mcp_tools_module._on_list_tools(None, None))
        assert "debug_get_render_state" not in [t.name for t in result.tools]

    def test_a_debug_tool_is_listed_when_the_server_runs_with_dev_mode(self):
        set_dev_mode(True)
        result = asyncio.run(mcp_tools_module._on_list_tools(None, None))
        assert "debug_get_render_state" in [t.name for t in result.tools]

    def test_calling_a_debug_tool_without_dev_mode_is_refused(self):
        result = asyncio.run(
            mcp_tools_module._on_call_tool(None, CallToolRequestParams(name="debug_get_render_state", arguments={}))
        )
        assert result.is_error is True
        assert "dev" in result.content[0].text

    def test_the_debug_tool_answers_the_last_report(self):
        set_dev_mode(True)
        debug_report.store({"room": {"width": 1580, "height": 1064}, "frames": 10})
        result = asyncio.run(
            mcp_tools_module._on_call_tool(None, CallToolRequestParams(name="debug_get_render_state", arguments={}))
        )
        assert result.is_error is False
        data = json.loads(result.content[0].text)
        assert data["frames"] == 10

    def test_nothing_is_answered_before_a_page_reports(self):
        set_dev_mode(True)
        result = asyncio.run(
            mcp_tools_module._on_call_tool(None, CallToolRequestParams(name="debug_get_render_state", arguments={}))
        )
        assert result.is_error is True
        assert "nothing has reported" in result.content[0].text


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

    def test_calling_a_tool_through_the_server_reaches_the_handler_with_arguments(self):
        """The path a client uses passes arguments, so a handler that takes none fails there.

        Calling a handler directly cannot show this, which is why the tests for these tools
        passed while a running server refused them.
        """

        class FakeSession:
            def get_result(self):
                return {}

            def stop(self):
                return True

        with patch("ziomek.mcp.tools._get_listening_session", return_value=FakeSession()):
            with patch("ziomek.server._state_machine", None):
                with patch("ziomek.server._stt_engine", None):
                    with patch("ziomek.server._audio_player", None):
                        with patch("ziomek.server._tts_model", None):
                            with patch("ziomek.server.get_uptime", return_value=123.45):
                                for name in ("status", "get_transcription", "stop_listening"):
                                    result = asyncio.run(
                                        mcp_tools_module._on_call_tool(
                                            None, CallToolRequestParams(name=name, arguments={})
                                        )
                                    )
                                    assert result.is_error is False, name

    def test_call_play_tool_no_model(self):
        """Play returns error when TTS model not loaded."""
        mock_model = MagicMock()
        mock_model.ready = False
        with patch("ziomek.server._tts_model", mock_model):
            with patch("ziomek.server._settings", None):
                result = asyncio.run(mcp_tools_module._handle_play({"text": "hello"}))
                assert result.is_error is True
                data = json.loads(result.content[0].text)
                assert "error" in data


class TestMcpPlayDoesNotTouchTheRoster:
    """Play speaks by voice without taking part in a call, so it records nothing."""

    def test_play_records_no_line(self):
        mock_model = MagicMock()
        mock_model.ready = True
        roster = MagicMock()
        roster.participants = []
        with patch("ziomek.server._tts_model", mock_model):
            with patch("ziomek.server._settings", None):
                with patch.object(mcp_tools_module, "get_roster", return_value=roster):
                    with patch("ziomek.tts.generate.generate_wav") as generate:
                        generate.return_value = (base64.b64encode(b"audio").decode(), 0.5, 16000)
                        with patch("ziomek.server._voice_cache", object()):
                            with patch("ziomek.server._audio_player", None):
                                result = asyncio.run(
                                    mcp_tools_module._handle_play({"text": "hello", "voice": "cosette"})
                                )
        assert json.loads(result.content[0].text)["voice"] == "cosette"
        roster.record.assert_not_called()

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


def _answer(tool: str, arguments: dict, roster=None, registry=None):
    """Answer a tool as the server would, with the call and the registry set for one test."""
    with (
        patch.object(mcp_tools_module, "get_roster", return_value=roster),
        patch.object(mcp_tools_module, "get_registry", return_value=registry),
    ):
        return asyncio.run(mcp_tools_module._on_call_tool(None, CallToolRequestParams(name=tool, arguments=arguments)))


def _text(result) -> str:
    return result.content[0].text


class TestReadingParticipants:
    """A client that joined cannot see the call, so reading it answers who is in it.

    A tool for the list and a tool for one name are separate because an empty call is a normal
    answer for the list while a name that is not in it is an error for a single read.
    """

    @pytest.fixture(autouse=True)
    def no_view_shows_one(self):
        """The view that shows one participant is module state, so a test must not inherit it."""
        from ziomek.api import avatar_ws

        avatar_ws._shown = None
        yield
        avatar_ws._shown = None

    def call(self, tool: str, arguments: dict, roster: Roster):
        return _answer(tool, arguments, roster=roster)

    def test_the_list_states_what_each_participant_is(self):
        roster = Roster()
        self.call("join", {"name": "first", "voice": "cosette"}, roster)
        self.call("join", {"name": "second", "voice": "alba"}, roster)

        result = self.call("read_participants", {}, roster)
        assert result.is_error is False
        assert json.loads(result.content[0].text) == [
            {
                "name": "first",
                "state": "active",
                "voice": "cosette",
                "skin": roster.participants[0].skin,
                "persona": None,
            },
            {
                "name": "second",
                "state": "active",
                "voice": "alba",
                "skin": roster.participants[1].skin,
                "persona": None,
            },
        ]

    def test_a_call_with_no_one_in_it_answers_an_empty_list(self):
        result = self.call("read_participants", {}, Roster())
        assert result.is_error is False
        assert json.loads(result.content[0].text) == []

    def test_read_participant_answers_the_same_fields_as_the_list(self):
        roster = Roster()
        self.call("join", {"name": "first", "voice": "cosette", "persona": "calm"}, roster)

        single = json.loads(self.call("read_participant", {"name": "first"}, roster).content[0].text)
        listed = json.loads(self.call("read_participants", {}, roster).content[0].text)
        assert single == listed[0]
        assert single["persona"] == "calm"

    def test_a_name_that_is_not_in_the_call_answers_that_error(self):
        result = self.call("read_participant", {"name": "not-in-the-call"}, Roster())
        assert result.is_error is True
        assert "Unknown participant" in result.content[0].text

    def test_a_held_participant_can_be_put_back_counting_again(self):
        roster = Roster()
        self.call("join", {"name": "first", "voice": "cosette"}, roster)
        self.call("hold", {"name": "first"}, roster)

        result = self.call("resume", {"name": "first"}, roster)

        assert result.is_error is False
        assert json.loads(result.content[0].text) == {
            "name": "first",
            "state": "active",
            "quiet_for": roster.quiet_for,
        }

    def test_join_states_the_face_it_drew(self):
        roster = Roster()
        result = self.call("join", {"name": "first", "voice": "cosette"}, roster)
        assert json.loads(result.content[0].text)["skin"] == roster.participants[0].skin

    def test_join_records_the_persona_it_was_given(self):
        roster = Roster()
        result = self.call("join", {"name": "first", "voice": "cosette", "persona": "calm"}, roster)
        assert json.loads(result.content[0].text)["persona"] == "calm"
        assert roster.participants[0].persona == "calm"

    def test_a_participant_that_was_given_no_persona_answers_none(self):
        result = self.call("join", {"name": "first", "voice": "cosette"}, Roster())
        assert json.loads(result.content[0].text)["persona"] is None

    def test_the_persona_argument_is_described_as_recorded(self):
        """Nothing reads a persona yet, so the tool must not say that it steers anything."""
        description = next(t for t in mcp_tools_module.TOOLS if t.name == "join").input_schema["properties"]["persona"][
            "description"
        ]
        assert "recorded" in description
        assert "behav" not in description


class TestJoiningWithAFace:
    """A name is refused when no such face was built, because a face that cannot be drawn
    would show as an empty box instead of being stated at the moment of joining.
    """

    def test_an_unknown_face_is_refused_and_no_one_is_joined(self, tmp_path):
        roster = Roster(skins=["cosette"])
        registry = SkinRegistry(skins_dir=tmp_path / "nothing", default_dir=tmp_path / "nothing")
        with (
            patch.object(mcp_tools_module, "get_roster", return_value=roster),
            patch.object(mcp_tools_module, "get_registry", return_value=registry),
        ):
            result = _answer("join", {"name": "first", "skin": "not-a-skin"}, roster, registry)
        assert result.is_error is True
        assert "Unknown skin" in _text(result)
        assert roster.participants == []

    def test_a_face_given_at_join_is_the_one_that_participant_keeps(self, tmp_path):
        registry = SkinRegistry(
            skins_dir=make_folder(tmp_path / "cosette", sheet_definition()), default_dir=tmp_path / "empty"
        )
        roster = Roster()
        first = json.loads(_text(_answer("join", {"name": "first", "skin": "cosette"}, roster, registry)))
        second = json.loads(_text(_answer("join", {"name": "second"}, roster, registry)))
        assert first["skin"] == "cosette"
        assert second["skin"] == "single-frame"

    def test_the_list_of_faces_answers_what_the_registry_built(self, tmp_path):
        bundle = make_bundle(
            tmp_path / "bundle",
            {
                "morda.json": sheet_definition(),
                "blue.morda.json": sheet_definition(name="blue", expressions={"neutral": "rest"}),
            },
        )
        registry = SkinRegistry(skins_dir=bundle, default_dir=tmp_path / "empty")
        result = _answer("read_available_skins", {}, None, registry)
        assert json.loads(_text(result))["skins"] == ["cosette", "blue"]

    def test_nothing_is_answered_before_a_registry_was_built(self):
        result = _answer("read_available_skins", {}, None, None)
        assert result.is_error is True
        assert "no skin registry was built" in _text(result)


class TestAnExpressionIsAppliedToTheNameItWasAskedAbout:
    """A name stated by a call has to be the name it acts on.

    A name that is not in the call is refused, because an answer that names nothing is not an
    answer about the thing the caller asked for. A call that states no name keeps using the global
    avatar, since it claims no one.
    """

    def test_an_expression_cannot_be_set_for_a_name_that_is_not_in_the_call(self):
        machine = MagicMock()
        machine.setExpression.return_value = True

        with patch("ziomek.server._state_machine", machine):
            result = _answer("set_expression", {"name": "not-in-the-call", "expression": "happy"}, Roster())

        assert result.is_error is True
        assert "Unknown participant: not-in-the-call" in _text(result)
        machine.setExpression.assert_not_called()

    def test_an_expression_cannot_be_read_for_a_name_that_is_not_in_the_call(self):
        machine = MagicMock()

        with patch("ziomek.server._state_machine", machine):
            result = _answer("get_expression", {"name": "not-in-the-call"}, Roster())

        assert result.is_error is True
        assert "Unknown participant: not-in-the-call" in _text(result)
        machine.tick.assert_not_called()

    def test_a_wrong_name_is_refused_even_when_no_machine_was_made(self):
        """The name the caller stated is their mistake, so it is answered before anything else."""
        result = _answer("set_expression", {"name": "not-in-the-call", "expression": "happy"}, Roster())

        assert result.is_error is True
        assert "Unknown participant" in _text(result)

    def test_a_call_that_names_no_one_still_uses_the_global_avatar(self):
        machine = MagicMock()
        machine.setExpression.return_value = True

        with patch("ziomek.server._state_machine", machine):
            result = _answer("set_expression", {"expression": "happy"}, Roster())

        assert result.is_error is False
        assert json.loads(_text(result))["name"] is None
        machine.setExpression.assert_called_once_with("happy", None)
