"""Tests for ziomek avatar state machine."""

import time as _time

import pytest

from ziomek.avatar.state_machine import (
    _EXPRESSIONS,
    AvatarInput,
    AvatarStateMachine,
    ExpressionState,
    TriggerType,
)


def test_initial_state_is_bored():
    """Verify initial state starts with 'bored' from IDLE_SEQUENCE."""
    sm = AvatarStateMachine()
    state = sm.tick(16)
    # IDLE_SEQUENCE[0] = 'bored', so initial state is 'bored'
    assert state.expressionName == "bored"


def test_button_press_triggers_happy():
    """Verify button 0 press triggers happy expression."""
    sm = AvatarStateMachine()
    input = AvatarInput(
        buttons=[{"pressed": True, "value": 0}, {"pressed": False, "value": 0}],
        axes=[0, 0, 0],
        connected=True,
        streaming=False,
        chatFocused=False,
        errorState=False,
    )
    sm.update(input)
    state = sm.tick(400)  # tick within happy's 500ms duration
    assert state.expressionName == "happy"


def test_button_release_returns_to_neutral():
    """Verify button release returns to neutral."""
    sm = AvatarStateMachine()
    input = AvatarInput(
        buttons=[{"pressed": True, "value": 0}],
        axes=[0, 0, 0],
        connected=True,
        streaming=False,
        chatFocused=False,
        errorState=False,
    )
    sm.update(input)
    sm.tick(600)  # trigger happy
    input.buttons[0]["pressed"] = False  # release
    sm.update(input)
    state = sm.tick(1000)  # wait for the idle cycle
    assert state.expressionName in ("bored", "neutral")


def test_intensity_preemption():
    """Verify higher intensity expression preempts lower."""
    sm = AvatarStateMachine()
    input = AvatarInput(
        buttons=[{"pressed": True, "value": 0}],  # happy (intensity 1)
        axes=[0.5, 0, 0.5],  # axis active for focused (intensity 2)
        connected=True,
        streaming=False,
        chatFocused=False,
        errorState=False,
    )
    sm.update(input)
    state = sm.tick(1000)
    assert state.expressionName == "focused"  # higher intensity wins


def test_set_expression_forces_expression():
    """Verify setExpression() forces an expression."""
    sm = AvatarStateMachine()
    result = sm.setExpression("surprised", duration_ms=500)
    assert result is True
    state = sm.tick(100)
    assert state.expressionName == "surprised"


def test_set_message_with_expiry():
    """Verify setMessage() sets message with expiry."""
    sm = AvatarStateMachine()
    sm.setMessage("Hello!", duration_ms=500)
    state = sm.tick(100)
    assert state.message == "Hello!"
    assert state.messageExpiry is not None


def test_get_expression_names():
    """Verify getExpressionNames() returns full list."""
    sm = AvatarStateMachine()
    names = sm.getExpressionNames()
    assert "neutral" in names
    assert "happy" in names
    assert "thinking" in names
    assert "dying" in names


def test_get_default_expression():
    """Verify getDefaultExpression() returns 'neutral'."""
    sm = AvatarStateMachine()
    assert sm.getDefaultExpression() == "neutral"


def test_reset_clears_state():
    """Verify reset() clears all state."""
    sm = AvatarStateMachine()
    input = AvatarInput(
        buttons=[{"pressed": True, "value": 0}],
        axes=[0.5, 0, 0.5],
        connected=True,
        streaming=False,
        chatFocused=False,
        errorState=False,
    )
    sm.update(input)
    sm.tick(1000)
    assert sm._current is not None

    sm.reset()
    assert sm._current is None
    state = sm.tick(16)
    # After reset, starts with IDLE_SEQUENCE[0] = 'bored'
    assert state.expressionName == "bored"


def test_streaming_triggers_thinking():
    """Verify streaming=True triggers thinking."""
    sm = AvatarStateMachine()
    input = AvatarInput(
        buttons=[],
        axes=[],
        connected=True,
        streaming=True,
        chatFocused=False,
        errorState=False,
    )
    sm.update(input)
    state = sm.tick(100)
    assert state.expressionName == "thinking"


def test_error_state_triggers_dying():
    """Verify errorState=True triggers dying."""
    sm = AvatarStateMachine()
    input = AvatarInput(
        buttons=[],
        axes=[],
        connected=True,
        streaming=False,
        chatFocused=False,
        errorState=True,
    )
    sm.update(input)
    state = sm.tick(100)
    assert state.expressionName == "dying"


def test_set_message_is_recorded_on_the_participant_as_written_by_the_agent():
    """The agent's own text lives on the participant record, not only on the machine."""
    from ziomek.avatar.state_machine import AvatarStateMachine
    from ziomek.roster import Participant

    participant = Participant("John A.")
    sm = AvatarStateMachine(participant=participant)
    sm.setMessage("compiling software")

    assert participant.status_text == "compiling software"
    assert participant.texts[0].author == "agent"


def test_an_expression_that_is_not_given_a_period_is_held_past_any_period_it_could_have_meant():
    """A period that was never stated must not end the expression on its own."""
    sm = AvatarStateMachine()
    assert sm.setExpression("surprised") is True
    assert sm.tick(100).expressionName == "surprised"
    assert sm.tick(60_000).expressionName == "surprised"


def test_a_period_stated_as_no_number_is_read_as_no_period():
    """Saying "no period" as a value must answer the same as leaving it out."""
    sm = AvatarStateMachine()
    assert sm.setExpression("surprised", duration_ms=None) is True
    assert sm.tick(60_000).expressionName == "surprised"


def test_an_expression_that_is_asked_for_a_shorter_period_than_its_own_length_ends_at_the_period_asked_for():
    """A period is what a caller asked for, so it cannot be longer than the expression it was given."""
    sm = AvatarStateMachine()
    assert sm.setExpression("dying", duration_ms=500) is True
    assert sm.tick(400).expressionName == "dying"
    assert sm.tick(150).expressionName != "dying"


def test_an_expression_of_the_same_strength_is_not_taken_over_by_a_trigger():
    """Only a stronger expression takes over what is showing."""
    sm = AvatarStateMachine()
    sm.update(
        AvatarInput(buttons=[], axes=[0, 0, 0], connected=True, streaming=True, chatFocused=False, errorState=False)
    )
    assert sm.tick(1).expressionName == "thinking"

    # streaming stays on, so the expression asked for is not ended by the trigger going away
    sm.update(
        AvatarInput(
            buttons=[{"pressed": True, "value": 0}],
            axes=[0, 0, 0],
            connected=True,
            streaming=True,
            chatFocused=False,
            errorState=False,
        )
    )
    assert sm.tick(1).expressionName == "thinking"
