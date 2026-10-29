from ziomek.api.avatar_ws import state_message


def test_state_message_has_name_and_status_text_when_provided():
    msg = state_message("happy", 0, name="John", status_text="*hmm* compiling")
    assert msg["name"] == "John"
    assert msg["status_text"] == "*hmm* compiling"


def test_state_message_fields_are_none_when_not_provided():
    msg = state_message("happy", 0)
    assert msg["name"] is None
    assert msg["status_text"] is None
