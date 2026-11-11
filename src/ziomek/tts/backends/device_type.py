"""The side of the sound path that a device name words."""

import re

HEADPHONE_WORDS = ("headphones", "headset", "earphones", "hands-free")
SPEAKER_WORDS = ("speakers",)
ANSWER_HEADPHONE = "headphone"
ANSWER_SPEAKER = "speaker"


def read_type_from_name(name: str) -> str | None:
    """Read which side of the sound path a device name words.

    Args:
        name: The device name as the machine reports it.

    Returns:
        "headphone", "speaker", or None when the name words no side.
    """
    # Only the part before the parenthesis is read; that other part names the driver, not the side.
    words = str(name).partition("(")[0].lower()
    found = set()
    for word in HEADPHONE_WORDS + SPEAKER_WORDS:
        if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", words):
            found.add(word)
    if found & set(HEADPHONE_WORDS) and found & set(SPEAKER_WORDS):
        return None
    if found & set(HEADPHONE_WORDS):
        return ANSWER_HEADPHONE
    if found & set(SPEAKER_WORDS):
        return ANSWER_SPEAKER
    return None
