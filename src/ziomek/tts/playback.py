"""ziomek TTS audio playback — backend-agnostic wrapper."""

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .backends.base import IBackend

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Thin wrapper that delegates to a pluggable backend."""

    def __init__(self, backend_name: str = "sounddevice", device=None, extra_settings=None) -> None:
        from .backends import BackendRegistry

        self.backend_name = backend_name
        self.device_name: str | None = device
        # What was asked for is kept as it was asked. It is played only where it can be heard: a name no
        # device carries, or a path that cannot be aimed, is said out loud instead of answered by the
        # default in silence. So does a name that more than one device could mean.
        self._refuses_to_play = False
        self._backend: "IBackend" = BackendRegistry().get(backend_name, device, extra_settings)
        if device is not None and str(device).lower() != "default":
            if not self._backend.can_be_aimed_at_a_device:
                logger.error("the device asked for (%s) cannot be aimed on backend %s", device, backend_name)
                self._refuses_to_play = True
            elif not self._backend.hears_on:
                logger.error("no device on backend %s carries %s", backend_name, device)
                self._refuses_to_play = True
            elif len(self._backend.hears_on) > 1:
                names = ", ".join(
                    dev["name"] for dev in self._backend.list_devices() if dev["id"] in self._backend.hears_on
                )
                logger.error("more than one device could be meant for %s: %s", device, names)
                self._refuses_to_play = True
        self._workers: list[threading.Thread] = []
        self._active = 0
        self._counted = threading.Lock()

    def play(self, wav_bytes: bytes, sample_rate: int) -> None:
        """Hand the sound to a worker. The wait for the device happens there, not in this call.

        A caller that waits for the device answers only after the whole utterance has been played,
        which is why a request should not be the thing that waits. The worker still waits, so nothing
        is finished before the device has taken the samples.
        """
        if self._refuses_to_play:
            return
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
        if self._refuses_to_play:
            return
        self._backend.mix_play(wav_bytes, sample_rate)

    def list_devices(self) -> list[dict]:
        return self._backend.list_devices()

    def supports_mixing(self) -> bool:
        return self._backend.supports_mixing
