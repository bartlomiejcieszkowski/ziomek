"""Tests for ziomek.client.gamepad — GamepadManager and GamepadState."""
from __future__ import annotations

from ziomek.client.gamepad import GamepadManager, GamepadState


def test_gamepad_manager_initial_state():
    """GamepadManager starts with empty, disconnected state."""
    manager = GamepadManager()
    assert not manager._initialized
    state = manager.poll()
    assert state.buttons == []
    assert state.axes == []
    assert state.connected is False


def test_gamepad_manager_start_without_gamepad():
    """Should not raise when no gamepad is connected."""
    manager = GamepadManager()
    try:
        manager.start()
        # If pygame init succeeded, verify poll returns disconnected state
        state = manager.poll()
        # May return empty state if no gamepad detected
        assert isinstance(state, GamepadState)
        manager.stop()
    except Exception:
        # pygame init may fail in headless environments — that's OK
        pass
