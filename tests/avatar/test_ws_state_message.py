"""The state message values come from participant records."""

from ziomek.api.avatar_ws import state_message
from ziomek.roster import Roster


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
