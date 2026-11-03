import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from ziomek.tts.playback import AudioPlayer


class _RecordingBackend:
    """A backend that records which path a sound took, and can hold until the device is said to be done."""

    def __init__(self, mixing: bool) -> None:
        self.mixing = mixing
        self.entered = threading.Event()
        self.released = threading.Event()
        self.done = threading.Event()
        self.paths: list[str] = []

    def wait_for_paths(self, count: int, timeout: float = 1.0) -> bool:
        """Wait until this many sounds have been recorded."""
        deadline = time.monotonic() + timeout
        while len(self.paths) < count and time.monotonic() < deadline:
            time.sleep(0.01)
        return len(self.paths) >= count

    def play(self, data: bytes, sr: int) -> None:
        self.paths.append("single")
        self.entered.set()
        if self.released.wait(2):
            self.done.set()

    def mix_play(self, data: bytes, sr: int) -> None:
        self.paths.append("mixed")

    def list_devices(self) -> list[dict]:
        return []

    @property
    def supports_mixing(self) -> bool:
        return self.mixing


def _player_with(backend) -> AudioPlayer:
    player = AudioPlayer(backend_name="noop")
    player._backend = backend
    return player


def _join(player: AudioPlayer) -> None:
    for worker in player._workers:
        worker.join()


def test_play_delegates_to_backend():
    """Verify play() reaches the backend through the worker."""
    player = AudioPlayer(backend_name="noop")
    with patch.object(player._backend, "play") as mock_play:
        player.play(b"data", 24000)
        _join(player)
        mock_play.assert_called_once_with(b"data", 24000)


def test_a_sound_on_a_device_that_is_not_busy_takes_the_single_shot_path():
    """Nothing else is on the device, so the sound is not treated as an overlap."""
    backend = _RecordingBackend(mixing=True)
    player = _player_with(backend)

    player.play(b"data", 24000)
    backend.released.set()
    _join(player)

    assert backend.paths == ["single"]


def test_the_call_returns_while_the_device_is_still_taking_samples():
    """The caller answers right away; the wait for the device happens in the worker."""
    backend = _RecordingBackend(mixing=False)
    player = _player_with(backend)

    player.play(b"data", 24000)

    assert backend.entered.wait(1)
    assert player._workers[-1].is_alive(), "the call waited for the device instead of answering"
    assert not backend.done.is_set()
    backend.released.set()
    _join(player)
    assert backend.done.is_set()


def test_a_second_sound_while_another_is_on_the_device_is_summed_with_it():
    """The player routes the second sound to the mixing path of a backend that can mix."""
    backend = _RecordingBackend(mixing=True)
    player = _player_with(backend)

    player.play(b"first", 24000)
    assert backend.entered.wait(1)
    player.play(b"second", 24000)
    assert backend.wait_for_paths(2), "the second sound never reached the backend"
    assert backend.paths == ["single", "mixed"]
    backend.released.set()
    _join(player)


def test_a_backend_that_cannot_mix_keeps_one_sound_at_a_time():
    """A backend that reports no mixing is not asked to mix, so both sounds take the single path."""
    backend = _RecordingBackend(mixing=False)
    player = _player_with(backend)

    player.play(b"first", 24000)
    assert backend.entered.wait(1)
    player.play(b"second", 24000)
    assert backend.wait_for_paths(2), "the second sound never reached the backend"
    assert backend.paths == ["single", "single"]
    backend.released.set()
    _join(player)


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
