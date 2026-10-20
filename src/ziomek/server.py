"""ziomek HTTP server — FastAPI application (unified TTS + avatar + STT)."""

import asyncio
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from ziomek import __version__
from ziomek.api.stt_ws import router as stt_ws_router
from ziomek.avatar.skins import SkinRegistry
from ziomek.avatar.state_machine import AvatarInput, AvatarStateMachine
from ziomek.config import Settings
from ziomek.gamepad import GamepadManager
from ziomek.logging import RequestIDMiddleware, get_log_buffer, setup_logging
from ziomek.stt import STTEngine, STTState
from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.playback import AudioPlayer
from ziomek.tts.voice import VoiceStateCache

_logger = logging.getLogger(__name__)

# Import version at module level
_version = __version__

# Global state (initialized at startup)
_startup_time: float = time.time()
_tts_model: Optional[TTSModelWrapper] = None
_voice_cache: Optional[VoiceStateCache] = None
_audio_player: Optional[AudioPlayer] = None
_state_machine: Optional[AvatarStateMachine] = None
_skin_registry: Optional[SkinRegistry] = None
_stt_engine: Optional[STTEngine] = None
_gamepad_manager: Optional[GamepadManager] = None
_gamepad_thread: Optional[threading.Thread] = None
_dev_mode: bool = False


def get_uptime() -> float:
    """Return seconds since server startup."""
    return time.time() - _startup_time


def _start_gamepad_thread(state_machine: AvatarStateMachine) -> None:
    """Start background gamepad polling thread."""
    global _gamepad_manager, _gamepad_thread

    gm = GamepadManager()
    gm.start()
    _gamepad_manager = gm

    def poll_loop() -> None:
        while True:
            try:
                state = _gamepad_manager.poll()  # pyright: ignore[reportPossiblyUnboundVariable]
                if state.connected:
                    buttons = [{"pressed": bool(b), "value": 0.0} for b in state.buttons]
                    inp = AvatarInput(
                        buttons=buttons,
                        axes=state.axes,
                        connected=state.connected,
                        streaming=False,
                        chatFocused=False,
                        errorState=False,
                    )
                    state_machine.update(inp)
            except Exception:
                _logger.exception("gamepad poll loop: unexpected error")
            time.sleep(0.01)  # 100Hz

    _gamepad_thread = threading.Thread(target=poll_loop, daemon=True)
    _gamepad_thread.start()


def _stop_gamepad_thread() -> None:
    """Stop the gamepad polling thread."""
    global _gamepad_manager, _gamepad_thread
    if _gamepad_thread:
        _gamepad_thread.join(timeout=2)
        _gamepad_thread = None
    if _gamepad_manager:
        _gamepad_manager.stop()
        _gamepad_manager = None


_settings: Settings | None = None


def create_app(
    settings: Settings | None = None,
    dev_mode: bool = False,
    verbose: bool = False,
    mcp_enabled: bool = False,
    mcp_http_enabled: bool = False,
    mcp_config_exposed: bool = False,
) -> FastAPI:
    global _tts_model, _voice_cache, _audio_player, _state_machine, _skin_registry, _settings
    if settings is None:
        settings = Settings()
    _settings = settings

    app = FastAPI(
        title="ziomek",
        version=_version,
        description="Humanize AI — TTS speech synthesis, avatar state machine, gamepad, and STT.",
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
    # Initialize TTS model (lazy load on first endpoint call)
    _tts_model = TTSModelWrapper()
    _voice_cache = VoiceStateCache(_tts_model, settings.cache_dir)
    _audio_player = AudioPlayer(backend_name=settings.audio_backend)
    # Initialize avatar components
    _state_machine = AvatarStateMachine()
    _skin_registry = SkinRegistry()
    # Initialize STT engine (optional, can be disabled)
    if not settings.no_vscode:
        global _stt_engine
        from ziomek.api.stt_ws import _stt_callback

        _stt_engine = STTEngine(
            engine_name=settings.stt_engine,
            model_name=settings.stt_model,
            model_dir=settings.stt_model_dir,
            on_transcription=_stt_callback,
            verbose=verbose,
        )
        _stt_engine.start()
        _logger.info(
            "STT engine started: %s model=%s",
            settings.stt_engine,
            settings.stt_model,
        )
    # Start gamepad thread if not in VS Code mode
    if not settings.no_vscode:
        _start_gamepad_thread(_state_machine)
        _logger.info("Gamepad polling thread started")

    # Include routers
    from ziomek.api import avatar, debug, health, stt, tts

    app.include_router(tts.router)
    app.include_router(stt.router)
    app.include_router(avatar.router)
    app.include_router(health.router)
    app.include_router(stt_ws_router)

    # Debug endpoints (only in dev mode)
    if dev_mode:
        app.include_router(debug.router)
        _dev_mode = True

        # Debug page HTML
        @app.get("/debug")
        async def debug_page() -> HTMLResponse:
            html_path = Path(__file__).parent / "client" / "resources" / "debug.html"
            return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    # MCP server (separate thread for stdio, HTTP routes for http mode)
    if mcp_enabled:
        import threading

        def _start_mcp() -> None:
            from ziomek.mcp import start_mcp_server

            start_mcp_server(mcp_config_exposed)

        mcp_thread = threading.Thread(target=_start_mcp, daemon=True)
        mcp_thread.start()
        _logger.info("MCP server started (stdio transport)")

    if mcp_http_enabled:
        from ziomek.mcp.http import register_mcp_http_routes

        register_mcp_http_routes(app, mcp_config_exposed)
        _logger.info("MCP server started (http transport)")

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
    dev_mode: bool = False,
    verbose: bool = False,
    mcp_enabled: bool = False,
    mcp_http_enabled: bool = False,
    mcp_config_exposed: bool = False,
):
    """Run the unified ziomek server.

    Serves TTS, avatar state machine, gamepad polling, WebSocket relay,
    and STT transcription in a single process.

    Args:
        port: Server port (default: 5003).
        model_path: Path to TTS model file.
        voice: Voice identifier (default: "default").
        cache_dir: Directory for TTS cache.
        audio_backend: Audio playback backend.
        audio_device: Audio device index, name, or "default".
        host: Host to bind (default: localhost).
        log_level: Logging level.
        no_vscode: Disable VS Code WebSocket relay and gamepad polling.
        no_browser: Do not open local browser.
        stt_engine: STT engine name (faster_whisper).
        stt_model: STT model name.
        stt_model_dir: STT model download directory.
        dev_mode: Enable debug endpoints and debug page.
        verbose: Enable DEBUG logging.
        mcp_enabled: Enable MCP server in stdio mode alongside HTTP server.
        mcp_http_enabled: Enable MCP server in HTTP mode alongside HTTP server.
        mcp_config_exposed: Expose full config via MCP (default: read-only).
    """
    # Determine effective log level
    effective_level = log_level
    if verbose:
        effective_level = "DEBUG"

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
        mcp_port=port,  # Reuse main port for MCP HTTP if not specified
        mcp_transport="http" if mcp_http_enabled else "stdio",
    )
    setup_logging(level=effective_level, enable_buffer=dev_mode)
    app = create_app(
        settings, dev_mode=dev_mode, verbose=verbose,
        mcp_enabled=mcp_enabled, mcp_http_enabled=mcp_http_enabled,
        mcp_config_exposed=mcp_config_exposed,
    )
    effective_port = port if port is not None else settings.port
    print(
        f"ziomek server listening on http://{settings.host}:{effective_port}",
        file=sys.stderr,
    )
    if dev_mode:
        print(f"  Debug mode enabled: http://{settings.host}:{effective_port}/debug", file=sys.stderr)
    if verbose:
        print("  Verbose mode enabled: DEBUG logging", file=sys.stderr)
    if mcp_enabled:
        print(f"  MCP server enabled (stdio transport)", file=sys.stderr)
        if mcp_config_exposed:
            print("  MCP config exposed: full config (default: read-only)", file=sys.stderr)
    if mcp_http_enabled:
        print(f"  MCP server enabled (http transport, port {settings.mcp_port})", file=sys.stderr)
        if mcp_config_exposed:
            print("  MCP config exposed: full config (default: read-only)", file=sys.stderr)
    uvicorn.run(app, host=settings.host, port=effective_port)


def shutdown_server() -> None:
    """Clean up server resources (gamepad thread, STT engine)."""
    global _stt_engine
    _stop_gamepad_thread()
    if _stt_engine:
        _stt_engine.stop()
        _stt_engine = None
