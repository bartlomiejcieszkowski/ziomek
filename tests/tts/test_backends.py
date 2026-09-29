"""Tests for backend protocol and individual backends."""
import inspect
from unittest.mock import patch

import numpy as np

from ziomek.tts.backends import BackendRegistry
from ziomek.tts.backends.noop import NoopBackend
from ziomek.tts.backends.sounddevice import SounddeviceBackend


def test_backend_protocol_has_required_methods():
    """IBackend ABC requires play, mix_play, list_devices, and supports_mixing."""
    from ziomek.tts.backends.base import IBackend

    required = {"play", "mix_play", "list_devices", "supports_mixing"}
    abstract = {name for name, method in inspect.getmembers(IBackend)
                if getattr(method, "__isabstractmethod__", False)}
    assert required == abstract


def test_noop_backend_play_calls_nothing():
    backend = NoopBackend()
    backend.play(b"data", 24000)  # should not raise


def test_noop_backend_mix_play_calls_nothing():
    backend = NoopBackend()
    backend.mix_play(b"data", 24000)  # should not raise


def test_noop_backend_list_devices_returns_empty():
    backend = NoopBackend()
    assert backend.list_devices() == []


def test_noop_backend_supports_mixing():
    backend = NoopBackend()
    assert backend.supports_mixing is True


def test_sounddevice_backend_supports_mixing():
    backend = SounddeviceBackend()
    assert backend.supports_mixing is True


def test_sounddevice_backend_list_devices():
    backend = SounddeviceBackend()
    devices = backend.list_devices()
    assert isinstance(devices, list)


def test_sounddevice_backend_play_handles_data():
    backend = SounddeviceBackend()
    wav_data = np.zeros(2400, dtype=np.float32).tobytes()
    with patch("soundfile.read", return_value=(np.zeros(2400, dtype=np.float32), 24000)):
        with patch("sounddevice.play"):
            with patch("sounddevice.stop"):
                backend.play(wav_data, 24000)


def test_sounddevice_backend_mix_play_handles_data():
    backend = SounddeviceBackend()
    wav_data = np.zeros(2400, dtype=np.float32).tobytes()
    with patch("soundfile.read", return_value=(np.zeros(2400, dtype=np.float32), 24000)):
        with patch("sounddevice.play"):
            backend.mix_play(wav_data, 24000)


def test_registry_get_noop():
    reg = BackendRegistry()
    backend = reg.get("noop")
    assert backend is not None
    assert backend.supports_mixing is True


def test_registry_get_sounddevice():
    reg = BackendRegistry()
    backend = reg.get("sounddevice")
    assert backend is not None
    assert backend.supports_mixing is True


def test_registry_get_unknown_raises():
    reg = BackendRegistry()
    try:
        reg.get("nonexistent")
        assert False, "Should have raised"
    except ValueError:
        pass


def test_registry_list_backends_includes_registered():
    reg = BackendRegistry()
    backends = reg.list_backends()
    assert "noop" in backends
    assert "sounddevice" in backends
