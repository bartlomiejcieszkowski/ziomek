"""Tests for backend protocol and individual backends."""
import inspect

from ziomek.tts.backends.noop import NoopBackend


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
