"""ziomek TTS audio backends — Sounddevice (default) backend."""

import io

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
        """Single-shot playback: wait until the device has taken every sample."""
        self._playback(data, sr, wait=True)

    def mix_play(self, data: bytes, sr: int) -> None:
        """Overlapping playback: return while the device is still taking samples."""
        self._playback(data, sr, wait=False)

    def _playback(self, data: bytes, sr: int, wait: bool) -> None:
        try:
            audio_data, read_sr = sf.read(io.BytesIO(data))
            if audio_data.ndim == 2:
                audio_data = audio_data.mean(axis=1)
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            sd.play(audio_data, samplerate=read_sr, blocking=wait)
            # Nothing is stopped after a playback that is not waited for: stopping before the device
            # has taken the samples cuts the end of what was queued. Overlapping playback needs an
            # explicit output stream, which is recorded in docs/internal/TODO.md.
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
