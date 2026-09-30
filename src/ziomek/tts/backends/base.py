"""ziomek TTS audio backends — IBackend abstract protocol."""

from abc import ABC, abstractmethod


class IBackend(ABC):
    """Protocol for audio playback backends."""

    @abstractmethod
    def play(self, data: bytes, sr: int) -> None:
        """Single-shot playback."""

    @abstractmethod
    def mix_play(self, data: bytes, sr: int) -> None:
        """Overlapping, non-blocking playback."""

    @abstractmethod
    def list_devices(self) -> list[dict]:
        """Return available audio endpoints.

        Each dict has keys: id (int), name (str), channels (int).
        Return [] if device enumeration is not supported.
        """

    @property
    @abstractmethod
    def supports_mixing(self) -> bool:
        """Whether this backend supports overlapping (mixing) playback."""
