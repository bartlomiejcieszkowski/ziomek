"""The quiet check runs on the event loop, not only when a tool call arrives."""

import asyncio
import time
from unittest.mock import patch

import pytest

from ziomek.roster import Roster, quiet_check


@pytest.fixture(autouse=True)
def _fresh_call():
    """Each test sees its own call, not the one another test made."""
    import ziomek.roster

    ziomek.roster._roster = None
    yield
    ziomek.roster._roster = None


def test_the_check_drops_a_participant_once_its_quiet_time_passes():
    roster = Roster(pool=[("John A.", "alice")], quiet_for=1)

    async def run():
        participant = roster.join()
        # Only part of the quiet time has passed at the first check.
        participant.last_seen = time.monotonic() - 0.4
        task = asyncio.create_task(quiet_check(roster, interval=0.05))
        await asyncio.sleep(0.1)
        assert roster.participants == [participant]
        await asyncio.sleep(0.6)
        assert roster.participants == []
        task.cancel()

    asyncio.run(run())


def test_the_check_runs_while_the_server_is_running():
    from fastapi.testclient import TestClient

    from ziomek.config import Settings
    from ziomek.server import create_app

    started = []

    async def fake_check(roster, interval):
        started.append((roster, interval))

    settings = Settings(
        no_gamepad=True,
        no_browser=True,
        no_stt=True,
        roster_pool=[("John A.", "alice")],
        roster_quiet_for=5,
        roster_check_interval=0.25,
    )

    with patch("ziomek.server.quiet_check", fake_check):
        app = create_app(settings)
        with TestClient(app) as client:
            client.get("/status")
            assert started

    assert started[0][1] == settings.roster_check_interval
    assert isinstance(started[0][0], Roster)
    assert started[0][0].quiet_for == settings.roster_quiet_for
