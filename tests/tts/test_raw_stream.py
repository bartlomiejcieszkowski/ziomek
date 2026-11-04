"""Tests for the raw output stream backends."""

import io
import threading
from unittest.mock import patch

import numpy as np
import soundfile as sf

from ziomek.tts.backends.raw_stream import (
    RawStreamBackend,
    RawStreamOverlapBackend,
    Timeline,
    scale_to_edge,
)


def wav_bytes(samples, rate):
    """Encode samples as a sound file, keeping the values as they are."""
    buffer = io.BytesIO()
    sf.write(buffer, samples, rate, format="WAV", subtype="FLOAT")
    return buffer.getvalue()


class FakeStream:
    """A stream that reports how many samples it can take and records what it was given."""

    def __init__(self, recorder, available):
        self._recorder = recorder
        self._available = available

    @property
    def write_available(self):
        return self._available

    def write(self, data):
        self._recorder.append(("write", len(data), threading.current_thread().name))

    def stop(self):
        self._recorder.append(("stop", None, threading.current_thread().name))

    def make_available(self, count):
        self._available = count


def test_the_samples_are_read_as_mono_float32_at_the_rate_they_were_written_at():
    from ziomek.tts.backends.raw_stream import read_samples

    stereo = np.array([[0.5, 0.1], [0.3, 0.9]], dtype=np.float32)
    samples, rate = read_samples(wav_bytes(stereo, 24000))
    assert rate == 24000
    assert samples.dtype == np.float32
    np.testing.assert_allclose(samples, [(0.5 + 0.1) / 2, (0.3 + 0.9) / 2])


def test_the_stream_is_opened_at_the_rate_the_samples_were_read_at():
    recorder = []
    with patch("sounddevice.RawOutputStream", side_effect=lambda *a, **k: FakeStream(recorder, 8)) as opened:
        RawStreamBackend().play(wav_bytes(np.array([0.1], dtype=np.float32), 24000), 24000)
    assert opened.call_args.kwargs["samplerate"] == 24000
    assert opened.call_args.kwargs["dtype"] == "float32"


def test_an_unavailable_stream_is_reported_instead_of_playing_through_another_path():
    # The name in the config is the path the audio went through, so a stream that cannot be opened
    # is reported rather than handed to another backend.
    recorder = []
    with patch("sounddevice.RawOutputStream", side_effect=RuntimeError("no device")):
        with patch("sounddevice.play") as played:
            RawStreamBackend().play(wav_bytes(np.array([0.1], dtype=np.float32), 24000), 24000)
            RawStreamOverlapBackend().mix_play(wav_bytes(np.array([0.2], dtype=np.float32), 24000), 24000)
    assert played.called is False
    assert recorder == []


def test_stop_is_called_only_after_every_chunk_has_been_written():
    # Stopping before the device has taken the samples is what cuts the end of a sound, so the
    # writer takes what it can and stops only when nothing is left.
    recorder = []
    stream = FakeStream(recorder, 2)
    with patch("sounddevice.RawOutputStream", side_effect=lambda *a, **k: stream):
        RawStreamBackend().play(wav_bytes(np.ones(5, dtype=np.float32), 24000), 24000)
    chunks = [entry for entry in recorder if entry[0] == "write"]
    assert [entry[1] for entry in chunks] == [8, 8, 4]
    assert recorder[-1][0] == "stop"


def test_a_second_sound_waits_for_the_first_in_the_queue_form():
    # The lock held while a sound is written is what keeps one sound at a time on the stream.
    recorder = []
    gate = threading.Event()
    wrote_first = threading.Event()

    class GatedStream(FakeStream):
        def write(self, data):
            name = threading.current_thread().name
            self._recorder.append(("write", len(data), name))
            if name == "first":
                wrote_first.set()
            gate.wait(2)

    backend = RawStreamBackend()
    with patch("sounddevice.RawOutputStream", side_effect=lambda *a, **k: GatedStream(recorder, 4)):
        first = threading.Thread(
            target=lambda: backend.play(wav_bytes(np.ones(1, dtype=np.float32), 24000), 24000), name="first"
        )
        second = threading.Thread(
            target=lambda: backend.play(wav_bytes(np.ones(1, dtype=np.float32), 24000), 24000), name="second"
        )
        first.start()
        assert wrote_first.wait(2)
        second.start()
        # The first sound still holds the lock, so the second cannot write yet.
        assert [entry[2] for entry in recorder] == ["first"]
        gate.set()
        first.join(2)
        second.join(2)

    assert [entry[0] for entry in recorder] == ["write", "stop", "write", "stop"]
    assert [entry[2] for entry in recorder] == ["first", "first", "second", "second"]


def test_a_second_sound_is_added_at_its_position_in_the_shared_timeline():
    timeline = Timeline()
    timeline.add(np.array([0.4, 0.4], dtype=np.float32))
    timeline.add(np.array([0.1], dtype=np.float32))
    np.testing.assert_allclose(np.frombuffer(timeline.take(2), dtype=np.float32), [0.5, 0.4])
    assert timeline.pending() == 0


def test_a_sum_that_passes_the_edge_is_scaled_by_the_peak_of_that_region():
    # Scaling the region rather than clipping keeps the shape of both sounds.
    timeline = Timeline()
    timeline.add(np.array([0.8], dtype=np.float32))
    timeline.add(np.array([0.8], dtype=np.float32))
    np.testing.assert_allclose(np.frombuffer(timeline.take(1), dtype=np.float32), [1.0])


def test_a_single_sound_inside_the_edge_keeps_its_level():
    samples = np.array([0.5, 0.25], dtype=np.float32)
    np.testing.assert_allclose(scale_to_edge(samples), samples)


def test_the_summing_path_returns_while_the_device_is_still_taking_samples():
    recorder = []
    stream = FakeStream(recorder, 0)
    with patch("sounddevice.RawOutputStream", side_effect=lambda *a, **k: stream):
        backend = RawStreamOverlapBackend()
        backend.mix_play(wav_bytes(np.array([0.2], dtype=np.float32), 24000), 24000)
        # Nothing was written yet, so the call returned while the samples were still pending.
        assert recorder == []
        stream.make_available(4)
        backend._writer._thread.join(2)

    assert [entry[0] for entry in recorder] == ["write", "stop"]


def test_the_queue_form_reports_no_mixing_and_the_summing_form_reports_mixing():
    assert RawStreamBackend().supports_mixing is False
    assert RawStreamOverlapBackend().supports_mixing is True


class SilentThenSpaceStream(FakeStream):
    """A stream that reports no space until it has begun taking samples, as a stream can do."""

    def __init__(self, recorder, silent_reads, space, consume_on_write=False):
        super().__init__(recorder, 0)
        self._silent_reads = silent_reads
        self._space = space
        self._consume_on_write = consume_on_write

    @property
    def write_available(self):
        if self._silent_reads > 0:
            self._silent_reads -= 1
            return 0
        return self._space

    def write(self, data):
        self._recorder.append(("write", len(data), threading.current_thread().name))
        if self._consume_on_write:
            # Space only comes back as the device plays, so a stream keeps less of it while samples
            # are still with the device.
            self._space -= len(data) // 4

    def make_available(self, count):
        # Freeing space here means the same thing as the device having taken the samples.
        self._space = count


def test_a_stream_that_reports_no_space_at_first_still_writes_every_sample():
    # A stream that shows nothing at the start is not a reason to stop writing, so the samples are
    # handed over as soon as it shows space.
    recorder = []
    stream = SilentThenSpaceStream(recorder, silent_reads=2, space=2)  # nothing is taken back yet, so the space stays
    timeline = Timeline()
    timeline.add(np.ones(5, dtype=np.float32))
    from ziomek.tts.backends.raw_stream import pump

    space = pump(stream, timeline)
    chunks = [entry for entry in recorder if entry[0] == "write"]
    assert [entry[1] for entry in chunks] == [8, 8, 4]
    assert timeline.pending() == 0
    assert space == 2


def test_the_wait_is_for_the_space_measured_when_the_first_sample_was_written():
    # A stream that shows no space until it starts cannot be waited for by its value at open, which
    # is nothing, so the wait has to use the space measured at the point of writing.
    from ziomek.tts.backends.raw_stream import pump, wait_for_device

    recorder = []
    stream = SilentThenSpaceStream(recorder, silent_reads=1, space=3, consume_on_write=True)
    timeline = Timeline()
    timeline.add(np.ones(2, dtype=np.float32))
    space = pump(stream, timeline)
    assert space == 3

    finished = threading.Event()
    thread = threading.Thread(target=lambda: (wait_for_device(stream, space), finished.set()))
    thread.start()
    assert finished.wait(0.5) is False
    # The device has taken the samples, so the space measured at the first write is free again.
    stream.make_available(3)
    assert finished.wait(2)
