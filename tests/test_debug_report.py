"""The values a page measured are kept as the last report it sent."""

import pytest

from ziomek import debug_report


@pytest.fixture(autouse=True)
def no_report_yet():
    """The report is kept for the life of the server, so a test starts from nothing."""
    debug_report.clear()


def test_the_last_report_is_the_one_answered():
    debug_report.store({"room": {"width": 1000, "height": 800}, "cell": None, "frames": 10})
    debug_report.store({"room": {"width": 640, "height": 480}, "cell": {"width": 320, "height": 240}, "frames": 3})

    report = debug_report.last()
    assert report["room"] == {"width": 640, "height": 480}
    assert report["frames"] == 3


def test_a_report_that_is_not_an_object_is_not_stored():
    debug_report.store("not a report")

    assert debug_report.last() is None


def test_a_part_that_is_not_there_is_kept_as_empty_rather_than_left_out():
    """A reader should not read a missing part as a bug, so every part is present."""
    debug_report.store({"room": {"width": 640, "height": 480}})

    report = debug_report.last()
    assert sorted(report) == ["cell", "frames", "path", "room", "tile"]


def test_a_page_that_could_not_measure_says_which_path_it_took():
    debug_report.store({"room": {"width": 0, "height": 0}, "path": "unmeasurable"})

    report = debug_report.last()
    assert report["path"] == "unmeasurable"
    assert report["cell"] is None
