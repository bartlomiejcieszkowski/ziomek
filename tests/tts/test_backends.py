"""Tests for backend protocol and individual backends."""
import inspect


def test_backend_protocol_has_required_methods():
    """IBackend ABC requires play, mix_play, list_devices, and supports_mixing."""
    from ziomek.tts.backends.base import IBackend

    required = {"play", "mix_play", "list_devices", "supports_mixing"}
    abstract = {name for name, method in inspect.getmembers(IBackend)
                if getattr(method, "__isabstractmethod__", False)}
    assert required == abstract
