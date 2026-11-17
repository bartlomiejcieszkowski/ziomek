"""Reading the record as messages, and which of them one participant has not been answered with."""

from ziomek.roster import Participant


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
