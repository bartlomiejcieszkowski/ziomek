"""Participant records hold the name and text, not the state machine."""

from ziomek.roster import Roster


def test_join_creates_a_participant_record():
    participant = Roster().join("John")
    assert participant.name == "John"


def test_participant_records_text_with_provenance():
    participant = Roster().join("John A.")
    participant.add_text("compiling software", author="agent")

    entry = participant.texts[0]
    assert entry.text == "compiling software"
    assert entry.author == "agent"


def test_system_messages_are_kept_apart_from_agent_text():
    participant = Roster().join("John B.")
    participant.add_text("compiling", author="agent")
    participant.add_text("On hold 00:12", author="system")

    assert [entry.author for entry in participant.texts] == ["agent", "system"]
