"""The gamepad is inert for now: it polls but applies nothing, it will be a control method later."""

from types import SimpleNamespace

from ziomek import server
from ziomek.gamepad import handle_gamepad_input
from ziomek.roster import Roster


def pressed_input():
    return SimpleNamespace(
        buttons=[1, 0],
        axes=[0.0],
        connected=True,
    )


class recording:
    def __init__(self):
        self.calls = []

    def update(self, input):
        self.calls.append(input)


def test_the_gamepad_input_is_not_applied_to_any_machine():
    machine = recording()
    roster = Roster(pool=[("John", "alice")], state_machine_factory=lambda participant: machine)
    participant = roster.join("John")

    handle_gamepad_input(pressed_input())

    # Nothing is driven: not even the machine that belongs to this participant.
    assert participant.state_machine is machine
    assert machine.calls == []


def test_the_poll_loop_delivers_input_without_touching_a_machine(monkeypatch):
    received = []

    class fake_manager:
        def start(self):
            pass

        def poll(self):
            return SimpleNamespace(connected=True, buttons=[1], axes=[0.0])

        def stop(self):
            pass

    def fake_handle(input):
        received.append(input)
        raise SystemExit  # SystemExit is not caught by the loop's except Exception

    server._stop_gamepad_thread()
    monkeypatch.setattr(server, "GamepadManager", lambda *a, **k: fake_manager())
    monkeypatch.setattr(server, "handle_gamepad_input", fake_handle)

    server._start_gamepad_thread()
    server._gamepad_thread.join(timeout=2)

    assert received
    # The loop has no machine to point at: the gamepad is not an expression source.
    assert "state_machine" not in server._start_gamepad_thread.__code__.co_varnames
