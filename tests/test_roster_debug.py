"""The page served in dev mode states what it measured; the page without it does not."""

import pytest
from fastapi.testclient import TestClient

from tests.roster_page_helpers import (
    debug_page_source,
    loaded_parts,
    page_shell,
    page_source,
    served_page,
    static_source,
)
from ziomek import dev_mode, server


def both_pages():
    """The definitions are in the shared part, so a test that checks them reads the page and the part added to it."""
    return page_source() + static_source("roster_debug.js")


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
    own_link = '<script src="/static/roster_debug.js"></script>'
    lines = [line.strip() for line in page_shell("roster_debug.html").splitlines()]
    assert lines.count(own_link) == 1
    assert [line for line in lines if line != own_link] == [line.strip() for line in page_shell().splitlines()]
    assert loaded_parts("roster_debug.html") == loaded_parts() + ["roster_debug.js"]
    part = static_source("roster_debug.js")
    assert "fetch(REPORT_PATH" in part and ".tile {" not in part
    # A part added to a page only states values; the page is the one that starts the view.
    assert "start(" not in part


def test_the_part_added_in_dev_mode_states_values_before_the_page_starts():
    """A part read after the view starts would miss the values of the first render, so the page loads it before it starts."""
    shell = page_shell("roster_debug.html")
    assert shell.index('<script src="/static/roster_debug.js"></script>') < shell.index("start(")
    assert "state_sizes = function" in static_source("roster_debug.js")


def test_the_page_asks_for_the_values_to_be_stated_after_dividing():
    """The values are counted from the room, so the page asks for them after the grid is named."""
    page = both_pages()
    assert 'state_sizes?.("measured", room, grid, frame, 1);' in page
    assert 'state_sizes?.("cannot be measured", room, null, null, null);' in page
    assert 'state_sizes?.("no frame size was read for these skins", room, null, null, null);' in page
    body = page.split("function apply_largest_tile(")[1]
    assert body.index("stated_blocks = blocks_in_frames(grid, parts.length, frame);") < body.index(
        'state_sizes?.("measured"'
    )


def test_the_part_added_in_dev_mode_sends_what_it_was_asked_to_state():
    """The values only exist in the browser, so the part sends them to the debug path."""
    part = debug_page_source().partition("/* the debug part */")[2]
    assert 'fetch(REPORT_PATH, { method: "POST"' in part


def test_each_block_is_stated_with_the_size_its_own_tile_was_given():
    """A page that drew blocks of different sizes cannot describe them with one value, so the report names every block with the size that was used for its own tile."""
    part = debug_page_source().partition("/* the debug part */")[2]
    assert "blocks: describe_blocks()," in part
    assert "function describe_blocks()" in part
    page = both_pages()
    assert "function blocks_in_frames(grid, count, frame)" in page
    assert "tile: { width: block.colSpan * frame, height: block.rowSpan * frame }" in page
    # What is drawn is one frame of the skin, so a picture that is not one cell keeps its own shape.
    assert "image-rendering: pixelated" in page and "background-repeat: no-repeat" in page
    assert "block.style.backgroundSize" in page and "block.style.backgroundPosition" in page
    assert "function fit_scale(" in page
    # What is shown when a frame is larger than the box is decided by its centre, since the format has no position field.
    assert (
        "(boxWidth - frame.width * scaleWidth) / 2" in page and "(boxHeight - frame.height * scaleHeight) / 2" in page
    )
    assert ".avatar img" not in page


def test_the_report_states_what_was_taken_from_the_room():
    """A reader cannot reproduce a number that was divided from a box it cannot see, so the part states the measured box and what the page takes for itself."""
    part = debug_page_source().partition("/* the debug part */")[2]
    assert "measured: room.measured," in part
    assert "taken: taken," in part
    assert "const taken = room.taken ? { padding: room.taken.padding" in part
    # A gap between tracks is what is taken, so a single row or column takes nothing.
    assert "room.taken.gap.x * (parts.cols - 1)" in part and "room.taken.gap.y * (parts.rows - 1)" in part


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
    assert client_without_dev.get("/roster").status_code == 200
    assert "REPORT_PATH" not in served_page(client_without_dev)


def test_the_roster_page_answers_with_the_debug_page_in_dev_mode(client_with_dev):
    """The debug paths are open only in dev mode, so the page that states values is served only there."""
    assert client_with_dev.get("/roster").status_code == 200
    # The page itself holds markup and links; what states values is the part it then asks for.
    assert 'fetch(REPORT_PATH, { method: "POST"' in served_page(client_with_dev, "roster_debug.html")


def test_the_room_is_divided_in_whole_frame_counts_not_equal_tracks():
    """A tile that is a whole number of frames keeps pixels even, so the grid is counted in whole frames and not by dividing the room into equal tracks."""
    page = both_pages()
    assert "function whole_frame_grid(room, frame)" in page
    # A gap sits between two tracks, so a track costs the frame plus the gap that follows it.
    assert "Math.floor((space + gap) / (frame + gap))" in page
    assert 'root.style.gridTemplateColumns = "repeat(" + grid.cols + ", " + frame + "px)"' in page
    assert 'root.style.gridTemplateRows = "repeat(" + grid.rows + ", " + frame + "px)"' in page


def test_a_block_is_a_whole_number_of_tracks_on_each_axis():
    """Half of an odd span is not a whole number of frames, so a block that cannot be split in whole tracks stays as it is instead of being cut."""
    page = both_pages()
    assert "function blocks_in_frames(grid, count, frame)" in page
    assert "if (block.rowSpan < 2 && block.colSpan < 2) continue;" in page
    assert "if (!biggest) break;" in page


def test_the_scale_is_one_whole_number_for_both_axes_so_the_shape_does_not_change():
    """A scale that is a whole number on both axes keeps pixels even. A block bigger than one frame cannot be filled without changing the shape, so one scale is taken for both axes."""
    page = both_pages()
    assert (
        "const scale = Math.max(1, Math.min(Math.floor(boxWidth / frame.width), Math.floor(boxHeight / frame.height)));"
        in page
    )
    assert "show_cell(block, skin, frame, scale, scale, boxWidth, boxHeight);" in page


def test_only_the_cells_own_picture_is_drawn_so_the_rest_of_the_block_stays_its_own_background():
    """The whole sheet is not painted here: drawing only the cell keeps the space it does not cover as the blocks own background, so a block that is wider or higher than the cell shows the same on both axes."""
    page = both_pages()
    assert "const show_cell = function (block, skin, frame, scaleWidth, scaleHeight, boxWidth, boxHeight) {" in page
    assert 'block.style.width = frame.width * scaleWidth + "px";' in page
    assert 'block.style.height = frame.height * scaleHeight + "px";' in page
    # The cell is placed at the middle of the block, not at its edge.
    assert 'block.style.left = (boxWidth - frame.width * scaleWidth) / 2 + "px";' in page
    assert 'block.style.top = (boxHeight - frame.height * scaleHeight) / 2 + "px";' in page


def test_the_blocks_this_page_draws_are_reported_as_whole_numbers_of_frames():
    """The values stated are the blocks this page draws, so what is reported is whole counts of frames."""
    page = both_pages()
    assert "stated_blocks = blocks_in_frames(grid, parts.length, frame);" in page
    assert "tile: { width: block.colSpan * frame, height: block.rowSpan * frame }" in page


def test_a_page_that_states_values_has_no_reader_when_the_server_runs_without_dev_mode(client_without_dev):
    """A page that posts to a path the server did not open would state values nothing can read, so both answer from one flag."""
    assert client_without_dev.post("/api/debug/render", json={"path": "measured"}).status_code == 404
    assert "state_sizes = function" not in served_page(client_without_dev)


def test_the_page_that_states_values_and_the_path_that_answers_it_open_together(client_with_dev):
    """The page that states values and the path that reads them are opened by the same flag."""
    assert client_with_dev.post("/api/debug/render", json={"path": "measured"}).status_code == 200
    assert 'fetch(REPORT_PATH, { method: "POST"' in served_page(client_with_dev, "roster_debug.html")
