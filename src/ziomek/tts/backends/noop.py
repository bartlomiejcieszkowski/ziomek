"""ziomek TTS audio backends — No-Op (test/dry-run) backend."""

from .base import IBackend


class NoopBackend(IBackend):
    """No-op backend for testing and dry-run mode."""

    @property
    def supports_mixing(self) -> bool:
        return True

    def play(self, data: bytes, sr: int) -> None:
        pass

    def mix_play(self, data: bytes, sr: int) -> None:
        pass

    def list_devices(self) -> list[dict]:
        return []
