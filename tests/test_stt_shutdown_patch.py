"""Tests for the RealtimeSTT poll-loop patch.

The library logs an invalid-handle error when its worker closes the connection while the
polling thread is still waiting on it, which is expected during shutdown on Windows.
"""

import logging
import pickle
from typing import Any

import pytest

from ziomek.stt import shutdown_patch


class _FakeEvent:
    """Reports the flag as set only after a fixed number of checks, like the real race."""

    def __init__(self, set_after_checks):
        self._set_after = set_after_checks
        self._checks = 0

    def is_set(self):
        self._checks += 1
        return self._checks > self._set_after


class _FakeQueue:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)

    def __eq__(self, other):
        return self.items == other


class _FakeConnection:
    def __init__(self, error, payloads=()):
        self._error = error
        self._raised = False
        self._payloads = list(payloads)

    def poll(self, timeout):
        if self._error is not None and not self._raised:
            self._raised = True
            raise self._error
        return bool(self._payloads)

    def recv(self):
        return self._payloads.pop(0)


class _FakeWorker:
    def __init__(self, error, set_after_checks, payloads=()):
        self.conn: Any = _FakeConnection(error, payloads)
        self.queue = _FakeQueue()
        self.shutdown_event = _FakeEvent(set_after_checks)


ERROR = OSError("[WinError 6] The handle is invalid")


@pytest.fixture(autouse=True)
def capture_stt_logs(caplog):
    caplog.set_level(logging.DEBUG, logger="ziomek.stt")
    return caplog


class TestPollLoopPatch:
    """The patched poll loop must not report the shutdown error as an error."""

    def test_error_raised_during_shutdown_is_logged_as_debug(self, capture_stt_logs):
        # check 1: loop entered (flag not set), error raises, check 2 during handling sees the flag.
        apply = shutdown_patch.apply_patch
        apply()
        shutdown_patch.poll_connection(_FakeWorker(ERROR, set_after_checks=1))

        assert not [r for r in capture_stt_logs.records if r.levelno == logging.ERROR]
        messages = [r.getMessage() for r in capture_stt_logs.records]
        assert any("Connection closed during shutdown" in m for m in messages)

    def test_error_while_running_is_still_logged_as_error(self, capture_stt_logs):
        # check 1: loop entered, check 2 during handling: still running -> error, check 3 exits.
        shutdown_patch.apply_patch()
        shutdown_patch.poll_connection(_FakeWorker(ERROR, set_after_checks=2))

        assert any(r.levelno == logging.ERROR for r in capture_stt_logs.records)

    def test_messages_still_reach_the_queue(self):
        shutdown_patch.apply_patch()
        # check 1: loop entered, the payload is forwarded, check 2 sees shutdown and exits.
        worker = _FakeWorker(None, set_after_checks=1, payloads=["hello"])
        shutdown_patch.poll_connection(worker)
        assert worker.queue.items == ["hello"]

    def test_poll_connection_is_used_by_the_worker_class(self):
        shutdown_patch.apply_patch()
        from RealtimeSTT.core.transcription import TranscriptionWorker

        assert TranscriptionWorker.poll_connection is shutdown_patch.poll_connection


class TestPatchIsReachableFromTheChildProcess:
    """RealtimeSTT spawns its worker, so the patch must survive pickling by name."""

    def test_run_transcription_worker_resolves_to_our_module(self):
        assert shutdown_patch.run_transcription_worker.__module__ == "ziomek.stt.shutdown_patch"
        loaded = pickle.loads(pickle.dumps(shutdown_patch.run_transcription_worker))
        assert loaded is shutdown_patch.run_transcription_worker

    def test_apply_patch_replaces_the_library_entry_point(self, monkeypatch):
        from RealtimeSTT.core import initialization

        monkeypatch.setattr(initialization, "run_transcription_worker", lambda *a, **k: None)
        shutdown_patch.apply_patch()
        assert initialization.run_transcription_worker is shutdown_patch.run_transcription_worker

    def test_start_applies_the_patch(self, monkeypatch):
        applied = []
        monkeypatch.setattr(shutdown_patch, "apply_patch", lambda: applied.append(True))

        from ziomek.stt import STTEngine

        engine = STTEngine()
        monkeypatch.setattr(STTEngine, "_new_recorder", lambda self: object())
        engine.start_from_file()
        assert applied == [True]
