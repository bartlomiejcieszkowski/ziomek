"""ziomek HTTP server — FastAPI application."""
import sys
from typing import Optional

import uvicorn
from fastapi import FastAPI

from ziomek.config import Settings
from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.voice import VoiceStateCache
from ziomek.tts.playback import AudioPlayer


# Global state (initialized at startup)
_tts_model: Optional[TTSModelWrapper] = None
_voice_cache: Optional[VoiceStateCache] = None
_audio_player: Optional[AudioPlayer] = None


def create_app(settings: Settings = None) -> FastAPI:
    global _tts_model, _voice_cache, _audio_player
    if settings is None:
        settings = Settings()
    app = FastAPI(title="ziomek", version="0.1.0")
    # Initialize TTS model
    _tts_model = TTSModelWrapper()
    # Note: model loading deferred to endpoint initialization
    # _tts_model.load(settings.model_path)
    _voice_cache = VoiceStateCache(_tts_model, settings.cache_dir)
    _audio_player = AudioPlayer()
    # Include TTS router
    from ziomek.api import tts
    app.include_router(tts.router, tags=["TTS"])
    return app


def run_server(port=5003, model_path=None, voice="default", cache_dir=None):
    settings = Settings(port=port, model_path=model_path, voice=voice, cache_dir=cache_dir)
    app = create_app(settings)
    print(f"ziomek server listening on http://localhost:{port}", file=sys.stderr)
    uvicorn.run(app, host="localhost", port=port)
