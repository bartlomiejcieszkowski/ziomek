"""Pytest fixtures for ziomek tests."""

import pytest


@pytest.fixture(autouse=True)
def _cleanup_stt_engine():
    """Stop STT engine after each test to prevent hanging threads."""
    yield
    try:
        from ziomek.server import _stt_engine
        if _stt_engine is not None:
            _stt_engine.stop()
    except Exception:
        pass
