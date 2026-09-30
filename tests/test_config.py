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
