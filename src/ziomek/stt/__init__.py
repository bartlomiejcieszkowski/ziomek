"""ziomek STT — speech-to-text using RealtimeSTT."""

from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Import RealtimeSTT at module level so tests can patch it
try:
    import RealtimeSTT  # noqa: F401
except ImportError:
    pass  # Optional dependency

logger = logging.getLogger(__name__)


class STTState(enum.Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"


@dataclass
class STTResult:
    """A transcription result."""
    text: str
    is_final: bool
    realtime: bool = False


@dataclass
class STTStats:
    """Runtime stats for the STT engine."""
    state: STTState = STTState.IDLE
    engine_name: str = "faster_whisper"
    model_name: str = "tiny"
    last_text: str = ""
    last_is_final: bool = False
    transcription_count: int = 0


class STTEngine:
    """Wraps RealtimeSTT's AudioToTextRecorder for server-side speech recognition.

    Default engine is ``faster_whisper`` (CTranslate2) because ``whisper_cpp``
    (pywhispercpp) segfaults on Windows with BEX64 access violations
    (see ISSUES.md).

    Args:
        engine_name: RealtimeSTT transcription engine name.
            ``"faster_whisper"`` (default, recommended) or ``"whisper_cpp"``.
        model_name: Model identifier (e.g. ``"tiny"``, ``"base"``).
        model_dir: Optional download root / model directory.
        on_transcription: Callback invoked with each :class:`STTResult`.
        verbose: Enable detailed logging of STT events (VAD, recording, transcription).
    """

    def __init__(
        self,
        engine_name: str = "faster_whisper",
        model_name: str = "tiny",
        model_dir: str | None = None,
        on_transcription: Callable[[STTResult], None] | None = None,
        verbose: bool = False,
    ) -> None:
        self._engine_name = engine_name
        self._model_name = model_name
        self._model_dir = model_dir
        self._on_transcription = on_transcription
        self._transcription_queue: list[STTResult] = []
        self._queue_lock = threading.Lock()
        self._verbose = verbose
        self._recorder = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._stats = STTStats(
            engine_name=engine_name,
            model_name=model_name,
        )
        self._lock = threading.Lock()
        self._recording_start_time: float = 0.0
        self._recording_active = False

    def _notify_transcription(self, result: STTResult) -> None:
        """Notify transcription callback (handles async callbacks safely)."""
        # Store in queue for sync access
        with self._queue_lock:
            self._transcription_queue.append(result)
        # Call callback if provided
        if self._on_transcription:
            try:
                import asyncio
                loop = None
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    pass
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self._on_transcription(result), loop
                    )
                else:
                    # No running loop — call directly (sync callback)
                    import inspect
                    if inspect.iscoroutinefunction(self._on_transcription):
                        # Can't run async without a loop — skip
                        logger.warning("Async transcription callback but no event loop")
                    else:
                        self._on_transcription(result)
            except Exception:
                logger.exception("Failed to notify transcription callback")

    @property
    def stats(self) -> STTStats:
        with self._lock:
            return STTStats(**self._stats.__dict__)

    @property
    def state(self) -> STTState:
        return self._stats.state

    def _on_recording_start(self) -> None:
        """Callback: audio recording started."""
        self._recording_start_time = time.time()
        self._recording_active = True
        if self._verbose:
            logger.info("STT recording started")

    def _on_recording_stop(self) -> None:
        """Callback: audio recording stopped."""
        if self._recording_active and self._verbose:
            duration = time.time() - self._recording_start_time
            logger.info("STT recording stopped (duration: %.2fs)", duration)
        self._recording_active = False

    def _on_vad_start(self) -> None:
        """Callback: voice activity detected."""
        if self._verbose:
            logger.info("STT voice activity detected (VAD start)")

    def _on_vad_stop(self) -> None:
        """Callback: voice activity ended."""
        if self._verbose:
            logger.info("STT voice activity ended (VAD stop)")

    def _on_vad_detect_start(self) -> None:
        """Callback: VAD detection began."""
        if self._verbose:
            logger.info("STT VAD detection started")

    def _on_vad_detect_stop(self) -> None:
        """Callback: VAD detection ended."""
        if self._verbose:
            logger.info("STT VAD detection ended")

    def _on_transcription_start(self, audio_data: bytes | None = None) -> None:
        """Callback: transcription began."""
        if self._verbose:
            duration = 0.0
            if audio_data is not None and len(audio_data) > 0:
                duration = len(audio_data) / (16000 * 2)  # 16kHz, 16-bit
            logger.info("STT transcription started (audio duration: %.2fs)", duration)

    def _on_realtime_transcription_update(self, text: str) -> None:
        """Callback: realtime transcription partial update."""
        if self._verbose:
            logger.debug("STT realtime update: '%s'", text)

    def _on_realtime_transcription_stabilized(self, text: str) -> None:
        """Callback: realtime transcription stabilized (finalized)."""
        if self._verbose:
            logger.info("STT realtime stabilized: '%s'", text)

    def _on_recorded_chunk(self, audio_data: bytes) -> None:
        """Callback: audio chunk recorded."""
        # Commented out — too verbose (fires every ~30ms)
        # if self._verbose:
        #     duration = len(audio_data) / (16000 * 2)  # 16kHz, 16-bit
        #     logger.debug("STT audio chunk: %d bytes (%.2fs)", len(audio_data), duration)

    def start(self) -> None:
        """Start the STT engine (blocking call — runs in background thread)."""
        try:
            import RealtimeSTT  # noqa: F401
        except ImportError:
            logger.error(
                "RealtimeSTT not installed. Install with: "
                "pip install RealtimeSTT[faster-whisper]",
            )
            return

        if self._engine_name == "whisper_cpp":
            logger.warning(
                "whisper_cpp engine is known to segfault on Windows due to "
                "pywhispercpp native library incompatibility (BEX64 access "
                "violation). Use 'faster_whisper' instead.",
            )

        try:
            self._recorder = RealtimeSTT.AudioToTextRecorder(
                transcription_engine=self._engine_name,
                model=self._model_name,
                device="cpu",
                enable_realtime_transcription=True,
                realtime_model_type="tiny",
                beam_size_realtime=1,
                download_root=self._model_dir or "",
                silero_backend=None,
                # Disable halo spinner — we use our own logging
                spinner=False,
                level=logging.WARNING,
                # Hook up verbose callbacks
                on_recording_start=self._on_recording_start,
                on_recording_stop=self._on_recording_stop,
                on_vad_start=self._on_vad_start,
                on_vad_stop=self._on_vad_stop,
                on_vad_detect_start=self._on_vad_detect_start,
                on_vad_detect_stop=self._on_vad_detect_stop,
                on_transcription_start=self._on_transcription_start,
                on_realtime_transcription_update=self._on_realtime_transcription_update,
                on_realtime_transcription_stabilized=self._on_realtime_transcription_stabilized,
                on_recorded_chunk=self._on_recorded_chunk,
            )
        except Exception:
            logger.exception("Failed to initialize RealtimeSTT recorder")
            with self._lock:
                self._stats.state = STTState.IDLE
            return

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def start_recording(self) -> None:
        """Start audio recording for transcription (non-blocking)."""
        if self._recorder is None:
            raise RuntimeError("STT engine not initialized. Call start() first.")
        if self._recording_active:
            raise RuntimeError("Already recording")
        try:
            self._recorder.start()  # type: ignore[union-attr]
            with self._lock:
                self._stats.state = STTState.LISTENING
        except Exception:
            logger.exception("Failed to start recording")
            raise RuntimeError("Failed to start recording")

    def stop_recording(self) -> None:
        """Stop audio recording (non-blocking). Engine remains ready."""
        if self._recorder is None:
            raise RuntimeError("STT engine not initialized")
        if not self._recording_active:
            raise RuntimeError("Not currently recording")
        try:
            self._recorder.stop()  # type: ignore[union-attr]
            with self._lock:
                self._stats.state = STTState.IDLE
        except Exception:
            logger.exception("Failed to stop recording")
            raise RuntimeError("Failed to stop recording")

    def reconfigure(self, engine_name: str, model_name: str) -> tuple[bool, str]:
        """Reconfigure STT engine with new engine/model.

        Stops recording, shuts down recorder, recreates with new params,
        restarts engine in idle state.

        Args:
            engine_name: New engine name (e.g. "faster_whisper").
            model_name: New model name (e.g. "base.en").

        Returns:
            (success, message) tuple.
        """
        with self._lock:
            # Save previous config for rollback
            prev_engine = self._engine_name
            prev_model = self._model_name

            # Stop recording if active
            if self._recording_active and self._recorder:
                try:
                    self._recorder.stop()  # type: ignore[union-attr]
                except Exception:
                    pass
                self._recording_active = False

            # Shut down recorder
            if self._recorder:
                try:
                    self._recorder.shutdown()
                except Exception:
                    pass
                self._recorder = None

            # Update config
            self._engine_name = engine_name
            self._model_name = model_name

            # Try to recreate recorder
            try:
                self._recorder = RealtimeSTT.AudioToTextRecorder(
                    transcription_engine=self._engine_name,
                    model=self._model_name,
                    device="cpu",
                    enable_realtime_transcription=True,
                    realtime_model_type="tiny",
                    beam_size_realtime=1,
                    download_root=self._model_dir or "",
                    silero_backend=None,
                    spinner=False,
                    level=logging.WARNING,
                    on_recording_start=self._on_recording_start,
                    on_recording_stop=self._on_recording_stop,
                    on_vad_start=self._on_vad_start,
                    on_vad_stop=self._on_vad_stop,
                    on_vad_detect_start=self._on_vad_detect_start,
                    on_vad_detect_stop=self._on_vad_detect_stop,
                    on_transcription_start=self._on_transcription_start,
                    on_realtime_transcription_update=self._on_realtime_transcription_update,
                    on_realtime_transcription_stabilized=self._on_realtime_transcription_stabilized,
                    on_recorded_chunk=self._on_recorded_chunk,
                )
                self._stats.engine_name = engine_name
                self._stats.model_name = model_name
                self._stats.state = STTState.IDLE
                return True, f"Reconfigured to {engine_name}/{model_name}"
            except Exception:
                logger.exception("Failed to recreate recorder with new config")
                # Rollback
                self._engine_name = prev_engine
                self._model_name = prev_model
                self._stats.engine_name = prev_engine
                self._stats.model_name = prev_model
                return False, f"Failed to reconfigure to {engine_name}/{model_name}"

    def stop(self) -> None:
        """Stop the STT engine."""
        self._running = False
        if self._recorder:
            self._recorder.shutdown()
            self._recorder = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        with self._lock:
            self._stats.state = STTState.IDLE

    def transcribe_chunk(self, audio_data: bytes, sample_rate: int = 16000) -> STTResult:
        """Transcribe a single audio chunk (non-streaming mode).

        Note: RealtimeSTT's text() method blocks in streaming mode.
        This method uses a timeout to avoid hanging.
        """
        if self._recorder is None:
            return STTResult(text="", is_final=True, realtime=False)
        try:
            self._recorder.feed_audio(audio_data, sample_rate)
            # Use a short timeout to avoid blocking indefinitely
            import threading
            result = [None]
            event = threading.Event()

            def get_text():
                try:
                    result[0] = self._recorder.text()  # type: ignore[union-attr]
                except Exception:
                    result[0] = ""
                event.set()

            thread = threading.Thread(target=get_text, daemon=True)
            thread.start()
            event.wait(timeout=2.0)

            if result[0] is None:
                return STTResult(text="", is_final=True, realtime=False)
            return STTResult(
                text=result[0] or "",
                is_final=True,
                realtime=False,
            )
        except Exception:
            logger.exception("transcribe_chunk failed")
            return STTResult(text="", is_final=True, realtime=False)

    def _listen_loop(self) -> None:
        """Background loop that listens for speech and calls the transcription callback."""
        with self._lock:
            self._stats.state = STTState.LISTENING

        while self._running and self._recorder:
            try:
                text = self._recorder.text()
                if text:
                    with self._lock:
                        self._stats.last_text = text
                        self._stats.last_is_final = True
                        self._stats.transcription_count += 1
                    if self._on_transcription:
                        self._notify_transcription(STTResult(
                            text=text,
                            is_final=True,
                            realtime=False,
                        ))
            except Exception:
                logger.exception("STT transcription error")
                break

        with self._lock:
            self._stats.state = STTState.IDLE

    def shutdown(self) -> None:
        """Alias for stop() — cleanup."""
        self.stop()


def download_model(model_name: str = "tiny", download_root: str | None = None) -> Path:
    """Download a faster-whisper model file. Returns path to downloaded model.

    Args:
        model_name: Model identifier (e.g. ``"tiny"``, ``"base"``).
        download_root: Directory to download the model to. Defaults to cache dir.

    Returns:
        Path to the downloaded model directory.
    """
    try:
        from faster_whisper.utils import download_model as fw_download  # noqa: F401
    except ImportError:
        raise ImportError(
            "faster_whisper not installed. Install with: pip install faster-whisper"
        )

    if download_root:
        Path(download_root).mkdir(parents=True, exist_ok=True)
        return fw_download(model_name, model_dir=download_root)
    else:
        return fw_download(model_name)
