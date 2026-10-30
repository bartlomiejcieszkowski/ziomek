"""Names and voices come from a configurable pool, with the usage rules."""

import random

from ziomek.roster import Roster


def test_join_assigns_from_the_pool_when_no_name_is_given():
    roster = Roster(pool=[("John A.", "alice"), ("Mary S.", "bob")], rng=random.Random(0))
    participant = roster.join()

    assert participant.name in ("John A.", "Mary S.")
    assert participant.voice in ("alice", "bob")


def test_used_entries_are_not_handed_out_again():
    roster = Roster(pool=[("John A.", "alice"), ("Mary S.", "bob")])
    a = roster.join()
    b = roster.join()

    assert {a.name, b.name} == {"John A.", "Mary S."}
    assert {a.voice, b.voice} == {"alice", "bob"}


def test_a_stated_name_and_voice_are_used_as_given():
    roster = Roster(pool=[("John A.", "alice")])
    participant = roster.join("Mary S.", voice="carol")

    assert participant.name == "Mary S."
    assert participant.voice == "carol"


def test_when_every_entry_is_used_the_least_used_one_is_given():
    pool = [("John A.", "alice"), ("Mary S.", "bob"), ("Kate C.", "carol")]
    roster = Roster(pool=pool, rng=random.Random(0))

    # Make one entry clearly the most used: a name that left can be used again in the call.
    first = roster.join("John A.")
    first.leave()
    roster.join("John A.")
    roster.join("Mary S.")
    roster.join("Kate C.")

    participant = roster.join()
    assert participant.name in ("Mary S.", "Kate C.")
    assert participant.usage == 2


def test_usage_counts_are_kept_only_while_the_call_is_open():
    roster = Roster(pool=[("John A.", "alice")])
    roster.join()
    roster.end_call()

    assert roster.usage_counts == {}
    participant = roster.join()
    assert participant.usage == 1


def test_a_quiet_participant_is_dropped_and_its_entry_is_released():
    roster = Roster(pool=[("John A.", "alice")], quiet_for=3000)
    participant = roster.join()
    participant.last_seen = 0.0

    assert roster.drop_quiet(now=2999.0) == []
    dropped = roster.drop_quiet(now=3000.0)

    assert [p.name for p in dropped] == ["John A."]
    assert participant.state == "left"
    assert roster.participants == []
    assert roster.usage_counts == {}


def test_a_participant_on_hold_is_not_counted_by_the_timer():
    roster = Roster(pool=[("John A.", "alice")], quiet_for=100)
    participant = roster.join()
    participant.last_seen = 0.0
    participant.hold()

    assert roster.drop_quiet(now=10_000.0) == []
    assert participant.state == "held"
