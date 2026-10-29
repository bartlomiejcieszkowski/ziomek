"""Participant records hold the name and text, not the state machine."""

from ziomek.roster import Roster


def test_join_creates_a_participant_record():
    participant = Roster().join("John")
    assert participant.name == "John"
