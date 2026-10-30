"""Roster — participants in one call."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class TextEntry:
    """A line of text belonging to a participant, with the author who wrote it."""

    text: str
    author: str


@dataclass
class EventEntry:
    """Something that happened to a participant during the current call."""

    name: str
    action: str


class Participant:
    """A participant in a call, holding its name and its own text."""

    def __init__(self, name: str, roster: "Roster | None" = None) -> None:
        self.name = name
        self.texts: list[TextEntry] = []
        self.roster = roster
        self.state = "active"
        self.held_at: float | None = None

    def add_text(self, text: str, author: str) -> TextEntry:
        """Record a line of text and who wrote it."""
        entry = TextEntry(text=text, author=author)
        self.texts.append(entry)
        return entry

    def hold(self) -> None:
        """The participant is quiet for a while, so inactivity is not counted."""
        self.state = "held"
        self.held_at = time.monotonic()
        if self.roster is not None:
            self.roster.record(self.name, "hold")

    def resume(self) -> None:
        """Count inactivity again."""
        self.state = "active"
        self.held_at = None

    @property
    def held_seconds(self) -> int:
        """How long the participant has been quiet, in whole seconds."""
        if self.held_at is None:
            return 0
        return int(time.monotonic() - self.held_at)

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
        # What happened during this call, kept only while it is open.
        self.events: list[EventEntry] = []

    def join(self, name: str) -> Participant:
        participant = Participant(name=name, roster=self)
        self.participants.append(participant)
        self.record(name, "join")
        return participant

    def record(self, name: str, action: str) -> EventEntry:
        entry = EventEntry(name=name, action=action)
        self.events.append(entry)
        return entry

    def end_call(self) -> None:
        """Drop the participants and the record once the call is over."""
        self.participants.clear()
        self.events.clear()
