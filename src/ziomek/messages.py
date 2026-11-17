"""Reading the record as messages, and which of them one participant has not been answered with."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ziomek.roster import Participant


def decide_time(previous: float | None, now: float) -> float:
    """The moment an entry is given, kept later than the one before it.

    A machine clock can show the same value for two calls made close together, so two messages
    noted in one step carry the same moment, and a marker holding that moment cannot say which of
    them a reader has already seen. A message that would tie is given a moment a millisecond
    later. That states a moment that did not happen, accepted so a reader is not answered with
    lines it has already seen."""
    if previous is None or now > previous:
        return now
    # The rule is this line: the moment must be later than the one before it, because a tie cannot be read.
    return previous + 0.001


def is_message(entry: dict) -> bool:
    """An entry that carries text is a message. An action with nothing written is not one."""
    return entry.get("text") is not None


def answer_new_messages_for(participant: Participant, entries: list[dict]) -> list[dict]:
    """Answer the messages this participant has not been answered with yet.

    Answering does not move the marker; only the act that says what was read does. A line this
    participant wrote itself is not a message for it, and a reader that has read nothing is
    answered with the whole record, which is where a join starts."""
    read_up_to = participant.read_up_to
    return [
        entry
        for entry in entries
        if is_message(entry)
        and entry.get("author") != participant.name
        and (read_up_to is None or entry["time"] > read_up_to)
    ]
