import pytest
import base64
import io
import numpy as np
import scipy.io.wavfile as wavfile
import torch  # type: ignore[import-untyped]
from unittest.mock import MagicMock, patch

from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.voice import VoiceStateCache
from ziomek.tts.generate import generate_wav


def test_generate_raises_when_not_ready():
    """Verify generate_wav raises when model not ready."""
    model = MagicMock(spec=TTSModelWrapper)
    model.ready = False
    voice_cache = VoiceStateCache(model)
    with pytest.raises(RuntimeError, match="not loaded"):
        generate_wav(model, voice_cache, "test")


def test_generate_returns_valid_wav():
    """Verify generate_wav returns valid base64 WAV data."""
    model = MagicMock(spec=TTSModelWrapper)
    model.ready = True
    model.sample_rate = 24000
    mock_audio = torch.zeros(24000)  # 1 second of silence

    with patch.object(model, 'generate_audio', return_value=mock_audio):
        voice_cache = VoiceStateCache(model)
        voice_cache.load_voice = MagicMock(return_value={})
        audio_b64, duration, sr = generate_wav(model, voice_cache, "test")

        assert duration == pytest.approx(1.0, abs=0.01)
        assert sr == 24000
        assert isinstance(audio_b64, str)
        assert len(audio_b64) > 0

        # Verify base64 decodes to valid WAV
        wav_bytes = base64.b64decode(audio_b64)
        read_sr, data = wavfile.read(io.BytesIO(wav_bytes))
        assert read_sr == 24000
        assert len(data) == 24000
