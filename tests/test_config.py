"""Tests for ziomek config loading and precedence."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from ziomek.config import Settings


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
