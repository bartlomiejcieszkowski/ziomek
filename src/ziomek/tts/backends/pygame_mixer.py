"""pygame.mixer audio backend — cross-platform with limited mixing."""

import io
import logging

import numpy as np

from .base import IBackend

logger = logging.getLogger(__name__)


class PygameMixerBackend(IBackend):
    """Audio backend using pygame.mixer."""

    @property
    def supports_mixing(self) -> bool:
        return True

    def play(self, data: bytes, sr: int) -> None:
        import pygame

        wav = io.BytesIO(data)
        try:
            import soundfile as sf

            audio, read_sr = sf.read(wav)
        except Exception:
            logger.warning("pygame_backend: soundfile unavailable, passing raw bytes")
            audio = np.frombuffer(data, dtype=np.float32)
            read_sr = sr

        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        pygame.mixer.init(frequency=read_sr, size=-16, channels=1)
        channel = pygame.mixer.Channel(0)
        sound = pygame.mixer.Sound(buffer=(audio * 32767).astype(np.int16).tobytes())
        channel.play(sound)
        channel.get_queue()  # wait for playback

    def mix_play(self, data: bytes, sr: int) -> None:
        import pygame

        wav = io.BytesIO(data)
        try:
            import soundfile as sf

            audio, read_sr = sf.read(wav)
        except Exception:
            logger.warning("pygame_backend: soundfile unavailable, passing raw bytes")
            audio = np.frombuffer(data, dtype=np.float32)
            read_sr = sr

        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        pygame.mixer.init(frequency=read_sr, size=-16, channels=8)
        sound = pygame.mixer.Sound(buffer=(audio * 32767).astype(np.int16).tobytes())
        sound.play()  # non-blocking, automatic channel assignment

    def list_devices(self) -> list[dict]:
        import pygame

        pygame.mixer.init()
        return [{"id": 0, "name": "pygame default", "channels": 8}]
