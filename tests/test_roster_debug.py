"""The page served in dev mode states what it measured; the page without it does not."""

import pytest
from fastapi.testclient import TestClient

from tests.roster_page_helpers import (
    page_shell,
    parts_of_page,
    static_source,
)
from ziomek import dev_mode, server


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


def test_the_page_that_draws_tiles_states_nothing_while_no_reading_is_set():
    """The rules that draw a tile are the page; stating what was measured is only asked for in dev mode."""
    assert "export const state_sizes = { report: null };" in static_source("state_sizes.mjs")
    drawing = static_source("roster.mjs")
    assert 'import { room_for, state_sizes } from "./state_sizes.mjs";' in drawing
    assert "state_sizes.report = function" not in drawing
    assert 'state_sizes.report?.("cannot be measured"' in drawing


def test_the_debug_page_is_the_page_with_only_its_own_parts_added():
    """The page shown in dev mode is the same page with only what exists in dev mode added to it: the part that states values and the rule that styles what it shows."""
    own = [
        line
        for line in page_shell("roster_debug.html").split("\n")
        if line not in page_shell("roster.html").split("\n")
    ]
    assert len(own) == 2
    assert any('"/static/roster_debug.mjs"' in line for line in own)
    assert any('"/static/roster_debug.css"' in line for line in own)
    assert 'from "./state_sizes.mjs"' in static_source("roster_debug.mjs")


def test_the_part_added_in_dev_mode_states_values_before_the_page_starts():
    """A part read after the view starts would miss the values of the first render, so the page loads it before it starts."""
    shell = page_shell("roster_debug.html")
    assert shell.index('"/static/roster_debug.mjs"') < shell.index("start(")
    assert "state_sizes.report = function" in static_source("roster_debug.mjs")


def test_the_part_added_in_dev_mode_sends_what_it_was_asked_to_state():
    """The values only exist in the browser, so the part sends them to the debug path."""
    part = static_source("roster_debug.mjs")
    assert 'fetch(REPORT_PATH, { method: "POST"' in part
    assert 'const REPORT_PATH = "/api/debug/render";' in part


def test_a_report_that_changed_nothing_is_not_sent_again():
    """The page asks for values on every render, so the same values would be sent on every poll."""
    part = static_source("roster_debug.mjs")
    assert "if (JSON.stringify(report) === JSON.stringify(last)) return;" in part
    assert "fetch(REPORT_PATH" in part


def test_the_drawing_part_asks_for_the_shape_of_a_report_before_it_counts_anything():
    """The drawing part cannot state values on its own, so it asks for the shape and reports after the blocks are counted."""
    drawing = static_source("roster.mjs")
    assert 'state_sizes.report?.("measured", room, grid, frame, 1, stated_blocks);' in drawing
    assert 'state_sizes.report?.("cannot be measured", room, null, null, null, []);' in drawing
    assert 'state_sizes.report?.("no frame size was read for these skins", room, null, null, null, []);' in drawing
    guard = drawing.split("if (!frame) {")[1].split("}")[0]
    assert "return;" in guard
    body = drawing[drawing.index("function apply_largest_tile") : drawing.index("function render(tiles)")]
    assert body.index("stated_blocks = blocks_in_frames(grid, parts.length, frame);") < body.index(
        'state_sizes.report?.("measured"'
    )


def test_a_participant_with_no_block_is_not_drawn():
    """The room can only be divided so far. Past that a participant has no block, and nothing is drawn for them rather than a placeholder."""
    for page in ("roster.html", "roster_debug.html"):
        assert (
            "if (!place) continue;  // the room cannot be divided further, so this participant has no block"
            in parts_of_page(page)["roster.mjs"]
        )


def test_the_roster_page_answers_with_the_page_without_the_debug_part(client_without_dev):
    """Without dev mode nothing can be told back, so a page that states values has no reader."""
    assert client_without_dev.get("/roster").status_code == 200
    assert not any("REPORT_PATH" in part for part in parts_of_page("roster.html").values())


def test_the_roster_page_answers_with_the_debug_page_in_dev_mode(client_with_dev):
    """The debug paths are open only in dev mode, so the page that states values is served only there."""
    assert client_with_dev.get("/roster").status_code == 200
    # The page itself holds markup and links; what states values is the part it then asks for.
    assert 'fetch(REPORT_PATH, { method: "POST"' in static_source("roster_debug.mjs")
    assert parts_of_page("roster_debug.html")["roster_debug.mjs"] == static_source("roster_debug.mjs")


def test_the_page_that_states_values_and_the_path_that_answers_it_open_together(client_with_dev):
    """The page that states values and the path that reads them are opened by the same flag."""
    assert client_with_dev.post("/api/debug/render", json={"path": "measured"}).status_code == 200
    assert 'fetch(REPORT_PATH, { method: "POST"' in static_source("roster_debug.mjs")


def test_the_room_is_divided_in_whole_frame_counts_not_equal_tracks():
    """A tile that is a whole number of frames keeps pixels even, so the grid is counted in whole frames and not by dividing the room into equal tracks."""
    drawing = parts_of_page("roster_debug.html")["roster_grid.mjs"]
    assert "function count_tracks(space, gap, frame)" in drawing
    # A gap sits between two tracks, so a track costs the frame plus the gap that follows it.
    assert "Math.floor((space + gap) / (frame + gap))" in drawing
    joined = static_source("roster.mjs")
    assert 'root.style.gridTemplateColumns = "repeat(" + grid.cols + ", " + frame + "px)"' in joined
    assert 'root.style.gridTemplateRows = "repeat(" + grid.rows + ", " + frame + "px)"' in joined


# What a page in dev mode shows on screen, for the person looking at it.


def test_a_page_served_in_dev_mode_shows_that_it_is_the_one_served_in_dev_mode():
    """Only the part added in dev mode can know how the app was started, so it is what says so on screen."""
    part = static_source("roster_debug.mjs")
    assert 'const indicator = document.createElement("div");' in part
    assert 'indicator.className = "debug_mode";' in part
    assert 'indicator.textContent = "debug mode";' in part


def test_a_page_that_was_not_served_in_dev_mode_shows_nothing_about_dev_mode():
    """A page without that part has no way to know how the app was started, so it shows no indicator."""
    for name in ("roster.mjs", "roster.css"):
        assert "debug_mode" not in static_source(name)


def test_a_page_served_in_dev_mode_prints_what_it_measured():
    """The values a page measured are shown next to the indicator that says dev mode is on."""
    part = static_source("roster_debug.mjs")
    assert 'const values = document.createElement("div");' in part
    assert 'values.className = "debug_values";' in part
    assert "values.textContent = describe(report);" in part


def test_a_page_that_was_not_served_in_dev_mode_prints_nothing_it_measured():
    """Without that part nothing is stated, so a page draws tiles and says nothing about their sizes."""
    for name in ("roster.mjs", "roster.css"):
        assert "debug_values" not in static_source(name)


def test_what_a_page_shows_about_its_sizes_is_the_report_it_sends():
    """What is on screen and what is stored must not be able to disagree, so one report serves both."""
    part = static_source("roster_debug.mjs")
    assert part.count("build_report(") == 1
    assert "values.textContent = describe(report);" in part
    assert "body: JSON.stringify(report)" in part


def test_a_page_that_could_not_measure_anything_says_why_not():
    """An empty box leaves a reader guessing, so the reason a measurement was not possible is the first thing printed."""
    part = static_source("roster_debug.mjs")
    described = part[part.index("function describe(report)") :]
    assert "const lines = [report.path];" in described


def test_the_values_printed_by_a_page_state_the_area_it_measured():
    """A record read from the printed values is about the area a page measured, so the numbers printed are that area and not what padding takes from it."""
    part = static_source("roster_debug.mjs")
    described = part[part.index("function describe(report)") :]
    assert "lines.push(`room ${report.room.measured.width}x${report.room.measured.height}`);" in described


def test_the_page_served_in_dev_mode_links_the_rule_that_styles_what_it_shows():
    """A page holds links only, so the rule for the indicator and the printed values is a part it asks for."""
    assert 'href="/static/roster_debug.css"' in page_shell("roster_debug.html")


def test_a_page_that_is_not_the_one_served_in_dev_mode_links_no_rule_for_it():
    """Nothing that only exists in dev mode is asked for by a page that was not served in dev mode."""
    assert "roster_debug.css" not in page_shell("roster.html")


def test_the_indicator_stays_in_the_bottom_right_corner_of_the_window():
    """The indicator is read at the edge of the window, so it stays there and does not move with the record."""
    rule = static_source("roster_debug.css")
    block = rule[rule.index(".debug_mode {") : rule.index(".debug_values {")]
    assert "position: fixed;" in block
    assert "right: 8px;" in block
    assert "bottom: 8px;" in block


def test_the_printed_values_stay_in_the_bottom_left_corner_of_the_window():
    """The printed values are read against the drawing area, so they stay at its edge."""
    rule = static_source("roster_debug.css")
    block = rule[rule.index(".debug_values {") :]
    assert "position: fixed;" in block
    assert "left: 8px;" in block
    assert "bottom: 8px;" in block


def test_the_values_printed_by_a_page_stay_on_the_lines_they_are_written_on():
    """The values are written one per line, so a reader sees them apart instead of as one run of words."""
    rule = static_source("roster_debug.css")
    block = rule[rule.index(".debug_values {") :]
    assert "white-space: pre-wrap;" in block
