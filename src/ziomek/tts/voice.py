"""ziomek TTS voice state management."""

import os
from pathlib import Path

from ziomek.tts.engine import TTSModelWrapper


class VoiceStateCache:
    """Cache and load voice states for TTS."""

    def __init__(self, model: TTSModelWrapper, cache_dir: str | None = None):
        self._model = model
        self._cache_dir: Path | None = Path(cache_dir) if cache_dir else None
        self._states: dict[str, dict] = {}

    def load_voice(self, voice_key: str) -> dict:
        """Load or retrieve cached voice state.

        Uses catalog voice "cosette" as default when voice_key is "default".
        """
        if voice_key in self._states:
            return self._states[voice_key]
        # Use catalog voice "cosette" as default (same as TS pocket-tts-server.py)
        voice_key_to_use = voice_key if voice_key != "default" else "cosette"
        model_instance = self._model.model  # Access the underlying TTSModel instance
        state = model_instance.get_state_for_audio_prompt(voice_key_to_use)
        self._states[voice_key] = state
        return state
