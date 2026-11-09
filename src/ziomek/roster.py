"""Roster — participants in one call."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass

from ziomek.names import load_name_lists
from ziomek.tts.voices import VOICES


@dataclass
class TextEntry:
    """A line of text belonging to a participant, with the author who wrote it."""

    text: str
    author: str

    def as_dict(self) -> dict:
        """The entry as the page reads it, with the author kept."""
        return {"text": self.text, "author": self.author}


class DuplicateNameError(ValueError):
    """A name cannot be used twice inside one call."""


class Participant:
    """A participant in a call, holding its name, its own text, and what happened to it."""

    def __init__(
        self,
        name: str,
        roster: "Roster | None" = None,
        voice: str | None = None,
        skin: str | None = None,
        persona: str | None = None,
    ) -> None:
        self.name = name
        # The name shown on the page is fixed at join and never taken again.
        self.display_name = name
        self.voice = voice
        # The skin that draws this participant's face, taken from its pool entry.
        self.skin = skin
        # Text recorded for the participant. Nothing reads it yet, so it is only held.
        self.persona = persona
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
        if self.roster is not None:
            self.roster.record(self.name, "text", text=text, author=author)
        return entry

    def hold(self) -> None:
        """The participant is quiet for a while, so inactivity is not counted."""
        self.state = "held"
        self.held_at = time.monotonic()
        if self.roster is not None:
            self.roster.report_change("room")
            self.roster.record(self.name, "hold")

    def resume(self) -> None:
        """Count inactivity again."""
        self.state = "active"
        self.held_at = None
        if self.roster is not None:
            self.roster.report_change("room")
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
        changed=None,
        default_skin: str = "single-frame",
        name_lists: dict[str, list[str]] | None = None,
        voices: list[str] | None = None,
        skins: list[str] | None = None,
    ) -> None:
        self.pool: list[tuple[str, str, str]] = list(pool or [])
        # Used when an entry names no skin, which is the config default.
        self.default_skin = default_skin
        self.state_machine_factory = state_machine_factory
        # The view push is attached to every machine the roster makes, so a participant's
        # expression change reaches the page instead of being polled.
        self.push_hook = push_hook
        # Which part changed is reported here, so a page can ask for that part alone. A call built
        # without this reports nothing.
        self.changed = changed
        # Words are the second part of a name when the first part is taken in the call.
        self.words: list[str] = list(words or [])
        # Name lists from the package resources, read as one pool of names.
        self.name_lists: dict[str, list[str]] = {k: list(v) for k, v in (name_lists or {}).items()}
        # The sets a name that is not in the pool is drawn from, in order.
        self.voices: list[str] = list(voices or VOICES)
        self.skins: list[str] = list(skins or [])
        self.quiet_for = quiet_for
        self.rng = rng or random.Random()
        self.participants: list[Participant] = []
        # Usage counts are kept only while the call is open.
        self.usage_counts: dict[str, int] = {}
        # The voice and the face a name was drawn with stay, so a rejoin gets the same pair.
        self.assigned: dict[str, tuple[str | None, str | None]] = {}
        # Where the round-robin stands in each set, so picks move forward instead of repeating.
        self.cursor: dict[str, int] = {}
        # What happened during this call, kept only while it is open.
        self.events: list[dict] = []

    def join(
        self, name: str | None = None, voice: str | None = None, skin: str | None = None, persona: str | None = None
    ) -> Participant:
        if name is not None and any(p.name == name for p in self.participants):
            raise DuplicateNameError(f"duplicate name in the call: {name}")
        participant = Participant(name=name or "", roster=self, voice=voice, skin=skin, persona=persona)
        if name is None:
            participant.name = self._pick_name()
        participant.display_name = participant.name
        # The name is picked first, so the voice and the face are drawn for it.
        first = self._key(participant.name)
        if voice is None:
            participant.voice = self._pick_voice(participant.name)
        # What was given for a face is taken before anything is drawn for the name.
        if skin is None:
            participant.skin = self._pick_skin(participant.name)
        self.assigned[first] = (participant.voice, participant.skin)
        # Usage is tracked on the entry a name belongs to.
        participant.usage = self._count(first)
        # Each participant drives its own state machine, reading the name and text
        # areas from its own record.
        participant.state_machine = self._machine_for(participant)
        self.participants.append(participant)
        # A participant added to the call is a change to the room, and the join entry below is a
        # change to the record, so both are reported.
        self.report_change("room")
        # The join entry carries what was drawn for the name, so the record shows the assignment.
        self.record(participant.name, "join", voice=participant.voice, skin=participant.skin)
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
        # A call that is already empty has no end to it, so a check that dropped nothing reports nothing.
        if dropped and not self.participants:
            self.end_call()
        return dropped

    def release(self, participant: Participant) -> None:
        """Release the pool entry; the usage history stays for the next pick."""
        if participant in self.participants:
            self.participants.remove(participant)
            self.report_change("room")

    def report_change(self, kind: str) -> None:
        """Report which part changed, so a page can ask for that part alone.

        A call that was built without anything to report to does nothing here.
        """
        if self.changed is None:
            return
        self.changed(kind)

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
        taken = {p.name for p in self.participants}

        # A name listed in the pool comes first, otherwise a name from the loaded lists.
        free = [entry for entry in self.pool if entry[0] not in taken]
        if free:
            # Prefer an entry that has not been used, otherwise the least used one.
            unused = [entry for entry in free if self.usage_counts.get(entry[0], 0) == 0]
            if unused:
                return self.rng.choice(unused)[0]
            lowest = min(self.usage_counts.get(entry[0], 0) for entry in free)
            return self.rng.choice([e for e in free if self.usage_counts.get(e[0], 0) == lowest])[0]

        names = [name for names in self.name_lists.values() for name in names if name not in taken]
        if names:
            # Every loaded list is one pool, so a name is taken from any of them.
            unused = [name for name in names if self.usage_counts.get(name, 0) == 0]
            if unused:
                return self.rng.choice(unused)
            counts = {name: self.usage_counts.get(name, 0) for name in names}
            lowest = min(counts.values())
            return self.rng.choice([name for name in names if counts[name] == lowest])

        if not self.pool or not self.words:
            return ""

        # Every first name is in the call, so the second part comes from the words.
        base = self.rng.choice(self._candidates(0))[0]
        combos = [f"{base} {word}" for word in self.words if f"{base} {word}" not in taken]
        if not combos:
            return ""
        return self.rng.choice(combos)

    def _key(self, name: str) -> str:
        """The entry a name belongs to: itself when an entry holds it, otherwise its first part."""
        for entry in self.pool:
            if entry[0] == name:
                return name
        return name.split(" ")[0]

    def _draw(self, field: str, source: list[str], held: set[str]) -> str | None:
        """Take the next entry of a set in order, skipping the ones held in the call."""
        if not source:
            return None
        start = self.cursor.get(field, 0)
        for step in range(len(source)):
            index = (start + step) % len(source)
            if source[index] not in held:
                self.cursor[field] = (index + 1) % len(source)
                return source[index]
        # Nothing is free, so the round-robin wraps and the next entry is reused.
        return source[start]

    def _pick_voice(self, name: str) -> str | None:
        """Take the voice stated for this name, otherwise the one remembered or drawn for it."""
        first = self._key(name)
        for entry in self.pool:
            if entry[0] == first and entry[1]:
                return entry[1]
        remembered = self.assigned.get(first)
        if remembered and remembered[0]:
            return remembered[0]
        return self._draw("voice", self.voices, {p.voice for p in self.participants if p.voice})

    def _pick_skin(self, name: str) -> str | None:
        """Take the face stated for this name, otherwise the one remembered or drawn for it."""
        first = self._key(name)
        for entry in self.pool:
            if entry[0] == first and len(entry) > 2 and entry[2]:
                return entry[2]
        remembered = self.assigned.get(first)
        if remembered and remembered[1]:
            return remembered[1]
        drawn = self._draw("skin", self.skins, {p.skin for p in self.participants if p.skin})
        # With no face registered there is nothing to draw from, so the configured one applies.
        return drawn or self.default_skin or None

    def record(
        self,
        name: str,
        action: str,
        text: str | None = None,
        author: str | None = None,
        voice: str | None = None,
        skin: str | None = None,
    ) -> dict:
        """Note what happened, on the call record and on the participant's own record.

        The text and its author are included only when there is something attached to the
        event, so an entry for a plain join, hold or leave stays comparable. The voice and the
        face are recorded only for a join, because that is where they are decided."""
        entry = {"name": name, "action": action}
        if text is not None:
            entry["text"] = text
        if author is not None:
            entry["author"] = author
        if voice is not None:
            entry["voice"] = voice
        if skin is not None:
            entry["skin"] = skin
        self.events.append(entry)
        self.report_change("record")
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
        # The record is gone, so a page that drew it has to be told this changed as well.
        self.report_change("record")


_roster: Roster | None = None


def build_roster(settings) -> Roster:
    """Build the roster for the current call from the configured pool."""
    global _roster
    from ziomek.api import avatar_ws, roster_ws
    from ziomek.avatar.skins import get_registry

    registry = get_registry()
    _roster = Roster(
        pool=list(settings.roster_pool),
        words=list(settings.roster_words),
        name_lists=load_name_lists(),
        skins=list(registry.list()) if registry else [],
        quiet_for=settings.roster_quiet_for,
        push_hook=avatar_ws.notify_change,
        changed=roster_ws.tell_page,
        default_skin=settings.roster_avatar,
    )
    return _roster


def get_roster() -> Roster:
    """Get the roster for the current call.

    The call owns its roster. The caller builds it from settings with build_roster.
    """
    if _roster is None:
        raise RuntimeError("the roster for this call was not built")
    return _roster


async def quiet_check(roster: Roster, interval: float) -> None:
    """Run on the event loop, dropping participants that stay quiet too long."""
    while True:
        roster.drop_quiet(time.monotonic())
        await asyncio.sleep(interval)
