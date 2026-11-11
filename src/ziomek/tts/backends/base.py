"""ziomek TTS audio backends — IBackend abstract protocol."""

from abc import ABC, abstractmethod

from .devices import resolve_devices


class IBackend(ABC):
    """Protocol for audio playback backends."""

    def __init__(self, device=None, extra_settings=None) -> None:
        """Keep what was asked for, and answer it against the devices this path can see.

        A path that cannot be aimed keeps nothing: answering with its own default would be a device the
        caller never asked for.
        """
        self.device = device
        # The name is not kept as an answer here: a name is only an answer when a device carries it, and
        # a path that cannot be aimed keeps nothing, so a caller cannot mistake its own device for the one
        # that was asked for. The answer names every device that carries the name, so more than one can be
        # said instead of one being picked in silence.
        self.hears_on: list[int] = resolve_devices(device, self) if self.can_be_aimed_at_a_device else []
        self.extra_settings = extra_settings

    def which_device_hears(self) -> int | None:
        """The device this path plays on. When more than one could be meant, none of them is taken here."""
        return self.hears_on[0] if len(self.hears_on) == 1 else None

    @property
    def can_be_aimed_at_a_device(self) -> bool:
        """Whether this path can play on a device it was told about."""
        return False

    @property
    def can_take_extra_settings(self) -> bool:
        """Whether extra settings mean anything on this path."""
        return False

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
