"""playsound audio backend — simple single-shot playback (no mixing)."""

import io
import logging
import tempfile

from .base import IBackend

logger = logging.getLogger(__name__)


class PlaysoundBackend(IBackend):
    """Audio backend using playsound library.

    Note: playsound does NOT support mixing (overlapping playback).
    Each call to play()/mix_play() will block until the sound finishes.
    """

    @property
    def supports_mixing(self) -> bool:
        return False

    def play(self, data: bytes, sr: int) -> None:
        from playsound import playsound

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(data)
            f.flush()
            playsound(f.name)

    def mix_play(self, data: bytes, sr: int) -> None:
        # Falls back to sequential playback (same as play())
        self.play(data, sr)

    def list_devices(self) -> list[dict]:
        return [{"id": 0, "name": "playsound default", "channels": 2}]
