"""ziomek TTS audio backends — pluggable playback system."""
import importlib
import logging
from typing import TYPE_CHECKING

from .base import IBackend

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .base import IBackend


class BackendRegistry:
    """Lazy registry of audio backends."""

    _instance: "BackendRegistry | None" = None
    _backends: dict[str, type["IBackend"]] = {}

    def __new__(cls) -> "BackendRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._backends:
            self._register_backend("noop", "ziomek.tts.backends.noop", "NoopBackend")
            self._register_backend(
                "sounddevice", "ziomek.tts.backends.sounddevice", "SounddeviceBackend"
            )

    def _register_backend(self, name: str, module_name: str, class_name: str) -> None:
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            self._backends[name] = cls
        except ImportError as exc:
            logger.warning("Backend %s unavailable (%s) — skipped", name, exc)

    def get(self, name: str) -> "IBackend":
        if name not in self._backends:
            raise ValueError(f"Unknown audio backend: {name}")
        return self._backends[name]()  # type: ignore[no-any-return]

    def list_backends(self) -> list[str]:
        return list(self._backends.keys())
