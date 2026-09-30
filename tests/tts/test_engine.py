from unittest.mock import MagicMock

from ziomek.tts.engine import TTSModelWrapper


def test_engine_initialization():
    """Verify wrapper starts not ready with default sample rate."""
    wrapper = TTSModelWrapper()
    assert wrapper.ready is False
    assert wrapper.sample_rate == 24000


def test_generate_raises_when_not_loaded():
    """Verify generate_audio raises RuntimeError when model not loaded."""
    wrapper = TTSModelWrapper()
    try:
        wrapper.generate_audio({}, "test")
        assert False, "Should have raised"
    except RuntimeError as e:
        assert "not loaded" in str(e)
