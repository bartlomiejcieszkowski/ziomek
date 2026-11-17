"""Which messages a participant has not been answered with yet."""

from itertools import count
from unittest.mock import patch

from ziomek.messages import answer_new_messages_for
from ziomek.roster import Roster


def test_the_answer_holds_only_entries_noticed_after_the_moment_a_participant_read_up_to():
    # The clock is held at values the machine cannot give in one step: on this box two calls to
    # time.monotonic() inside a burst return the same number, so a tie here would say nothing.
    roster = Roster()
    participant = roster.join("p1")
    with patch("ziomek.roster.time.monotonic", side_effect=count(1000.0)):
        first = roster.record("p1", "text", text="first", author="agent")
        second = roster.record("p1", "text", text="second", author="agent")

    participant.set_read_up_to(first["time"])

    assert answer_new_messages_for(participant, roster.events) == [second]


def test_the_answer_holds_nothing_after_the_last_moment_a_participant_read_up_to():
    roster = Roster()
    participant = roster.join("p1")
    last = roster.record("p1", "text", text="last", author="agent")

    participant.set_read_up_to(last["time"])

    assert answer_new_messages_for(participant, roster.events) == []


def test_answering_does_not_mark_what_was_answered_as_read():
    roster = Roster()
    participant = roster.join("p1")
    entry = roster.record("p1", "text", text="said once", author="agent")

    first_answer = answer_new_messages_for(participant, roster.events)
    second_answer = answer_new_messages_for(participant, roster.events)

    assert second_answer == first_answer


def test_a_participant_that_has_not_read_anything_is_answered_with_the_whole_record():
    roster = Roster()
    participant = roster.join("p1")
    first = roster.record("p1", "text", text="first", author="agent")
    second = roster.record("p2", "text", text="second", author="agent")

    assert answer_new_messages_for(participant, roster.events) == [first, second]


def test_a_line_a_participant_wrote_itself_is_not_answered_for_it():
    roster = Roster()
    participant = roster.join("p1")
    own_line = roster.record("p1", "text", text="its own line", author="p1")
    line_for_it = roster.record("p2", "text", text="a line for it", author="agent")

    assert answer_new_messages_for(participant, roster.events) == [line_for_it]


def test_an_entry_that_carries_no_text_is_not_a_message():
    # A join, a hold or a leave is an action with nothing written, so it is not part of the record read.
    roster = Roster()
    participant = roster.join("p1")
    join_entry = roster.record("p2", "join")
    message = roster.record("p2", "text", text="a line for it", author="agent")

    assert answer_new_messages_for(participant, roster.events) == [message]
