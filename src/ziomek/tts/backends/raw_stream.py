"""ziomek TTS audio backends — raw output streams that write what the device takes."""

import io
import logging
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

from .base import IBackend

logger = logging.getLogger(__name__)

POLL_SECONDS = 0.01  # how often the device is asked whether it has taken the samples
WRITE_STUCK_SECONDS = 1.0  # how long a stream may show no space to write into before it is reported
PLAY_STUCK_SECONDS = 5.0  # how long a stream may hold samples it has taken before it is reported


def read_samples(data: bytes) -> tuple[np.ndarray, int]:
    """Read a sound as mono float32 samples, and report the rate it was read at.

    Raw data is not converted by the library, so what is written to an output stream must already be
    mono float32 samples at the rate the stream was opened at. That is why reading happens here
    rather than being left to the caller: the rate carried by the samples is what the stream uses.
    """
    samples, rate = sf.read(io.BytesIO(data), dtype="float32")
    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    return samples, int(rate)


def scale_to_edge(samples: np.ndarray) -> np.ndarray:
    """Scale a summed region when it would pass the edge, by the peak of that region.

    A region that stays inside full scale is left as it is, so a single sound keeps its level. Only
    the part still pending can change here, because samples already handed to the device cannot be
    changed again. Clipping stays as the guard at the edge, not as the rule.
    """
    if len(samples) == 0:
        return samples
    peak = float(np.max(np.abs(samples)))
    if peak <= 1.0:
        return samples
    return samples * (1.0 / peak)


class Timeline:
    """Samples waiting to be written, summed at the position where they are heard."""

    def __init__(self) -> None:
        self._pending = np.zeros(0, dtype=np.float32)

    def add(self, samples: np.ndarray) -> None:
        """Add a sound at the position where the next samples would be written."""
        length = max(len(self._pending), len(samples))
        if length == 0:
            return
        summed = np.zeros(length, dtype=np.float32)
        summed[: len(self._pending)] += self._pending
        summed[: len(samples)] += samples
        self._pending = scale_to_edge(summed)

    def take(self, count: int) -> bytes:
        """Return the next samples as raw bytes, and forget them."""
        chunk, self._pending = self._pending[:count], self._pending[count:]
        return chunk.tobytes()

    def pending(self) -> int:
        return len(self._pending)


def open_stream(rate: int):
    """Open a stream, or report that this path cannot be used and give up.

    It is reported rather than falling back to another path, so a test in prod stays answerable: the
    name you chose is the path the audio went through.
    """
    try:
        return sd.RawOutputStream(samplerate=rate, channels=1, dtype="float32")
    except Exception as exc:
        logger.error("cannot open an output stream at %s: %s", rate, exc)
        return None


def write_available(stream) -> int:
    try:
        return int(stream.write_available)
    except Exception:
        return 0


def measure_space(stream) -> int:
    """Report the space the stream can hold, or nothing when it has not shown any yet.

    A stream can report no space before it starts, so the space is only known at the point where the
    first sample is written. Measuring it at open would compare against nothing and let a stop come
    before the device has taken the samples.
    """
    return write_available(stream)


def pump(stream, timeline: Timeline, rate: int) -> int:
    """Hand over what the device takes until nothing is left pending, and report the space measured at the first write.

    A stream that shows no space for WRITE_STUCK_SECONDS cannot be written to, so it is reported rather
    than waited on forever: a sound that can never be handed over has no end to wait for. The write side
    gets the shorter limit because a stream that will not take anything shows that at once, while playing
    what was taken takes longer and a long wait there is normal.
    """
    space = 0
    waited = time.monotonic()
    while timeline.pending() > 0:
        available = write_available(stream)
        if space == 0:
            space = measure_space(stream)
        take = min(available, timeline.pending())
        if take <= 0:
            if time.monotonic() - waited >= WRITE_STUCK_SECONDS:
                logger.error(
                    "the stream for %s showed no space for %s seconds, so nothing was written",
                    rate,
                    WRITE_STUCK_SECONDS,
                )
                return 0
            time.sleep(POLL_SECONDS)
            continue
        stream.write(timeline.take(take))
        # Space came back after this write, so the stream is taking samples and is not stuck.
        waited = time.monotonic()
    return space


def wait_for_device(stream, capacity: int, rate: int) -> None:
    """Wait until the space measured at the first write is free again.

    Space a stream reports as free again is the space it has already played, so this is what keeps a
    stop from cutting the end of a sound. With nothing measured there is nothing to wait for, so a
    stream that never took a sample is not held here. A stream that holds samples for PLAY_STUCK_SECONDS
    is reported, because that end will not come.
    """
    waited = time.monotonic()
    while write_available(stream) < capacity:
        if time.monotonic() - waited >= PLAY_STUCK_SECONDS:
            logger.error(
                "the stream for %s kept %s samples for more than %s seconds, so its end is not waited for",
                rate,
                capacity - write_available(stream),
                PLAY_STUCK_SECONDS,
            )
            return
        time.sleep(POLL_SECONDS)


class _RawStreamBackend(IBackend):
    """Shared parts of the two raw stream forms: one stream, one reading path."""

    def __init__(self) -> None:
        self._timeline = Timeline()

    def list_devices(self) -> list[dict]:
        try:
            found = sd.query_devices()
            return [
                {
                    "id": i,
                    "name": d["name"] if isinstance(d, dict) else d.name,
                    "channels": d["channels_out"] if isinstance(d, dict) else d.max_output_channels,
                }
                for i, d in enumerate(found)
            ]
        except Exception:
            return []


class RawStreamBackend(_RawStreamBackend):
    """Raw output stream, one sound at a time, so a second sound waits for the first."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()

    @property
    def supports_mixing(self) -> bool:
        return False

    def play(self, data: bytes, sr: int) -> None:
        """Single-shot playback, and the same for a second sound: this form keeps one at a time."""
        samples, rate = read_samples(data)
        self._timeline.add(samples)
        stream = open_stream(rate)
        if stream is None:
            return
        try:
            with self._lock:
                space = pump(stream, self._timeline, rate)
                wait_for_device(stream, space, rate)
        except Exception as exc:
            logger.error("the output stream could not write the samples: %s", exc)
        finally:
            stream.stop()

    def mix_play(self, data: bytes, sr: int) -> None:
        """Called for overlapping playback; this form does not mix, so it keeps the same path."""
        self.play(data, sr)


class _Writer:
    """One thread writing one shared timeline to one stream."""

    def __init__(self, timeline: Timeline) -> None:
        self._timeline = timeline
        self._thread: threading.Thread | None = None
        self._drained = threading.Event()

    def start(self, rate: int) -> None:
        if self._thread is not None:
            return
        self._drained.clear()
        self._thread = threading.Thread(target=self._run, args=(rate,), daemon=True)
        self._thread.start()

    def _run(self, rate: int) -> None:
        stream = open_stream(rate)
        if stream is None:
            self._drained.set()
            return
        space = 0
        waiting_to_write = time.monotonic()
        waiting_to_play = time.monotonic()
        try:
            while True:
                available = write_available(stream)
                if space == 0:
                    space = measure_space(stream)
                take = min(available, self._timeline.pending())
                if take > 0:
                    stream.write(self._timeline.take(take))
                    waiting_to_write = time.monotonic()
                    continue
                if self._timeline.pending() == 0 and write_available(stream) >= space:
                    self._drained.set()
                    return
                if self._timeline.pending() > 0 and time.monotonic() - waiting_to_write >= WRITE_STUCK_SECONDS:
                    logger.error(
                        "the stream for %s showed no space for %s seconds, so nothing was written",
                        rate,
                        WRITE_STUCK_SECONDS,
                    )
                    self._drained.set()
                    return
                if time.monotonic() - waiting_to_play >= PLAY_STUCK_SECONDS:
                    logger.error(
                        "the stream for %s kept %s samples for more than %s seconds, so its end is not waited for",
                        rate,
                        space - write_available(stream),
                        PLAY_STUCK_SECONDS,
                    )
                    self._drained.set()
                    return
                time.sleep(POLL_SECONDS)
        except Exception as exc:
            logger.error("the output stream could not write the samples: %s", exc)
            self._drained.set()
        finally:
            stream.stop()

    def wait(self) -> None:
        self._drained.wait()


class RawStreamOverlapBackend(_RawStreamBackend):
    """Raw output stream where samples are summed at the position they are heard at."""

    def __init__(self) -> None:
        super().__init__()
        self._writer = _Writer(self._timeline)

    @property
    def supports_mixing(self) -> bool:
        return True

    def play(self, data: bytes, sr: int) -> None:
        """Single-shot playback: wait until the device has taken every sample."""
        samples, rate = read_samples(data)
        self._timeline.add(samples)
        self._writer.start(rate)
        self._writer.wait()

    def mix_play(self, data: bytes, sr: int) -> None:
        """Overlapping playback: add at the position, then return while the device is still taking."""
        samples, rate = read_samples(data)
        self._timeline.add(samples)
        self._writer.start(rate)
