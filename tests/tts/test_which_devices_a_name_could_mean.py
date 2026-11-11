"""The answer for a name is every device that carries it, not one of them."""

from ziomek.tts.backends.devices import resolve_devices, which_devices_carry


class ReportsItsDevices:
    """A set of device names a lookup can be asked about."""

    def __init__(self, names: list[tuple[int, str]]):
        self._names = names

    def list_devices(self) -> list[dict]:
        return [{"id": i, "name": n, "channels": 2} for i, n in self._names]


HEADPHONES = ReportsItsDevices(
    [
        (3, "Speakers (Realtek Audio)"),
        (4, "Headphones 1 (Realtek 2nd output)"),
        (5, "Headphones 2 (USB Audio)"),
    ]
)


def test_the_answer_names_every_device_that_carries_the_part_asked_for():
    """A name that several devices carry is answered with all of them, in the order they are reported."""
    assert which_devices_carry("headphones", HEADPHONES) == [4, 5]


def test_a_part_of_a_name_is_matched_against_the_names_devices_carry():
    """A part of a name is matched against the whole names, so an incomplete name is still answered."""
    assert which_devices_carry("realtek 2nd", HEADPHONES) == [4]


def test_nothing_is_answered_when_no_device_carries_the_name():
    """A name no device carries is answered with nothing, not with a device that was not asked for."""
    assert which_devices_carry("nonexistent", HEADPHONES) == []


def test_the_part_of_a_name_is_matched_without_case():
    """The same names are answered whatever case the part asked for is written in."""
    assert which_devices_carry("REALTEK 2ND", HEADPHONES) == [4]


def test_a_number_is_answered_with_the_device_it_names():
    """A device given as a number is answered with that device, whatever the names say."""
    assert resolve_devices(7, HEADPHONES) == [7]


def test_nothing_is_answered_when_no_device_was_named():
    """An ask that names no device is answered with nothing, so the caller uses its own default."""
    assert resolve_devices(None, HEADPHONES) == []
    assert resolve_devices("default", HEADPHONES) == []


def test_a_name_that_a_device_carries_is_answered_with_that_device():
    """A whole name is answered the same way as a part of it, because a name carries itself."""
    assert which_devices_carry("Realtek 2nd output", HEADPHONES) == [4]


def test_the_default_is_not_an_answer_to_a_name():
    """The default is chosen by the caller, not returned as an answer, so nothing-found stays apart from it."""
    assert resolve_devices("default", HEADPHONES) == []
    assert resolve_devices(None, HEADPHONES) == []
