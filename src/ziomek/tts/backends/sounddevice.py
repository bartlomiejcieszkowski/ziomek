"""ziomek TTS audio backends — Sounddevice (default) backend."""

import gc
import io
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

from .base import IBackend


class SounddeviceBackend(IBackend):
    """Audio playback using sounddevice (supports mixing)."""

    @property
    def supports_mixing(self) -> bool:
        return True

    def play(self, data: bytes, sr: int) -> None:
        """Single-shot blocking playback."""
        thread = threading.Thread(
            target=self._playback_thread,
            args=(data, sr),
            daemon=True,
        )
        thread.start()
        thread.join()

    def mix_play(self, data: bytes, sr: int) -> None:
        """Overlapping non-blocking playback."""
        thread = threading.Thread(
            target=self._playback_thread,
            args=(data, sr),
            daemon=True,
        )
        thread.start()

    def _playback_thread(self, data: bytes, sr: int) -> None:
        try:
            wav_file = io.BytesIO(data)
            audio_data, read_sr = sf.read(wav_file)
            if audio_data.ndim == 2:
                audio_data = audio_data.mean(axis=1)
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            sd.play(audio_data, samplerate=read_sr, blocking=False)
            duration_s = len(audio_data) / read_sr if len(audio_data) > 0 else 0
            time.sleep(duration_s + 0.1)
            sd.stop()
            gc.collect()
        except Exception:
            # Silent failure — playback errors shouldn't crash the server
            pass

    def list_devices(self) -> list[dict]:
        try:
            devices = sd.query_devices()
            return [
                {
                    "id": i,
                    "name": d["name"] if isinstance(d, dict) else d.name,
                    "channels": d["channels_out"] if isinstance(d, dict) else d.max_output_channels,
                }
                for i, d in enumerate(devices)
            ]
        except Exception:
            return []
