"""The roster page shows a tile for each participant in the call."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ziomek.roster as module
from ziomek import server
from ziomek.api.roster_view import router
from ziomek.config import Settings
from ziomek.roster import get_roster


@pytest.fixture(autouse=True)
def fresh_roster():
    module._roster = None
    from ziomek.api import avatar_ws

    avatar_ws._shown = None


def build_app():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_the_roster_view_lists_the_participants_of_the_call():
    client = build_app()
    roster = get_roster()
    first = roster.join("John")
    first.add_text("compiling", author="agent")
    second = roster.join("Donald", voice="bob")
    second.hold()

    tiles = client.get("/api/roster").json()

    assert [tile["name"] for tile in tiles] == ["John", "Donald"]
    assert tiles[0]["status_text"] == "compiling"
    assert tiles[1]["state"] == "held"
    assert [(e["name"], e["action"]) for e in tiles[1]["events"]] == [
        ("Donald", "join"),
        ("Donald", "hold"),
    ]


def test_the_roster_page_renders_a_tile_for_each_participant():
    client = build_app()
    page = client.get("/api/roster/view").text

    # Tiles are built per participant, and the text areas are filled from the tile data.
    assert 'className = "tile"' in page
    assert "status_text" in page


def test_the_roster_page_is_served_by_the_server():
    app = server.create_app(Settings(audio_backend="noop", no_stt=True, no_gamepad=True))
    client = TestClient(app)

    assert client.get("/api/roster").status_code == 200
    assert 'className = "tile"' in client.get("/api/roster/view").text


def test_the_shown_participant_is_rendered_with_its_own_machine(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from ziomek.api import avatar_ws
    from ziomek.roster import Roster

    sent = []

    class fake_ws:
        async def send_json(self, message):
            sent.append(message)

    class own_machine:
        def getCurrentState(self):
            return SimpleNamespace(expressionName="focused", cycleIndex=2)

    ws = fake_ws()
    monkeypatch.setattr(avatar_ws, "_connected_clients", [ws])

    roster = Roster(pool=[("John", "alice")], state_machine_factory=lambda p: own_machine())
    participant = roster.join("John")
    avatar_ws.show(participant)

    asyncio.run(avatar_ws._state_message(ws))

    assert sent[0]["expression"] == "focused"
    assert sent[0]["name"] == "John"


def test_the_roster_uses_the_view_push_as_its_hook():
    from ziomek.api import avatar_ws
    from ziomek.roster import get_roster

    assert get_roster().push_hook is avatar_ws.notify_change
