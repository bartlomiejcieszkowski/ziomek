"""ziomek client gamepad module — pygame joystick polling.

Wraps pygame joystick for gamepad input detection and polling.
Thread-safe: state is protected by a lock so poll() can be called
from any thread (e.g. the background poll loop).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class GamepadState:
    """Current state of the gamepad."""
    buttons: list[float] = field(default_factory=list)
    axes: list[float] = field(default_factory=list)
    connected: bool = False


class GamepadManager:
    """Wraps pygame joystick polling for gamepad input.

    Attributes:
        manager: The underlying GamepadManager instance (lazily initialized).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = GamepadState()
        self._initialized = False
        self._joystick = None

    def start(self) -> None:
        """Initialize pygame and discover gamepads.

        Does NOT throw if no gamepad is connected.
        """
        import pygame

        pygame.joystick.init()
        count = pygame.joystick.get_count()
        if count > 0:
            self._joystick = pygame.joystick.Joystick(0)
            self._joystick.init()
            self._initialized = True

    def poll(self) -> GamepadState:
        """Read current gamepad state (buttons, axes, connected).

        Returns a copy of the current state. Thread-safe via lock.
        """
        if not self._initialized or self._joystick is None:
            return GamepadState()

        with self._lock:
            buttons = [
                self._joystick.get_button(i)
                for i in range(self._joystick.get_numbuttons())
            ]
            axes = [
                self._joystick.get_axis(i)
                for i in range(self._joystick.get_numaxes())
            ]
            self._state = GamepadState(
                buttons=buttons,
                axes=axes,
                connected=True,
            )

        return GamepadState(
            buttons=self._state.buttons,
            axes=self._state.axes,
            connected=self._state.connected,
        )

    def stop(self) -> None:
        """Cleanup pygame joystick resources."""
        if self._joystick is not None:
            self._joystick.quit()
            self._joystick = None

        import pygame

        pygame.joystick.quit()
        self._initialized = False
