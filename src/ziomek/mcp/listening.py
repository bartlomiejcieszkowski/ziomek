"""ziomek MCP continuous listening session manager."""

from __future__ import annotations

import threading
from typing import Any

from ziomek.stt import STTEngine, STTResult, STTState


class ListeningSession:
    """Manages a continuous listening session from the microphone.

    Wraps an STTEngine instance and provides thread-safe access to the
    latest transcription result.
    """

    def __init__(self) -> None:
        self._engine: STTEngine | None = None
        self._lock = threading.Lock()
        self._latest_result: STTResult | None = None
        self._active = False

    def start(self, engine_name: str = "faster_whisper", model_name: str = "tiny") -> bool:
        """Start continuous listening from the microphone.

        Args:
            engine_name: STT engine name (default: faster_whisper).
            model_name: STT model name (default: tiny).

        Returns:
            True if listening started successfully, False otherwise.
        """
        with self._lock:
            if self._active:
                return False

            try:
                self._engine = STTEngine(
                    engine_name=engine_name,
                    model_name=model_name,
                    verbose=False,
                    on_transcription=self._on_transcription,
                )
                self._engine.start_recording()
                self._active = True
                return True
            except Exception:
                return False

    def stop(self) -> bool:
        """Stop continuous listening.

        Returns:
            True if stopped successfully, False if not active.
        """
        with self._lock:
            if not self._active:
                return False

            try:
                if self._engine:
                    self._engine.stop_recording()
                    self._engine = None
                self._active = False
                return True
            except Exception:
                return False

    def get_result(self) -> dict[str, Any]:
        """Get the latest transcription result.

        Returns:
            Dict with text, is_final, and state fields.
        """
        with self._lock:
            state = STTState.LISTENING if self._active else STTState.IDLE
            if self._latest_result:
                return {
                    "text": self._latest_result.text,
                    "is_final": self._latest_result.is_final,
                    "state": state.value,
                }
            return {
                "text": "",
                "is_final": False,
                "state": state.value,
            }

    @property
    def is_active(self) -> bool:
        """Whether the session is currently recording."""
        with self._lock:
            return self._active

    def _on_transcription(self, result: STTResult) -> None:
        """Callback invoked by STTEngine on each transcription result."""
        with self._lock:
            self._latest_result = result
