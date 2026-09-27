import pytest
import io
import numpy as np
from unittest.mock import MagicMock, patch

from ziomek.tts.playback import AudioPlayer


def test_play_nonblocking():
    """Verify play() calls sounddevice.play with blocking=False."""
    player = AudioPlayer()
    wav_bytes = io.BytesIO(np.array([0.0] * 2400, dtype=np.float32).tobytes()).getvalue()

    with patch('sounddevice.play') as mock_play:
        with patch('soundfile.read') as mock_read:
            mock_read.return_value = (np.array([0.0] * 2400, dtype=np.float32), 24000)
            player.play(wav_bytes, 24000)

            # Verify play was called with blocking=False
            mock_play.assert_called_once()
            args, kwargs = mock_play.call_args
            assert kwargs.get('blocking') is False

    # Wait for thread to finish
    for t in player._playback_threads:
        t.join(timeout=2.0)


def test_play_multiple_spawn_threads():
    """Verify multiple plays spawn separate threads."""
    player = AudioPlayer()
    wav_bytes = io.BytesIO(np.array([0.0] * 100, dtype=np.float32).tobytes()).getvalue()

    with patch('sounddevice.play'):
        with patch('soundfile.read') as mock_read:
            mock_read.return_value = (np.array([0.0] * 100, dtype=np.float32), 24000)
            for _ in range(3):
                player.play(wav_bytes, 24000)

    assert len(player._playback_threads) == 3
    for t in player._playback_threads:
        t.join(timeout=2.0)


def test_play_handles_audio_errors():
    """Verify playback errors don't crash the thread."""
    player = AudioPlayer()
    wav_bytes = b"invalid data"

    with patch('soundfile.read') as mock_read:
        mock_read.side_effect = Exception("Read error")
        player.play(wav_bytes, 24000)

    # Thread should complete without raising
    for t in player._playback_threads:
        t.join(timeout=2.0)
    # Verify thread finished successfully
    assert all(not t.is_alive() for t in player._playback_threads)
