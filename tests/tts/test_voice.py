from unittest.mock import MagicMock
from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.voice import VoiceStateCache


def test_voice_cache_caches_states():
    """Verify voice states are cached and loaded only once."""
    model = MagicMock(spec=TTSModelWrapper)
    model.sample_rate = 24000
    model.ready = True
    mock_model_instance = MagicMock()
    mock_model_instance.get_state_for_audio_prompt.return_value = {"voice": "test"}
    model.model = mock_model_instance
    cache = VoiceStateCache(model)
    cache.load_voice("cosette")
    cache.load_voice("cosette")
    # Should have been called only once (cached)
    assert len(cache._states) == 1
    # Verify get_state_for_audio_prompt was called once with cosette
    mock_model_instance.get_state_for_audio_prompt.assert_called_once_with("cosette")


def test_voice_cache_returns_different_states():
    """Verify different voice keys return different cached states."""
    model = MagicMock(spec=TTSModelWrapper)
    model.sample_rate = 24000
    model.ready = True
    mock_model_instance = MagicMock()
    mock_model_instance.get_state_for_audio_prompt.return_value = {"voice": "test"}
    model.model = mock_model_instance
    cache = VoiceStateCache(model)
    cache.load_voice("cosette")
    cache.load_voice("marius")
    assert len(cache._states) == 2


def test_default_voice_maps_to_cosette():
    """Verify 'default' voice key maps to 'cosette'."""
    model = MagicMock(spec=TTSModelWrapper)
    model.sample_rate = 24000
    model.ready = True
    mock_model_instance = MagicMock()
    mock_model_instance.get_state_for_audio_prompt.return_value = {"voice": "cosette"}
    model.model = mock_model_instance
    cache = VoiceStateCache(model)
    cache.load_voice("default")
    # Should have stored as 'default' key
    assert "default" in cache._states
    # Should have called get_state_for_audio_prompt with 'cosette'
    mock_model_instance.get_state_for_audio_prompt.assert_called_once_with("cosette")
