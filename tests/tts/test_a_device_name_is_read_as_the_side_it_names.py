"""Names read as the side of the sound path they name."""

from ziomek.tts.backends.device_type import read_type_from_name


def test_a_name_that_names_headphones_answers_for_the_headphone_side():
    """A name that says headphones is read as the headphone side, as the machine on this box reports it."""
    assert read_type_from_name("Headphones 1 (Realtek HD Audio 2nd output with SST)") == "headphone"


def test_a_name_that_names_a_headset_answers_for_the_headphone_side():
    """A name that words a call device reaches the same answer as one that says headphones."""
    assert read_type_from_name("Headset (WH-1000XM5)") == "headphone"
    assert read_type_from_name("WH-1000XM5 Hands-Free") == "headphone"


def test_a_name_that_names_speakers_answers_for_the_speaker_side():
    """A name that says speakers is read as the speaker side, as the machine on this box reports it."""
    assert read_type_from_name("Speakers (3- Realtek(R) Audio)") == "speaker"


def test_the_words_are_read_without_case():
    """The same word answers the same side whatever case the name is written in."""
    assert read_type_from_name("SPEAKERS (Realtek)") == "speaker"
    assert read_type_from_name("headphones (usb audio)") == "headphone"


def test_the_part_that_names_the_driver_is_not_read():
    """A word inside the part in parentheses is not read, because that part names the driver, not the side."""
    assert read_type_from_name("Realtek Audio (Headphones)") is None


def test_a_name_that_names_neither_side_answers_nothing():
    """A name that names no side is not guessed, so an answer of nothing is a real answer."""
    assert read_type_from_name("Line Out (SteelSeries_Sonar_VAD Stream Wave)") is None
    assert read_type_from_name("U32U3CV (NVIDIA High Definition Audio)") is None


def test_a_name_that_names_both_side_answers_nothing():
    """A name that names both sides cannot be read as one of them."""
    assert read_type_from_name("Speakers and Headphones") is None


def test_a_word_inside_a_longer_name_is_not_read_as_one_of_them():
    """Only a word on its own is read, so a brand that only looks like one is not read as a side."""
    assert read_type_from_name("RealtekHeadphones") is None
