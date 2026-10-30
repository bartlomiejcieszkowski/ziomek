"""Roster — participants in one call."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass

CHECK_INTERVAL = 1.0  # seconds between checks on the event loop


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

    def __init__(
        self,
        name: str,
        roster: "Roster | None" = None,
        voice: str | None = None,
    ) -> None:
        self.name = name
        self.voice = voice
        self.texts: list[TextEntry] = []
        self.roster = roster
        self.state = "active"
        self.held_at: float | None = None
        self.last_seen = time.monotonic()
        self.usage = 1

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
        self.seen()

    def seen(self) -> None:
        """Mark the participant as active now, so the inactivity timer restarts."""
        self.last_seen = time.monotonic()

    def leave(self) -> None:
        """The participant is gone and its pool entry is released."""
        self.state = "left"
        if self.roster is not None:
            self.roster.release(self)
            self.roster.record(self.name, "leave")

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

    def __init__(
        self,
        pool: list[tuple[str, str]] | None = None,
        quiet_for: int = 3000,
        rng: random.Random | None = None,
    ) -> None:
        self.pool: list[tuple[str, str]] = list(pool or [])
        self.quiet_for = quiet_for
        self.rng = rng or random.Random()
        self.participants: list[Participant] = []
        # Usage counts are kept only while the call is open.
        self.usage_counts: dict[str, int] = {}
        # What happened during this call, kept only while it is open.
        self.events: list[EventEntry] = []

    def join(self, name: str | None = None, voice: str | None = None) -> Participant:
        participant = Participant(name=name or "", roster=self, voice=voice)
        if name is None:
            participant.name = self._pick_name()
        if voice is None:
            participant.voice = self._pick_voice(participant.name)
        participant.usage = self._count(participant.name)
        self.participants.append(participant)
        self.record(participant.name, "join")
        return participant

    def drop_quiet(self, now: float) -> list[Participant]:
        """Drop participants that have been silent past the configured quiet time."""
        dropped = []
        for participant in self.participants:
            if participant.state != "active":
                continue
            if now - participant.last_seen >= self.quiet_for:
                dropped.append(participant)
        for participant in dropped:
            participant.leave()
        return dropped

    def release(self, participant: Participant) -> None:
        """Release the pool entry the participant was using."""
        count = self.usage_counts.get(participant.name, 0)
        if count > 1:
            self.usage_counts[participant.name] = count - 1
        else:
            self.usage_counts.pop(participant.name, None)
        if participant in self.participants:
            self.participants.remove(participant)

    def _count(self, name: str) -> int:
        count = self.usage_counts.get(name, 0) + 1
        self.usage_counts[name] = count
        return count

    def _candidates(self, key: int) -> list[tuple[str, str]]:
        """Entries with the lowest usage count for the given pool field."""
        counts = {entry[0]: self.usage_counts.get(entry[0], 0) for entry in self.pool}
        lowest = min(counts.values()) if counts else 0
        return [entry for entry in self.pool if counts[entry[0]] == lowest]

    def _pick_name(self) -> str:
        if not self.pool:
            return ""
        # Prefer an entry that has not been used, otherwise the least used one.
        unused = [entry for entry in self.pool if self.usage_counts.get(entry[0], 0) == 0]
        if unused:
            return self.rng.choice(unused)[0]
        return self.rng.choice(self._candidates(0))[0]

    def _pick_voice(self, name: str) -> str | None:
        if not self.pool:
            return None
        for entry in self.pool:
            if entry[0] == name:
                return entry[1]
        used_voices = {p.voice for p in self.participants if p.voice}
        unused = [entry[1] for entry in self.pool if entry[1] not in used_voices]
        if unused:
            return self.rng.choice(unused)
        counts = {entry[1]: self.usage_counts.get(entry[0], 0) for entry in self.pool}
        lowest = min(counts.values())
        return self.rng.choice([voice for voice, c in counts.items() if c == lowest])

    def record(self, name: str, action: str) -> EventEntry:
        entry = EventEntry(name=name, action=action)
        self.events.append(entry)
        return entry

    def end_call(self) -> None:
        """Drop the participants, the pool counts, and the record."""
        self.participants.clear()
        self.usage_counts.clear()
        self.events.clear()


_roster: Roster | None = None


def get_roster(settings: object | None = None) -> Roster:
    """Get the roster for the current call, built from the configured pool."""
    global _roster
    if _roster is None:
        pool = list(settings.roster_pool) if settings else []
        quiet_for = settings.roster_quiet_for if settings else 3000
        _roster = Roster(pool=pool, quiet_for=quiet_for)
    return _roster


async def quiet_check(roster: Roster, interval: float = CHECK_INTERVAL) -> None:
    """Run on the event loop, dropping participants that stay quiet too long."""
    while True:
        roster.drop_quiet(time.monotonic())
        await asyncio.sleep(interval)
