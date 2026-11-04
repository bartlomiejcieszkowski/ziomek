"""Participant records hold the name and text, not the state machine."""

import time

from ziomek.avatar.state_machine import AvatarStateMachine
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

    assert p.events == [{"name": "John A.", "action": "join", "voice": p.voice, "skin": p.skin}]


def test_the_join_entry_carries_the_voice_and_face_it_assigned():
    # The record shows what was drawn for a name, so both sides can read it.
    roster = Roster()
    participant = roster.join("John A.")

    entry = roster.events[0]
    assert entry["action"] == "join"
    assert entry["voice"] == participant.voice == "cosette"
    assert entry["skin"] == participant.skin == "single-frame"


def test_an_entry_for_a_join_keeps_nothing_that_was_not_drawn():
    # Nothing is recorded for a name that could not be drawn from either set.
    roster = Roster()
    roster.voices = []
    roster.skins = []
    roster.default_skin = ""
    participant = roster.join("John A.")

    assert participant.voice is None and participant.skin is None
    assert roster.events[0] == {"name": "John A.", "action": "join"}


def test_joining_a_name_that_is_already_in_the_call_is_rejected():
    roster = Roster()
    roster.join("John A.")

    try:
        roster.join("John A.")
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("joining a name already in the call should be rejected")


def test_the_display_name_of_a_participant_stays_fixed_while_it_is_in_the_call():
    roster = Roster(pool=[("John A.", "alice"), ("John B.", "bob")])
    first = roster.join()

    # A later join may not take the name away from a participant already in the call.
    second = roster.join()
    assert first.name != second.name
    assert first.name == first.display_name


def test_join_creates_its_own_state_machine_for_the_participant():
    roster = Roster(pool=[("John", "alice")], state_machine_factory=AvatarStateMachine)
    first = roster.join()
    second = roster.join("Donald", voice="bob")

    assert first.state_machine is not None
    # Each participant drives its own machine, not a shared one.
    assert first.state_machine is not second.state_machine
    # The machine reads the name and text areas from its participant record.
    assert first.state_machine.participant is first


def test_the_view_push_hook_is_attached_to_every_machine_the_roster_makes():
    made = []

    class machine:
        def __init__(self, participant):
            made.append(self)
            self.participant = participant
            self.on_change = None

    pushes = []

    def push(participant, expression, cycle_index):
        pushes.append((participant, expression, cycle_index))

    roster = Roster(pool=[("John", "alice")], state_machine_factory=machine, push_hook=push)
    participant = roster.join("John")

    made[0].on_change(participant, "happy", 0)
    assert pushes == [(participant, "happy", 0)]


def test_the_recorded_event_carries_the_text_attached_to_it():
    roster = Roster()
    p = roster.join("John A.")
    p.add_text("compiling", author="agent")

    entry = roster.events[-1]
    assert entry["name"] == "John A."
    assert entry["action"] == "text"
    assert entry["text"] == "compiling"
    assert entry["author"] == "agent"


def test_the_record_is_cleared_when_the_last_participant_is_dropped():
    roster = Roster(quiet_for=1000)
    roster.join("John A.")

    roster.drop_quiet(time.monotonic() + 1001)

    assert roster.participants == []
    assert roster.events == []
