"""The state message values come from participant records."""

from ziomek.api.avatar_ws import state_message
from ziomek.roster import Participant, Roster


def test_state_message_reads_from_the_participant_record():
    participant = Roster().join("John A.")
    participant.add_text("*hmm* compiling", author="agent")

    msg = state_message(participant, "happy", 0)
    assert msg["name"] == "John A."
    assert msg["status_text"] == "*hmm* compiling"


def test_fields_are_empty_without_a_participant_record():
    msg = state_message(None, "happy", 0)
    assert msg["name"] is None
    assert msg["status_text"] is None


def test_agent_text_and_system_text_stay_in_their_own_areas():
    participant = Roster().join("John B.")
    participant.add_text("compiling", author="agent")
    participant.add_text("On hold 00:12", author="system")

    msg = state_message(participant, "happy", 0)
    assert msg["status_text"] == "compiling"
    assert msg["system_text"] == "On hold 00:12"


def test_the_message_says_when_a_participant_is_on_hold():
    participant = Roster().join("John C.")
    participant.hold()

    msg = state_message(participant, "happy", 0)
    assert msg["on_hold"] is True
    # The page ticks the elapsed time itself, so it needs a starting point.
    assert msg["held_seconds"] == 0


def test_the_payload_carries_the_author_of_each_text():
    p = Participant("John A.", voice="alice")
    p.add_text("compiling", author="agent")
    p.add_text("On hold 00:12", author="system")

    msg = state_message(p, "focused", 0)

    # The page can tell the two apart only if each entry carries its author.
    assert msg["texts"] == [
        {"text": "compiling", "author": "agent"},
        {"text": "On hold 00:12", "author": "system"},
    ]
