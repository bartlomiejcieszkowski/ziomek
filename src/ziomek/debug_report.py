"""What a page measured for itself, kept as the last report it sent."""

from __future__ import annotations

# Every part of a report is kept even when a page cannot state it, so a reader does not read a
# missing part as a bug. The grid is stated as the base track, and the blocks a page made beyond it are
# kept as it stated them, because blocks of different sizes cannot be described with one value.
PARTS = ["path", "room", "cell", "frames", "tile", "blocks"]

_report: dict | None = None


def clear() -> None:
    """Forget the report, as a server that has not seen one is. The call record is not kept either."""
    global _report
    _report = None


def store(raw) -> dict | None:
    """Keep what a page sent. Something that is not a set of values is not a report."""
    global _report
    if not isinstance(raw, dict):
        return None

    report = {part: raw.get(part) for part in PARTS}
    _report = report
    return report


def last() -> dict | None:
    """The last report a page sent, or nothing when no page reported."""
    return _report
