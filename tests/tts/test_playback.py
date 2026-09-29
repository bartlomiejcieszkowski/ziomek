from unittest.mock import MagicMock, patch

import pytest

from ziomek.tts.playback import AudioPlayer


def test_play_delegates_to_backend():
    """Verify play() delegates to the backend."""
    player = AudioPlayer(backend_name="noop")
    with patch.object(player._backend, "play") as mock_play:
        player.play(b"data", 24000)
        mock_play.assert_called_once_with(b"data", 24000)


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
