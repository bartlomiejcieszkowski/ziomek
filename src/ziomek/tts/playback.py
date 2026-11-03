"""ziomek TTS audio playback — backend-agnostic wrapper."""

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .backends.base import IBackend

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Thin wrapper that delegates to a pluggable backend."""

    def __init__(self, backend_name: str = "sounddevice") -> None:
        from .backends import BackendRegistry

        self.backend_name = backend_name
        self._backend: "IBackend" = BackendRegistry().get(backend_name)
        self.device_name: str | None = None
        self._workers: list[threading.Thread] = []
        self._active = 0
        self._counted = threading.Lock()

    def play(self, wav_bytes: bytes, sample_rate: int) -> None:
        """Hand the sound to a worker. The wait for the device happens there, not in this call.

        A caller that waits for the device answers only after the whole utterance has been played,
        which is why a request should not be the thing that waits. The worker still waits, so nothing
        is finished before the device has taken the samples.
        """
        worker = threading.Thread(target=self._run, args=(wav_bytes, sample_rate), daemon=True)
        self._workers.append(worker)
        worker.start()

    def _run(self, wav_bytes: bytes, sample_rate: int) -> None:
        """Take one sound at a time, unless another is already on the device and the backend can mix."""
        with self._counted:
            overlaps = self._active > 0
            self._active += 1
        try:
            if overlaps and self._backend.supports_mixing:
                self._backend.mix_play(wav_bytes, sample_rate)
            else:
                self._backend.play(wav_bytes, sample_rate)
        finally:
            with self._counted:
                self._active -= 1

    def mix_play(self, wav_bytes: bytes, sample_rate: int) -> None:
        """Overlapping, non-blocking playback."""
        self._backend.mix_play(wav_bytes, sample_rate)

    def list_devices(self) -> list[dict]:
        return self._backend.list_devices()

    def supports_mixing(self) -> bool:
        return self._backend.supports_mixing
