"""ziomek HTTP server — FastAPI application."""

import sys
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ziomek import __version__
from ziomek.avatar.skins import SkinRegistry
from ziomek.avatar.state_machine import AvatarStateMachine
from ziomek.config import Settings
from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.playback import AudioPlayer
from ziomek.tts.voice import VoiceStateCache

# Import version at module level
_version = __version__

# Global state (initialized at startup)
_tts_model: Optional[TTSModelWrapper] = None
_voice_cache: Optional[VoiceStateCache] = None
_audio_player: Optional[AudioPlayer] = None
_state_machine: Optional[AvatarStateMachine] = None
_skin_registry: Optional[SkinRegistry] = None


def create_app(settings: Settings | None = None) -> FastAPI:
    global _tts_model, _voice_cache, _audio_player, _state_machine, _skin_registry
    if settings is None:
        settings = Settings()
    app = FastAPI(
        title="ziomek",
        version=_version,
        description="Humanize AI — TTS speech synthesis, avatar state machine, and gamepad integration.",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    # Add CORS middleware for VS Code webviews
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Initialize TTS model
    _tts_model = TTSModelWrapper()
    # Note: model loading deferred to endpoint initialization
    # _tts_model.load(settings.model_path)
    _voice_cache = VoiceStateCache(_tts_model, settings.cache_dir)
    _audio_player = AudioPlayer(backend_name=settings.audio_backend)
    # Initialize avatar components
    _state_machine = AvatarStateMachine()
    _skin_registry = SkinRegistry()
    # Include routers
    from ziomek.api import avatar, health, tts

    app.include_router(tts.router)
    app.include_router(avatar.router)
    app.include_router(health.router)
    return app


def run_server(
    port=5003,
    model_path=None,
    voice="default",
    cache_dir=None,
    audio_backend=None,
    audio_device=None,
):
    settings = Settings.compose(
        cli_backend=audio_backend,
        cli_device=audio_device,
        port=port,
        model_path=model_path,
        voice=voice,
        cache_dir=cache_dir,
    )
    app = create_app(settings)
    print(f"ziomek server listening on http://localhost:{port}", file=sys.stderr)
    uvicorn.run(app, host="localhost", port=port)
