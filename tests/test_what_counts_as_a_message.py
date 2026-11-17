"""What counts as a message in the record."""

from __future__ import annotations

from ziomek.messages import is_message


def test_an_entry_that_carries_text_is_a_message():
    assert is_message({"action": "text", "text": "the kettle is on", "time": 1.0, "author": "Maria B."}) is True


def test_an_action_with_nothing_written_is_not_a_message():
    assert is_message({"action": "join", "voice": "cosette", "skin": "two-tone_teal", "time": 2.0}) is False
