"""ziomek HTTP server — FastAPI application."""

import sys
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ziomek import __version__
from ziomek.avatar.skins import SkinRegistry
from ziomek.avatar.state_machine import AvatarStateMachine
from ziomek.config import Settings
from ziomek.logging import RequestIDMiddleware, setup_logging
from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.playback import AudioPlayer
from ziomek.tts.voice import VoiceStateCache

# Import version at module level
_version = __version__

# Global state (initialized at startup)
_startup_time: float = time.time()
_tts_model: Optional[TTSModelWrapper] = None
_voice_cache: Optional[VoiceStateCache] = None
_audio_player: Optional[AudioPlayer] = None
_state_machine: Optional[AvatarStateMachine] = None
_skin_registry: Optional[SkinRegistry] = None


def get_uptime() -> float:
    """Return seconds since server startup."""
    return time.time() - _startup_time


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
        allow_origin_regex=r"http://localhost:\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Add request ID tracing middleware
    app.add_middleware(RequestIDMiddleware)
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
    port: int | None = None,
    model_path: str | None = None,
    voice: str = "default",
    cache_dir: str | None = None,
    audio_backend: str | None = None,
    audio_device: str | int | None = None,
    host: str | None = None,
    log_level: str = "INFO",
    no_vscode: bool = False,
    no_browser: bool = False,
    stt_engine: str | None = None,
    stt_model: str | None = None,
    stt_model_dir: str | None = None,
):
    """Run the ziomek TTS server.

    Args:
        port: Server port (default: 5003).
        model_path: Path to TTS model file.
        voice: Voice identifier (default: "default").
        cache_dir: Directory for TTS cache.
        audio_backend: Audio playback backend.
        audio_device: Audio device index, name, or "default".
        host: Host to bind (default: localhost).
        log_level: Logging level.
        no_vscode: Disable VS Code WebSocket relay.
        no_browser: Do not open local browser.
        stt_engine: STT engine name (whisper_cpp, faster_whisper).
        stt_model: STT model name.
        stt_model_dir: STT model download directory.
    """
    settings = Settings.compose(
        cli_backend=audio_backend,
        cli_device=audio_device,
        cli_host=host,
        port=port,
        model_path=model_path,
        voice=voice,
        cache_dir=cache_dir,
        no_browser=no_browser,
        no_vscode=no_vscode,
        stt_engine=stt_engine,
        stt_model=stt_model,
        stt_model_dir=stt_model_dir,
    )
    setup_logging(level=log_level)
    app = create_app(settings)
    effective_port = port if port is not None else settings.port
    print(
        f"ziomek server listening on http://{settings.host}:{effective_port}",
        file=sys.stderr,
    )
    uvicorn.run(app, host=settings.host, port=effective_port)
