"""Tests for ziomek config loading and precedence."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from ziomek.config import Settings
from ziomek.tts.backends.devices import resolve_device


def test_settings_default_audio_backend():
    s = Settings()
    assert s.audio_backend == "sounddevice"
    assert s.audio_device is None


def test_settings_custom_audio_backend():
    s = Settings(audio_backend="noop", audio_device=3)
    assert s.audio_backend == "noop"
    assert s.audio_device == 3


def test_settings_load_missing_file_falls_through():
    loaded = Settings.load("/nonexistent/path.yaml")
    assert loaded.audio_backend == "sounddevice"
    assert loaded.audio_device is None


def test_settings_load_from_config_file():
    content = "audio_backend: noop\naudio_device: 5\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        loaded = Settings.load(path)
        assert loaded.audio_backend == "noop"
        assert loaded.audio_device == 5
    finally:
        os.unlink(path)


def test_compose_env_overrides_file():
    content = "audio_backend: noop\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        with patch.dict(os.environ, {"ZIOMEK_AUDIO_BACKEND": "sounddevice"}):
            s = Settings.compose(
                file_path=path,
                env_backend="sounddevice",
            )
            assert s.audio_backend == "sounddevice"
    finally:
        os.unlink(path)


def test_compose_cli_overrides_env():
    content = "audio_backend: noop\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        with patch.dict(os.environ, {"ZIOMEK_AUDIO_BACKEND": "sounddevice"}):
            s = Settings.compose(
                file_path=path,
                env_backend="sounddevice",
                cli_backend="pygame",
            )
            assert s.audio_backend == "pygame"
    finally:
        os.unlink(path)


def test_compose_file_overrides_defaults():
    content = "audio_backend: noop\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        s = Settings.compose(file_path=path)
        assert s.audio_backend == "noop"
    finally:
        os.unlink(path)


def test_compose_defaults_when_no_file():
    s = Settings.compose(file_path=None)
    assert s.audio_backend == "sounddevice"


def test_resolve_device_none_returns_none():
    backend_mock = MagicMock()
    assert resolve_device(None, backend_mock) is None


def test_resolve_device_default_returns_none():
    backend_mock = MagicMock()
    assert resolve_device("default", backend_mock) is None


def test_resolve_device_index_returns_index():
    backend_mock = MagicMock()
    assert resolve_device(3, backend_mock) == 3


def test_resolve_device_name_matches():
    backend_mock = MagicMock()
    backend_mock.list_devices.return_value = [
        {"id": 0, "name": "default"},
        {"id": 1, "name": "HDMI"},
        {"id": 2, "name": "Built-in"},
    ]
    result = resolve_device("hdmi", backend_mock)
    assert result == 1


def test_resolve_device_name_no_match_raises():
    backend_mock = MagicMock()
    backend_mock.list_devices.return_value = [
        {"id": 0, "name": "default"},
    ]
    try:
        resolve_device("nonexistent", backend_mock)
        assert False, "Should have raised"
    except ValueError as e:
        assert "nonexistent" in str(e)
        assert "default" in str(e)


def test_server_with_noop_backend():
    """Server creates app with noop audio backend."""
    from ziomek import server
    from ziomek.config import Settings

    settings = Settings.compose(
        cli_backend="noop",
        cli_device=None,
    )
    app = server.create_app(settings)
    client = TestClient(app)
    resp = client.get("/status")
    assert resp.status_code == 200
    # Verify the audio player was created with the noop backend
    assert server._audio_player is not None
    assert server._audio_player.supports_mixing() is True


def test_settings_has_no_gamepad_and_no_no_vscode():
    """The split-era no_vscode flag is gone; gamepad polling is gated by no_gamepad."""
    s = Settings()
    assert s.no_gamepad is False
    assert "no_vscode" not in Settings.model_fields


def test_no_gamepad_from_config_file():
    """A config file can enable the gate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "ziomek_config.yaml")
        with open(path, "w") as f:
            f.write("no_gamepad: true\n")
        s = Settings.load(path)
        assert s.no_gamepad is True


def test_no_gamepad_cli_beats_config_file():
    """Precedence: CLI > config file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "ziomek_config.yaml")
        with open(path, "w") as f:
            f.write("no_gamepad: false\n")
        s = Settings.compose(file_path=path, no_gamepad=True)
        assert s.no_gamepad is True


def test_settings_has_no_stt_flag():
    """STT is gated by the no_stt flag, not by any other flag."""
    s = Settings()
    assert s.no_stt is False


def test_no_stt_from_config_file():
    """A config file can disable STT."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "ziomek_config.yaml")
        with open(path, "w") as f:
            f.write("no_stt: true\n")
        s = Settings.load(path)
        assert s.no_stt is True


def test_no_stt_cli_beats_config_file():
    """Precedence: CLI > config file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "ziomek_config.yaml")
        with open(path, "w") as f:
            f.write("no_stt: false\n")
        s = Settings.compose(file_path=path, no_stt=True)
        assert s.no_stt is True


def test_the_tools_are_not_turned_off_when_nothing_is_stated():
    """MCP is on by default, so a run that states nothing serves it."""
    assert Settings().no_mcp is False


def test_the_transport_taken_when_nothing_is_stated_is_http():
    """The transport a run uses when nothing is stated is the one it serves the tools over."""
    assert Settings().mcp_transport == "http"


def test_a_transport_read_from_the_config_file_is_used_when_nothing_is_stated_on_the_command_line():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "ziomek_config.yaml")
        with open(path, "w") as f:
            f.write("mcp_transport: stdio\n")
        assert Settings.compose(file_path=path).mcp_transport == "stdio"


def test_a_config_file_can_turn_the_tools_off():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "ziomek_config.yaml")
        with open(path, "w") as f:
            f.write("no_mcp: true\n")
        assert Settings.load(path).no_mcp is True


def test_turning_the_tools_off_on_the_command_line_beats_the_config_file():
    """Precedence: CLI > config file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "ziomek_config.yaml")
        with open(path, "w") as f:
            f.write("no_mcp: false\n")
        assert Settings.compose(file_path=path, no_mcp=True).no_mcp is True


def test_scaffold_config_documents_the_tools_and_their_default_transport():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "ziomek_server_config.yaml")
        Settings.scaffold_config(path)
        with open(path) as f:
            content = f.read()
        assert "no_mcp" in content
        assert "http" in content


def test_scaffold_config_creates_file():
    """Settings.scaffold_config creates a default YAML config file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "ziomek_server_config.yaml")
        result = Settings.scaffold_config(path)
        assert os.path.isfile(path)
        assert str(result) == os.path.abspath(path)
        with open(path) as f:
            content = f.read()
        assert "audio_backend" in content
        assert "sounddevice" in content
        assert "audio_device" in content
        assert "no_gamepad" in content
        assert "no_stt" in content
        assert "no_vscode" not in content


def test_e2e_noop_backend_full_chain():
    """From Settings.compose → AudioPlayer → backend play call."""
    from unittest.mock import patch

    from ziomek.config import Settings

    s = Settings.compose(cli_backend="noop", cli_device=None)
    from ziomek.tts.playback import AudioPlayer

    player = AudioPlayer(backend_name=s.audio_backend)
    assert player.supports_mixing() is True

    with patch.object(player._backend, "play") as mock_play:
        player.play(b"data", 24000)
        mock_play.assert_called_once_with(b"data", 24000)

    with patch.object(player._backend, "mix_play") as mock_mix:
        player.mix_play(b"data", 24000)
        mock_mix.assert_called_once_with(b"data", 24000)


def test_host_default():
    """Default host should be localhost."""
    s = Settings()
    assert s.host == "localhost"


def test_host_cli_precedence():
    """CLI host should override defaults."""
    s = Settings.compose(cli_host="0.0.0.0")
    assert s.host == "0.0.0.0"


def test_host_env_precedence():
    """Env host should override file/host defaults but be overridden by CLI."""
    s = Settings.compose(env_host="127.0.0.1", cli_host=None)
    assert s.host == "127.0.0.1"


def test_host_cli_overrides_env():
    """CLI host should override env host."""
    s = Settings.compose(env_host="127.0.0.1", cli_host="0.0.0.0")
    assert s.host == "0.0.0.0"


def test_host_kwarg_takes_precedence():
    """Host kwarg should override both CLI and env."""
    s = Settings.compose(env_host="127.0.0.1", cli_host="0.0.0.0", host="192.168.1.1")
    assert s.host == "192.168.1.1"


def test_roster_pool_defaults_to_an_empty_list():
    s = Settings()
    assert s.roster_pool == []
    assert s.roster_quiet_for > 0


def test_roster_settings_load_from_config_file():
    content = "roster_pool:\n  - [John A., alice]\n  - [Mary S., bob]\nroster_quiet_for: 3000\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        loaded = Settings.load(path)
        # An entry that names no skin is read as an empty third part.
        assert loaded.roster_pool == [("John A.", "alice", ""), ("Mary S.", "bob", "")]
        assert loaded.roster_quiet_for == 3000
    finally:
        os.unlink(path)


def test_a_pool_entry_that_names_a_skin_is_read_as_that_skin():
    content = """roster_pool:
  - [cosette, alice, single-frame]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        loaded = Settings.load(path)
        assert loaded.roster_pool == [("cosette", "alice", "single-frame")]
    finally:
        os.unlink(path)


def test_roster_words_are_read_from_config():
    s = Settings()
    assert s.roster_words == []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("roster_words: [compiling, reading]\n")
        path = f.name
    try:
        loaded = Settings.load(path)
        assert loaded.roster_words == ["compiling", "reading"]
    finally:
        os.unlink(path)


def test_scaffold_config_documents_the_words():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        path = f.name
    try:
        content = Settings.scaffold_config(path).read_text()
        assert "# roster_words:" in content
        # The pool example uses single names, not names with a second part.
        assert "[John, alice, single-frame]" in content
    finally:
        os.unlink(path)


def test_scaffold_config_documents_the_roster_settings():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        path = f.name
    try:
        result = Settings.scaffold_config(path)
        content = result.read_text()
        assert "# roster_pool:" in content
        assert "# roster_quiet_for:" in content
    finally:
        os.unlink(path)


def test_the_check_interval_is_a_configured_knob():
    s = Settings()
    assert s.roster_check_interval == 1.0

    content = "roster_check_interval: 0.5\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        loaded = Settings.load(path)
        assert loaded.roster_check_interval == 0.5
    finally:
        os.unlink(path)


def test_scaffold_config_documents_the_check_interval():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        path = f.name
    try:
        content = Settings.scaffold_config(path).read_text()
        assert "# roster_check_interval:" in content
    finally:
        os.unlink(path)


def test_the_transcript_panel_defaults_to_open():
    assert Settings().roster_transcript_default == "open"


def test_scaffold_config_documents_the_panel_default():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        path = f.name
    try:
        content = Settings.scaffold_config(path).read_text()
        assert "# roster_transcript_default:" in content
    finally:
        os.unlink(path)


def test_a_non_string_panel_default_is_normalized():
    assert Settings(roster_transcript_default=True).roster_transcript_default == "closed"
    assert Settings(roster_transcript_default=5).roster_transcript_default == "closed"


def test_scaffold_config_documents_the_avatar_option():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        path = f.name
    try:
        content = Settings.scaffold_config(path).read_text()
        assert "# roster_avatar:" in content
    finally:
        os.unlink(path)
