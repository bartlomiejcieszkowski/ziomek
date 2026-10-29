"""Roster — participants in one call."""

from __future__ import annotations


class Participant:
    """A participant in a call, holding its name and its own text."""

    def __init__(self, name: str) -> None:
        self.name = name


class Roster:
    """The participants taking part in one call."""

    def __init__(self) -> None:
        self.participants: list[Participant] = []

    def join(self, name: str) -> Participant:
        participant = Participant(name=name)
        self.participants.append(participant)
        return participant
