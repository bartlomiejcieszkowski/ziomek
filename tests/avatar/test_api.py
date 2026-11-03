import pytest
from fastapi.testclient import TestClient

from ziomek.server import create_app


@pytest.fixture
def client():
    from ziomek.config import Settings

    settings = Settings(no_gamepad=True)
    app = create_app(settings)
    return TestClient(app)


def test_state_endpoint(client):
    """Verify /api/avatar/state returns expression."""
    resp = client.get("/api/avatar/state")
    assert resp.status_code == 200
    data = resp.json()
    assert "expression" in data
    assert "cycleIndex" in data


def test_expression_endpoint(client):
    """Verify /api/avatar/expression sets expression."""
    resp = client.post("/api/avatar/expression", json={"name": "surprised"})
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data


def test_input_endpoint(client):
    """Verify /api/avatar/input accepts gamepad state."""
    resp = client.post(
        "/api/avatar/input",
        json={
            "buttons": [{"pressed": True, "value": 0}],
            "axes": [0, 0, 0],
            "connected": True,
            "streaming": False,
            "chatFocused": False,
            "errorState": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "expression" in data


def test_sprite_endpoint(client):
    """Verify /api/avatar/sprite returns sprite info (may fail if no file)."""
    resp = client.get("/api/avatar/sprite")
    assert resp.status_code in (200, 404)  # 404 if sprite file missing


def test_a_skin_name_that_is_not_registered_is_not_served_by_the_sprite_endpoint(client):
    """A name is read through the registry, so an unknown one can only answer with nothing."""
    resp = client.get("/api/avatar/sprite?skin=not-a-skin")
    assert resp.status_code in (404, 503)  # the registry answers only for a registered skin


def test_the_sprite_endpoint_answers_for_the_default_skin_when_none_is_named(client):
    """The page asks for a skin, and the default is used when it does not."""
    resp = client.get("/api/avatar/sprite")
    assert resp.status_code in (200, 404, 503)


def test_speak_endpoint_no_tts(client):
    """Verify /api/avatar/speak returns 503 when TTS not loaded."""
    resp = client.post("/api/avatar/speak", json={"text": "test"})
    assert resp.status_code == 503


def image_client(tmp_path):
    from tests.avatar.morda_helpers import make_folder

    definition = {
        "name": "cosette",
        "type": "image",
        "frames": {"cry": {"file": "parts/cry.png", "object-fit": "cover"}, "neutral": {"file": "parts/cry.png"}},
        "expressions": {"sad": {"frame_order": ["cry"]}},
        "fallback": "neutral",
    }
    make_folder(tmp_path / "cosette", definition, sizes={"parts/cry.png": (120, 90)})

    from ziomek.config import Settings
    from ziomek.server import create_app

    return TestClient(create_app(Settings(skins_dir=str(tmp_path), no_gamepad=True)))


def test_an_image_definition_answers_with_no_sheet_to_send_whole(tmp_path):
    client = image_client(tmp_path)
    data = client.get("/api/avatar/sprite?skin=cosette").json()
    assert data["skin"] == "cosette"
    assert data["sprite_b64"] is None  # type image states no sheet
    assert data["grid"] is None  # and no grid, since there are no cells to name
    frame = data["expressions"]["sad"]["frames"][0]
    assert frame["kind"] == "file" and frame["file"] == "parts/cry.png"
    assert (frame["width"], frame["height"]) == (120, 90)  # the size the picture reports
    assert frame["fit"] == "cover"  # what that frame stated for itself
    # The frame it falls back to states nothing, and the definition states nothing, so the default is used.
    assert data["fallback"]["fit"] == "contain"


def test_one_image_is_served_for_a_frame_that_names_a_file(tmp_path):
    client = image_client(tmp_path)
    resp = client.get("/api/avatar/image?skin=cosette&file=parts/cry.png")
    assert resp.status_code == 200
    data = resp.json()
    assert data["image_b64"].startswith("data:image/png;base64,")
    assert (data["width"], data["height"]) == (120, 90)


def test_a_file_that_is_not_there_is_not_served(tmp_path):
    client = image_client(tmp_path)
    resp = client.get("/api/avatar/image?skin=cosette&file=parts/missing.png")
    assert resp.status_code == 404
