"""Keep RealtimeSTT's shutdown-time connection error out of the log.

The library's transcription worker closes its connection before joining its own polling
thread, so a poll that is still waiting for the handle raises ``OSError: [WinError 6]`` on
Windows. Joining before closing would be the correct order, but the close happens first —
and nothing we can do from ``ziomek.stt`` changes that order. An error raised while the
worker is already shutting down is therefore expected; every other error must stay visible.

RealtimeSTT spawns its workers, so this patch has to be reachable from inside the child:
``run_transcription_worker`` is referenced through the library module, so replacing it with a
module-level function here is what the spawned process resolves.
"""

from __future__ import annotations

import logging
import time

try:
    from RealtimeSTT.core import initialization, transcription
except ImportError:  # the optional "stt" extra is not installed
    initialization = None
    transcription = None

TIME_SLEEP = 0.02

logger = logging.getLogger("ziomek.stt")


def poll_connection(self):
    """Transfer pipe messages into the worker queue, treating shutdown as expected."""
    while not self.shutdown_event.is_set():
        try:
            if self.conn.poll(0.01):  # Short poll keeps shutdown responsive.
                data = self.conn.recv()
                self.queue.put(data)
            else:
                time.sleep(TIME_SLEEP)
        except Exception as e:
            if getattr(self.shutdown_event, "is_set", None) and self.shutdown_event.is_set():
                logger.debug("Connection closed during shutdown: %s", e)
                return
            logger.error(f"Error receiving data from connection: {e}", exc_info=True)
            time.sleep(TIME_SLEEP)


def run_transcription_worker(*args, **kwargs):
    """Entry point for the spawned worker process, patched before the worker runs."""
    apply_patch()
    if transcription is not None:
        transcription.run_transcription_worker(*args, **kwargs)


def apply_patch():
    """Replace the worker's poll loop and the entry point used to start it."""
    if transcription is None:
        return
    transcription.TranscriptionWorker.poll_connection = poll_connection
    if initialization is not None:
        initialization.run_transcription_worker = run_transcription_worker
