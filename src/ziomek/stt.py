"""ziomek STT — speech-to-text using RealtimeSTT."""

from __future__ import annotations

import enum
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

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
    model_name: str = "tiny.en"
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
        model_name: Model identifier (e.g. ``"tiny.en"``, ``"base.en"``).
        model_dir: Optional download root / model directory.
        on_transcription: Callback invoked with each :class:`STTResult`.
    """

    def __init__(
        self,
        engine_name: str = "faster_whisper",
        model_name: str = "tiny.en",
        model_dir: str | None = None,
        on_transcription: Callable[[STTResult], None] | None = None,
    ) -> None:
        self._engine_name = engine_name
        self._model_name = model_name
        self._model_dir = model_dir
        self._on_transcription = on_transcription
        self._recorder = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._stats = STTStats(
            engine_name=engine_name,
            model_name=model_name,
        )
        self._lock = threading.Lock()

    @property
    def stats(self) -> STTStats:
        with self._lock:
            return STTStats(**self._stats.__dict__)

    @property
    def state(self) -> STTState:
        return self._stats.state

    def start(self) -> None:
        """Start the STT engine (blocking call — runs in background thread)."""
        try:
            from RealtimeSTT import AudioToTextRecorder  # noqa: F401
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
            self._recorder = AudioToTextRecorder(
                transcription_engine=self._engine_name,
                model=self._model_name,
                device="cpu",
                enable_realtime_transcription=True,
                realtime_model_type="tiny.en",
                beam_size_realtime=1,
                download_root=self._model_dir or "",
                silero_backend=None,
            )
        except Exception:
            logger.exception("Failed to initialize RealtimeSTT recorder")
            return

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

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
        """Transcribe a single audio chunk (non-streaming mode)."""
        if self._recorder is None:
            return STTResult(text="", is_final=True, realtime=False)
        try:
            self._recorder.feed_audio(audio_data, sample_rate)
            return STTResult(
                text=self._recorder.text(),
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
                        self._on_transcription(STTResult(
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


def download_model(model_name: str = "tiny.en", download_root: str | None = None) -> Path:
    """Download a faster-whisper model file. Returns path to downloaded model.

    Args:
        model_name: Model identifier (e.g. ``"tiny.en"``, ``"base.en"``).
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
