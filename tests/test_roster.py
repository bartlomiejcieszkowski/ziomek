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


def test_participant_can_be_put_on_hold_and_shows_the_time_it_started():
    participant = Roster().join("Kate B.")
    assert participant.state == "active"
    assert participant.held_at is None

    participant.hold()
    assert participant.state == "held"
    assert isinstance(participant.held_at, float)

    participant.resume()
    assert participant.state == "active"


def test_the_call_keeps_a_record_of_what_happened():
    roster = Roster()
    roster.join("John A.")
    mary = roster.join("Mary S.")
    mary.hold()

    assert [(event["name"], event["action"]) for event in roster.events] == [
        ("John A.", "join"),
        ("Mary S.", "join"),
        ("Mary S.", "hold"),
    ]


def test_the_record_is_cleared_when_the_call_ends():
    roster = Roster()
    roster.join("John C.").hold()
    roster.end_call()

    assert roster.events == []
    assert roster.participants == []


def test_the_participant_keeps_its_own_events():
    roster = Roster()
    p = roster.join("John A.")

    assert p.events == [{"name": "John A.", "action": "join"}]
