"""The moment a message is given, and what follows from two of them landing at once."""

from unittest.mock import patch

from ziomek.messages import decide_time
from ziomek.roster import Roster


def test_a_message_noted_in_the_same_moment_as_the_previous_one_is_given_a_time_after_it():
    # A millisecond later, stated as the addition the rule makes, so the test does not depend on
    # how a number is stored.
    assert decide_time(1000.0, 1000.0) == 1000.0 + 0.001


def test_a_message_noted_after_the_clock_moved_keeps_the_moment_it_was_noted():
    assert decide_time(1000.0, 1002.5) == 1002.5


def test_the_first_message_of_a_record_is_given_the_moment_the_clock_shows():
    assert decide_time(None, 1002.5) == 1002.5


def test_two_messages_recorded_at_the_same_moment_are_not_given_the_same_time():
    # The clock is held so this does not depend on how coarse a machine's clock is.
    roster = Roster()
    with patch("ziomek.roster.time.monotonic", return_value=1000.0):
        first = roster.record("p1", "text", text="first", author="agent")
        second = roster.record("p1", "text", text="second", author="agent")

    assert second["time"] == first["time"] + 0.001
