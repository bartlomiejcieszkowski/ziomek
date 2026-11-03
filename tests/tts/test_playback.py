import threading
from unittest.mock import MagicMock, patch

import pytest

from ziomek.tts.playback import AudioPlayer


class _HoldingBackend:
    """A backend that holds until the device has taken the samples."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.released = threading.Event()
        self.finished = threading.Event()
        self.threads: list[str] = []

    def play(self, data: bytes, sr: int) -> None:
        self.threads.append(threading.current_thread().name)
        self.entered.set()
        if self.released.wait(2):
            self.finished.set()

    def mix_play(self, data: bytes, sr: int) -> None:
        pass

    def list_devices(self) -> list[dict]:
        return []

    @property
    def supports_mixing(self) -> bool:
        return False


def _player_with(backend) -> AudioPlayer:
    player = AudioPlayer(backend_name="noop")
    player._backend = backend
    return player


def test_play_delegates_to_backend():
    """Verify play() reaches the backend through the worker."""
    player = AudioPlayer(backend_name="noop")
    with patch.object(player._backend, "play") as mock_play:
        player.play(b"data", 24000)
        player._worker.join()
        mock_play.assert_called_once_with(b"data", 24000)


def test_the_call_returns_while_the_device_is_still_taking_samples():
    """The caller answers right away; the wait for the device happens in the worker."""
    backend = _HoldingBackend()
    player = _player_with(backend)

    player.play(b"data", 24000)

    assert backend.entered.wait(1)
    assert player._worker.is_alive(), "the call waited for the device instead of answering"
    assert threading.current_thread().name not in backend.threads
    backend.released.set()
    player._worker.join()
    assert backend.finished.is_set()


def test_the_worker_finishes_only_after_the_device_has_taken_the_samples():
    """The worker waits for the device, so a sound is not cut short."""
    backend = _HoldingBackend()
    player = _player_with(backend)

    player.play(b"data", 24000)
    backend.entered.wait(1)
    assert not backend.finished.is_set(), "the worker finished before the device took the samples"
    backend.released.set()
    player._worker.join()
    assert backend.finished.is_set()


def test_mix_play_delegates_to_backend():
    """Verify mix_play() delegates to the backend."""
    player = AudioPlayer(backend_name="noop")
    with patch.object(player._backend, "mix_play") as mock_mix:
        player.mix_play(b"data", 24000)
        mock_mix.assert_called_once_with(b"data", 24000)


def test_list_devices_delegates():
    """Verify list_devices() delegates to the backend."""
    player = AudioPlayer(backend_name="noop")
    expected = [{"id": 0, "name": "test"}]
    with patch.object(player._backend, "list_devices", return_value=expected):
        result = player.list_devices()
        assert result == expected


def test_supports_mixing_delegates():
    """Verify supports_mixing() delegates to the backend."""
    player = AudioPlayer(backend_name="noop")
    assert player.supports_mixing() is True
