"""Roster — participants in one call."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TextEntry:
    """A line of text belonging to a participant, with the author who wrote it."""

    text: str
    author: str


class Participant:
    """A participant in a call, holding its name and its own text."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.texts: list[TextEntry] = []

    def add_text(self, text: str, author: str) -> TextEntry:
        """Record a line of text and who wrote it."""
        entry = TextEntry(text=text, author=author)
        self.texts.append(entry)
        return entry

    @property
    def status_text(self) -> str | None:
        """The latest line written by the agent."""
        return self._latest_written_by("agent")

    @property
    def system_text(self) -> str | None:
        """The latest line written by the system."""
        return self._latest_written_by("system")

    def _latest_written_by(self, author: str) -> str | None:
        for entry in reversed(self.texts):
            if entry.author == author:
                return entry.text
        return None


class Roster:
    """The participants taking part in one call."""

    def __init__(self) -> None:
        self.participants: list[Participant] = []

    def join(self, name: str) -> Participant:
        participant = Participant(name=name)
        self.participants.append(participant)
        return participant
