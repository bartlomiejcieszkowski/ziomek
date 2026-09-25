"""ziomek TTS generation — text to WAV bytes (base64 response)."""
import base64
import io
import numpy as np  # type: ignore[import-untyped]
import scipy.io.wavfile as wavfile  # type: ignore[import-untyped]
import torch  # type: ignore[import-untyped]

from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.voice import VoiceStateCache


def generate_wav(
    model: TTSModelWrapper,
    voice_cache: VoiceStateCache,
    text: str,
    voice: str = "default",
) -> tuple[str, float, int]:
    """Generate WAV audio from text.

    Returns:
        Tuple of (base64-encoded WAV, duration in seconds, sample rate).
    """
    if not model.ready:
        raise RuntimeError("TTS model not loaded")
    voice_state = voice_cache.load_voice(voice)
    audio_tensor = model.generate_audio(voice_state, text)
    if isinstance(audio_tensor, torch.Tensor):
        audio_np = audio_tensor.detach().cpu().numpy()
    else:
        audio_np = np.array(audio_tensor)
    sample_rate = model.sample_rate
    wav_buffer = io.BytesIO()
    wavfile.write(wav_buffer, sample_rate, audio_np)
    wav_bytes = wav_buffer.getvalue()
    audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
    duration = len(audio_np) / sample_rate if hasattr(audio_np, "__len__") else 0
    return audio_b64, float(duration), sample_rate
