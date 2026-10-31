"""Roster — participants in one call."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass


@dataclass
class TextEntry:
    """A line of text belonging to a participant, with the author who wrote it."""

    text: str
    author: str


class DuplicateNameError(ValueError):
    """A name cannot be used twice inside one call."""


class Participant:
    """A participant in a call, holding its name, its own text, and what happened to it."""

    def __init__(
        self,
        name: str,
        roster: "Roster | None" = None,
        voice: str | None = None,
    ) -> None:
        self.name = name
        # The name shown on the page is fixed at join and never taken again.
        self.display_name = name
        self.voice = voice
        self.texts: list[TextEntry] = []
        # What happened to this participant during the current call.
        self.events: list[dict] = []
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
        words: list[str] | None = None,
        quiet_for: int = 3000,
        rng: random.Random | None = None,
        state_machine_factory=None,
        push_hook=None,
    ) -> None:
        self.pool: list[tuple[str, str]] = list(pool or [])
        self.state_machine_factory = state_machine_factory
        # The view push is attached to every machine the roster makes, so a participant's
        # expression change reaches the page instead of being polled.
        self.push_hook = push_hook
        # Words are the second part of a name when the first part is taken in the call.
        self.words: list[str] = list(words or [])
        self.quiet_for = quiet_for
        self.rng = rng or random.Random()
        self.participants: list[Participant] = []
        # Usage counts are kept only while the call is open.
        self.usage_counts: dict[str, int] = {}
        # What happened during this call, kept only while it is open.
        self.events: list[dict] = []

    def join(self, name: str | None = None, voice: str | None = None) -> Participant:
        if name is not None and any(p.name == name for p in self.participants):
            raise DuplicateNameError(f"duplicate name in the call: {name}")
        participant = Participant(name=name or "", roster=self, voice=voice)
        if name is None:
            participant.name = self._pick_name()
        participant.display_name = participant.name
        if voice is None:
            participant.voice = self._pick_voice(participant.name)
        # Usage is tracked on the first part of the name, the one that comes from the pool.
        participant.usage = self._count(participant.name.split(" ")[0])
        # Each participant drives its own state machine, reading the name and text
        # areas from its own record.
        participant.state_machine = self._machine_for(participant)
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
        """Release the pool entry; the usage history stays for the next pick."""
        if participant in self.participants:
            self.participants.remove(participant)

    def _count(self, name: str) -> int:
        count = self.usage_counts.get(name, 0) + 1
        self.usage_counts[name] = count
        return count

    def _machine_for(self, participant: Participant):
        """Build the state machine for one participant."""
        factory = self.state_machine_factory
        if factory is None:
            from ziomek.avatar.state_machine import AvatarStateMachine

            factory = AvatarStateMachine
        machine = factory(participant)
        machine.on_change = self.push_hook
        return machine

    def _candidates(self, key: int) -> list[tuple[str, str]]:
        """Entries with the lowest usage count for the given pool field."""
        counts = {entry[0]: self.usage_counts.get(entry[0], 0) for entry in self.pool}
        lowest = min(counts.values()) if counts else 0
        return [entry for entry in self.pool if counts[entry[0]] == lowest]

    def _pick_name(self) -> str:
        if not self.pool:
            return ""
        taken = {p.name for p in self.participants}
        free = [entry for entry in self.pool if entry[0] not in taken]
        if free:
            # Prefer an entry that has not been used, otherwise the least used one.
            unused = [entry for entry in free if self.usage_counts.get(entry[0], 0) == 0]
            if unused:
                return self.rng.choice(unused)[0]
            lowest = min(self.usage_counts.get(entry[0], 0) for entry in free)
            return self.rng.choice([e for e in free if self.usage_counts.get(e[0], 0) == lowest])[0]

        # Every first name is in the call, so the second part comes from the words.
        if not self.words:
            return ""
        base = self.rng.choice(self._candidates(0))[0]
        combos = [f"{base} {word}" for word in self.words if f"{base} {word}" not in taken]
        if not combos:
            return ""
        return self.rng.choice(combos)

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

    def record(self, name: str, action: str) -> dict:
        """Note what happened, on the call record and on the participant's own record."""
        entry = {"name": name, "action": action}
        self.events.append(entry)
        participant = self._find(name)
        if participant is not None:
            participant.events.append(entry)
        return entry

    def _find(self, name: str) -> Participant | None:
        for participant in self.participants:
            if participant.name == name:
                return participant
        return None

    def end_call(self) -> None:
        """Drop the participants and the record; the usage history stays for the next call."""
        self.participants.clear()
        self.events.clear()


_roster: Roster | None = None


def get_roster(settings: object | None = None) -> Roster:
    """Get the roster for the current call, built from the configured pool."""
    global _roster
    if _roster is None:
        from ziomek.api import avatar_ws

        pool = list(settings.roster_pool) if settings else []
        quiet_for = settings.roster_quiet_for if settings else 3000
        _roster = Roster(
            pool=pool,
            words=list(settings.roster_words) if settings else [],
            quiet_for=quiet_for,
            push_hook=avatar_ws.notify_change,
        )
    return _roster


async def quiet_check(roster: Roster, interval: float) -> None:
    """Run on the event loop, dropping participants that stay quiet too long."""
    while True:
        roster.drop_quiet(time.monotonic())
        await asyncio.sleep(interval)
