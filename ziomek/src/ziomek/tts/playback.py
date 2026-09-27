"""ziomek TTS audio playback with sounddevice mixing support."""
import io
import threading
import time
import gc

import numpy as np  # type: ignore[import-untyped]
import soundfile as sf  # type: ignore[import-untyped]
import sounddevice as sd  # type: ignore[import-untyped]


class AudioPlayer:
    """Handles non-blocking audio playback with mixing support."""

    def __init__(self):
        self._playback_threads: list[threading.Thread] = []

    def play(self, wav_bytes: bytes, sample_rate: int) -> None:
        """Play WAV audio bytes without blocking.

        Uses sounddevice.play() for non-blocking playback that supports
        multiple simultaneous voices (mixing).
        """
        thread = threading.Thread(
            target=self._play_thread,
            args=(wav_bytes, sample_rate),
            daemon=True,
        )
        self._playback_threads.append(thread)
        thread.start()

    def _play_thread(self, wav_bytes: bytes, sample_rate: int) -> None:
        """Actual playback in a background thread."""
        try:
            wav_file = io.BytesIO(wav_bytes)
            audio_data, read_sr = sf.read(wav_file)
            if audio_data.ndim == 2:
                audio_data = audio_data.mean(axis=1)
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            # Non-blocking playback — supports mixing
            sd.play(audio_data, samplerate=read_sr, blocking=False)
            # Wait for playback to complete
            duration_s = len(audio_data) / read_sr if len(audio_data) > 0 else 0
            time.sleep(duration_s + 0.1)
            sd.stop()
            gc.collect()
        except Exception:
            # Silent failure — playback errors shouldn't crash the server
            pass
