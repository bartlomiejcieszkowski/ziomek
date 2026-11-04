"""The page served in dev mode states what it measured; the page without it does not."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ziomek import dev_mode, server


def page_source():
    """The page without the debug part, as stored."""
    return (Path(__file__).parent.parent / "src" / "ziomek" / "resources" / "roster.html").read_text(encoding="utf-8")


def debug_page_source():
    """The page served in dev mode, as stored."""
    return (Path(__file__).parent.parent / "src" / "ziomek" / "resources" / "roster_debug.html").read_text(
        encoding="utf-8"
    )


@pytest.fixture(autouse=True)
def no_reader_yet():
    """The flag is one flag, so a test must not inherit it from another."""
    dev_mode.set_dev_mode(False)
    yield
    dev_mode.set_dev_mode(False)


@pytest.fixture
def client_with_dev():
    from ziomek.config import Settings

    app = server.create_app(Settings(no_gamepad=True), dev_mode=True)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_without_dev():
    app = server.create_app(dev_mode=False)
    with TestClient(app) as c:
        yield c


def test_the_page_that_draws_tiles_has_no_way_to_state_values_on_its_own():
    """The rules that draw a tile are the page; stating what was measured is only asked for in dev mode."""
    page = page_source()
    assert "let state_sizes = null;" in page
    assert "REPORT_PATH" not in page


def test_the_debug_page_is_the_page_with_only_its_own_part_added():
    """The debug page must draw tiles the same way as the page, so it is the page plus a part that only states values."""
    page = page_source()
    head, part = debug_page_source().split("/* the debug part */")
    assert head == page.split("setShown(panelOpen());")[0]
    assert "fetch(REPORT_PATH" in part and ".tile {" not in part
    assert "setShown(panelOpen());" in debug_page_source()


def test_the_part_added_in_dev_mode_states_values_before_the_page_starts():
    """A part added after the page runs would miss the values of the first render."""
    debug = debug_page_source()
    assert debug.index("/* the debug part */") < debug.index("setShown(panelOpen());")


def test_the_page_asks_for_the_values_to_be_stated_after_dividing():
    """A page that cannot state values on its own still names what it measured, so the part added in dev mode can carry it."""
    page = page_source()
    assert 'state_sizes?.("measured", room, parts, frame, frames);' in page
    assert 'state_sizes?.("cannot be measured", room, null, null, null);' in page
    guard = page.split("function apply_largest_tile(")[1].split("if (!frame) {")[1].split("}")[0]
    assert 'state_sizes?.("no frame size was read for these skins", room, parts, null, null);' in guard
    assert "return;" in guard

    body = page.split("function apply_largest_tile(")[1]
    assert body.index("stated_blocks = measure_blocks(frame, room, parts);") < body.index('state_sizes?.("measured"')


def test_the_part_added_in_dev_mode_sends_what_it_was_asked_to_state():
    """The values only exist in the browser, so the part sends them to the debug path."""
    part = debug_page_source().partition("/* the debug part */")[2]
    assert 'fetch(REPORT_PATH, { method: "POST"' in part


def test_each_block_is_stated_with_the_size_its_own_tile_was_given():
    """A page that drew blocks of different sizes cannot describe them with one value."""
    part = debug_page_source().partition("/* the debug part */")[2]
    assert "blocks: describe_blocks()," in part
    assert (
        "{ row: block.row, col: block.col, rows: block.rowSpan, cols: block.colSpan, "
        "tile: tile_size(frame, block.colSpan * (room.width / parts.cols), block.rowSpan * (room.height / parts.rows)) }"
        in page_source()
    )


def test_a_page_that_drew_the_whole_grid_as_one_block_states_no_blocks():
    """One block is the whole grid, which the cell part already states, so nothing is added for it."""
    part = debug_page_source().partition("/* the debug part */")[2]
    assert (
        "if (stated_blocks.length < 2) return null;  // one block is the whole grid, which the cell part already states"
        in part
    )


def test_a_report_that_changed_nothing_is_not_sent_again():
    """The page asks for values on every render, so the same values would be sent on every poll."""
    part = debug_page_source().partition("/* the debug part */")[2]
    assert "if (text === last_report) return;" in part


def test_a_participant_with_no_block_is_not_drawn():
    """The room can only be divided so far. Past that a participant has no block, and nothing is drawn for them rather than a placeholder."""
    for source in (page_source(), debug_page_source()):
        assert (
            "if (!place) continue;  // the room cannot be divided further, so this participant has no block" in source
        )


def test_the_roster_page_answers_with_the_page_without_the_debug_part(client_without_dev):
    """Without dev mode nothing can be told back, so a page that states values has no reader."""
    resp = client_without_dev.get("/roster")
    assert resp.status_code == 200
    assert "REPORT_PATH" not in resp.text


def test_the_roster_page_answers_with_the_debug_page_in_dev_mode(client_with_dev):
    """The debug paths are open only in dev mode, so the page that states values is served only there."""
    resp = client_with_dev.get("/roster")
    assert resp.status_code == 200
    assert 'fetch(REPORT_PATH, { method: "POST"' in resp.text


def test_a_page_that_states_values_has_no_reader_when_the_server_runs_without_dev_mode(client_without_dev):
    """A page that posts to a path the server did not open would state values nothing can read, so both answer from one flag."""
    assert client_without_dev.post("/api/debug/render", json={"path": "measured"}).status_code == 404
    assert "state_sizes = function" not in client_without_dev.get("/roster").text


def test_the_page_that_states_values_and_the_path_that_answers_it_open_together(client_with_dev):
    """The page that states values and the path that reads them are opened by the same flag."""
    assert client_with_dev.post("/api/debug/render", json={"path": "measured"}).status_code == 200
    assert 'fetch(REPORT_PATH, { method: "POST"' in client_with_dev.get("/roster").text
