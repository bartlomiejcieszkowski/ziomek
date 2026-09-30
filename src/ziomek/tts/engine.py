"""ziomek TTS engine — Pocket TTS model management."""
from typing import Optional

import torch  # type: ignore[import-untyped]


class TTSModelWrapper:
    """Wrapper around pocket_tts.TTSModel."""

    def __init__(self):
        self._tts_model = None  # type: Optional["TTSModel"]  # type: ignore[name-defined]
        self.sample_rate: int = 24000

    @property
    def model(self):
        """Expose the underlying TTS model instance."""
        return self._tts_model

    def load(self, model_path: str = None) -> None:
        """Load the Pocket TTS model."""
        from pocket_tts import TTSModel  # type: ignore[import-untyped]
        if model_path:
            self._tts_model = TTSModel.load_from_path(model_path)
        else:
            self._tts_model = TTSModel.load_model()

    @property
    def ready(self) -> bool:
        """Return True if model is loaded."""
        return self._tts_model is not None

    def generate_audio(self, voice_state: dict, text: str) -> torch.Tensor:  # type: ignore[name-defined]
        """Generate audio from text and voice state."""
        if not self.ready:
            raise RuntimeError("TTS model not loaded")
        return self._tts_model.generate_audio(voice_state, text)  # type: ignore[union-attr]
