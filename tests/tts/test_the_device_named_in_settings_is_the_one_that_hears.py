"""The device named in settings is the device that hears."""

import pytest

from ziomek.tts.backends import BackendRegistry
from ziomek.tts.backends.base import IBackend
from ziomek.tts.playback import AudioPlayer

DEVICES = [
    {"id": 3, "name": "Speakers (Realtek Audio)", "channels": 2},
    {"id": 4, "name": "Headphones 1 (Realtek 2nd output)", "channels": 2},
]

SEVERAL = [
    {"id": 4, "name": "Headphones 1 (Realtek 2nd output)", "channels": 2},
    {"id": 5, "name": "Headphones 2 (USB Audio)", "channels": 2},
]

BUILT: list = []


class AimablePath(IBackend):
    """A path that can be aimed at a device, and records whether a sound reached it."""

    def __init__(self, device=None, extra_settings=None):
        super().__init__(device, extra_settings)
        self.heard_on: list = []
        BUILT.append(self)

    @property
    def can_be_aimed_at_a_device(self) -> bool:
        return True

    @property
    def supports_mixing(self) -> bool:
        return False

    def play(self, data: bytes, sr: int) -> None:
        # What a sound goes to is the device this path was told about.
        self.heard_on.append(self.which_device_hears())

    def mix_play(self, data: bytes, sr: int) -> None:
        # What a sound goes to is the device this path was told about.
        self.heard_on.append(self.which_device_hears())

    def list_devices(self) -> list[dict]:
        return DEVICES


class SeveralDevicesPath(AimablePath):
    """A path that can be aimed, but reports more names than one."""

    def list_devices(self) -> list[dict]:
        return SEVERAL


class PathThatCannotBeAimed(IBackend):
    """A path that plays on whatever the machine answers as its own."""

    def __init__(self, device=None, extra_settings=None):
        super().__init__(device, extra_settings)
        self.heard_on: list = []
        BUILT.append(self)

    @property
    def supports_mixing(self) -> bool:
        return False

    def play(self, data: bytes, sr: int) -> None:
        self.heard_on.append(self.hears_on[0] if len(self.hears_on) == 1 else None)

    def mix_play(self, data: bytes, sr: int) -> None:
        self.heard_on.append(self.hears_on[0] if len(self.hears_on) == 1 else None)

    def list_devices(self) -> list[dict]:
        return DEVICES


@pytest.fixture
def path_in_the_app():
    """Put one path in the registry for this test, and put the registry back after it."""
    saved = dict(BackendRegistry._backends)
    BUILT.clear()

    def build(name: str, path: type):
        BackendRegistry._backends[name] = path
        return BUILT

    yield build

    BackendRegistry._backends.clear()
    BackendRegistry._backends.update(saved)
    BUILT.clear()


def test_a_device_named_in_settings_is_the_device_the_sound_goes_to(path_in_the_app):
    """A sound is played on the device that was named, not on whatever the machine answers as its own."""
    built = path_in_the_app("aimable", AimablePath)
    AudioPlayer("aimable", device=4).mix_play(b"", 24000)
    assert built[-1].heard_on == [4]


def test_a_device_named_by_a_name_is_found_without_case(path_in_the_app):
    """A device named in settings is found by the name it carries, whatever case it is written in."""
    built = path_in_the_app("aimable", AimablePath)
    AudioPlayer("aimable", device="headphones 1 (realtek 2nd output)").mix_play(b"", 24000)
    assert built[-1].heard_on == [4]


def test_a_name_that_no_device_carries_is_reported(path_in_the_app, caplog):
    """A name that no device carries is said out loud, rather than answered by the default in silence."""
    path_in_the_app("aimable", AimablePath)
    AudioPlayer("aimable", device="something not on this machine")
    assert "something not on this machine" in caplog.text


def test_nothing_is_played_when_the_device_asked_for_cannot_be_found(path_in_the_app):
    """A sound is not sent anywhere when the device asked for is not a device on this machine."""
    built = path_in_the_app("aimable", AimablePath)
    AudioPlayer("aimable", device="something not on this machine").mix_play(b"", 24000)
    assert built[-1].heard_on == []


def test_a_path_that_cannot_be_aimed_says_that_it_cannot_be_aimed(path_in_the_app):
    """A path that plays on its own device says so, so an aim is not taken in silence."""
    built = path_in_the_app("cannot", PathThatCannotBeAimed)
    AudioPlayer("cannot", device=4)
    assert built[-1].can_be_aimed_at_a_device is False


def test_a_name_asked_for_on_a_path_that_cannot_be_aimed_is_reported(path_in_the_app, caplog):
    """The device asked for on a path that cannot be aimed is named in the report."""
    path_in_the_app("cannot", PathThatCannotBeAimed)
    AudioPlayer("cannot", device=4)
    assert "cannot be aimed" in caplog.text


def test_nothing_is_played_on_a_path_that_cannot_be_aimed(path_in_the_app):
    """A sound is not sent to the default of a path that was asked to go somewhere else."""
    built = path_in_the_app("cannot", PathThatCannotBeAimed)
    AudioPlayer("cannot", device=4).mix_play(b"", 24000)
    assert built[-1].heard_on == []


def test_a_path_that_can_be_aimed_answers_yes_for_aiming():
    """A path that can play on a device it was told about says so."""
    from ziomek.tts.backends.sounddevice import SounddeviceBackend

    assert SounddeviceBackend().can_be_aimed_at_a_device is True


def test_a_name_given_as_a_side_chooses_the_device_that_reads_as_that_side(path_in_the_app):
    """A name given as a side of the sound path is answered by the device whose name reads as that side."""
    built = path_in_the_app("aimable", AimablePath)
    AudioPlayer("aimable", device="headphone").mix_play(b"", 24000)
    assert built[-1].heard_on == [4]


def test_nothing_is_played_when_more_than_one_device_could_be_meant(path_in_the_app):
    """A name several devices carry is not answered by picking one of them."""
    built = path_in_the_app("several", SeveralDevicesPath)
    AudioPlayer("several", device="headphones").mix_play(b"", 24000)
    assert built[-1].heard_on == []


def test_the_report_names_which_devices_are_meant(path_in_the_app, caplog):
    """The names that could be meant are said, so the ask can be answered with one of them."""
    path_in_the_app("several", SeveralDevicesPath)
    AudioPlayer("several", device="headphones")
    assert "Headphones 1 (Realtek 2nd output)" in caplog.text
    assert "Headphones 2 (USB Audio)" in caplog.text


def test_a_sound_reaches_the_device_it_was_named_for(monkeypatch):
    """The device a path was told about is the one its play call is given."""
    import numpy as np

    from ziomek.tts.backends.sounddevice import SounddeviceBackend

    given = []
    monkeypatch.setattr("soundfile.read", lambda f: (np.zeros(1, dtype=np.float32), 24000))
    monkeypatch.setattr(
        "sounddevice.play", lambda data, samplerate=None, blocking=False, device=None: given.append(device)
    )
    path = SounddeviceBackend(device=6)
    path.play(b"", 24000)
    assert given == [6]


def test_a_sound_written_through_pyaudio_goes_to_the_device_it_was_named_for(monkeypatch):
    """The same holds for the path that opens a stream on a device it was told about."""
    from ziomek.tts.backends.pyaudio import PyaudioBackend

    opened_on = []

    class FakeStream:
        def write(self, data):
            pass

        def stop_stream(self):
            pass

        def close(self):
            pass

    class FakePyAudio:
        def get_default_output_device_info(self):
            return {"index": 0}

        def open(self, **kwargs):
            opened_on.append(kwargs.get("output_device_index"))
            return FakeStream()

    monkeypatch.setattr("pyaudio.PyAudio", lambda: FakePyAudio())
    path = PyaudioBackend(device=6)
    path.play(b"", 24000)
    assert opened_on == [6]


def test_a_sound_written_to_a_raw_stream_goes_to_the_device_it_was_named_for(monkeypatch):
    """The same holds for the path that opens a raw stream on a device it was told about."""
    import numpy as np

    from ziomek.tts.backends import raw_stream

    opened_on = []

    class FakeStream:
        write_available = 1000

        def write(self, data):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(raw_stream, "open_stream", lambda rate, device=None: opened_on.append(device) or FakeStream())
    monkeypatch.setattr(raw_stream, "read_samples", lambda data: (np.zeros(1, dtype=np.float32), 24000))
    path = raw_stream.RawStreamBackend(device=6)
    path.play(b"", 24000)
    assert opened_on == [6]
