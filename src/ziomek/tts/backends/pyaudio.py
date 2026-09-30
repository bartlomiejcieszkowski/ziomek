"""pyaudio audio backend — cross-platform with full mixing support."""

import io
import logging
from typing import Optional

import numpy as np

from .base import IBackend

logger = logging.getLogger(__name__)


class PyaudioBackend(IBackend):
    """Audio backend using PyAudio."""

    @property
    def supports_mixing(self) -> bool:
        return True

    def __init__(self) -> None:
        import pyaudio

        self._pa = pyaudio.PyAudio()
        try:
            info = self._pa.get_default_output_device_info()
            self._output_device: int = int(info["index"])
        except OSError:
            self._output_device = 0

    def play(self, data: bytes, sr: int) -> None:
        import pyaudio

        stream = self._pa.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=sr,
            output=True,
            output_device_index=self._output_device,
        )
        stream.write(data)
        stream.stop_stream()
        stream.close()

    def mix_play(self, data: bytes, sr: int) -> None:
        import pyaudio

        stream = self._pa.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=sr,
            output=True,
            output_device_index=self._output_device,
            frames_per_buffer=1024,
        )
        stream.write(data)
        # Don't close immediately — allows overlapping playback

    def list_devices(self) -> list[dict]:
        devices: list[dict] = []
        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            channels = int(info["maxOutputChannels"])
            if channels > 0:
                devices.append(
                    {
                        "id": i,
                        "name": info["name"],
                        "channels": channels,
                    }
                )
        return devices

    def __del__(self) -> None:
        try:
            self._pa.terminate()
        except Exception:
            pass
