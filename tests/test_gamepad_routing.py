"""The gamepad drives one machine, so it is not routed to participants while a call is open."""

from ziomek.avatar.state_machine import AvatarInput, AvatarStateMachine
from ziomek.gamepad import route_gamepad_input
from ziomek.roster import Roster


def pressed_input():
    return AvatarInput(
        buttons=[{"pressed": True, "value": 1.0}],
        axes=[0.0],
        connected=True,
        streaming=False,
        chatFocused=False,
        errorState=False,
    )


def test_the_gamepad_is_not_routed_to_participants_while_a_call_is_open():
    roster = Roster(pool=[("John", "alice")], state_machine_factory=AvatarStateMachine)
    participant = roster.join()
    routed = []

    def note(machine, expression, cycle_index):
        routed.append(expression)

    participant.state_machine.on_change = note
    route_gamepad_input(pressed_input(), participant.state_machine, roster)

    assert routed == []
    assert len(roster.participants) == 1


def test_the_gamepad_is_routed_when_no_call_is_open():
    roster = Roster(pool=[("John", "alice")], state_machine_factory=AvatarStateMachine)
    machine = AvatarStateMachine()
    routed = []

    def note(m, expression, cycle_index):
        routed.append(expression)

    machine.on_change = note
    route_gamepad_input(pressed_input(), machine, roster)

    assert routed != []
    assert roster.participants == []


def test_the_server_loop_uses_the_routing_instead_of_the_machine_directly(monkeypatch):
    import sys
    from types import SimpleNamespace

    from ziomek import server

    # Stop any gamepad thread started by another test, so only this loop reports calls.
    server._stop_gamepad_thread()

    roster = Roster(pool=[("John", "alice")])
    calls = []

    class fake_manager:
        def start(self):
            pass

        def poll(self):
            return SimpleNamespace(connected=True, buttons=[0], axes=[0.0])

        def stop(self):
            pass

    machine = object()

    def fake_route(inp, passed_machine, passed_roster):
        calls.append((passed_machine, passed_roster))
        raise SystemExit  # SystemExit is not caught by the loop's except Exception

    monkeypatch.setattr(server, "GamepadManager", lambda *a, **k: fake_manager())
    monkeypatch.setattr(server, "get_roster", lambda settings=None: roster)
    monkeypatch.setattr(server, "route_gamepad_input", fake_route)

    server._start_gamepad_thread(machine)
    server._gamepad_thread.join(timeout=2)

    # The loop routes through the shared roster instead of calling the machine directly.
    assert (machine, roster) in calls
