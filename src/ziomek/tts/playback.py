"""ziomek TTS audio playback — backend-agnostic wrapper."""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .backends.base import IBackend

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Thin wrapper that delegates to a pluggable backend."""

    def __init__(self, backend_name: str = "sounddevice") -> None:
        from .backends import BackendRegistry

        self._backend: "IBackend" = BackendRegistry().get(backend_name)

    def play(self, wav_bytes: bytes, sample_rate: int) -> None:
        """Single-shot playback."""
        self._backend.play(wav_bytes, sample_rate)

    def mix_play(self, wav_bytes: bytes, sample_rate: int) -> None:
        """Overlapping, non-blocking playback."""
        self._backend.mix_play(wav_bytes, sample_rate)

    def list_devices(self) -> list[dict]:
        return self._backend.list_devices()

    def supports_mixing(self) -> bool:
        return self._backend.supports_mixing
