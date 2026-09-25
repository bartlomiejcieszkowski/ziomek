"""Tests for ziomek avatar state machine."""
import pytest
import time as _time

from ziomek.avatar.state_machine import (
    AvatarStateMachine,
    AvatarInput,
    ExpressionState,
    _EXPRESSIONS,
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


def test_button_release_returns_to_idle():
    """Verify button release returns to idle."""
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
    state = sm.tick(1000)  # wait for idle cycle
    assert state.expressionName in ("bored", "neutral", "idle")


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
    assert "idle" in names
    assert "happy" in names
    assert "thinking" in names
    assert "dying" in names


def test_get_default_expression():
    """Verify getDefaultExpression() returns 'idle'."""
    sm = AvatarStateMachine()
    assert sm.getDefaultExpression() == "idle"


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
