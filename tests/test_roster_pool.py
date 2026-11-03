"""Names and voices come from a configurable pool, with the usage rules."""

import random

from ziomek.roster import Roster


def test_join_assigns_from_the_pool_when_no_name_is_given():
    roster = Roster(pool=[("John", "alice"), ("Donald", "bob")], rng=random.Random(0))
    participant = roster.join()

    assert participant.name in ("John", "Donald")
    assert participant.voice in ("alice", "bob")


def test_used_entries_are_not_handed_out_again():
    roster = Roster(pool=[("John", "alice"), ("Donald", "bob")])
    a = roster.join()
    b = roster.join()

    assert {a.name, b.name} == {"John", "Donald"}
    assert {a.voice, b.voice} == {"alice", "bob"}


def test_a_stated_name_and_voice_are_used_as_given():
    roster = Roster(pool=[("John", "alice")], words=["compiling"])
    participant = roster.join("Mary", voice="carol")

    assert participant.name == "Mary"
    assert participant.voice == "carol"


def test_the_least_used_entry_is_given_when_every_entry_has_been_used():
    pool = [("John", "alice"), ("Donald", "bob"), ("Kate", "carol")]
    roster = Roster(pool=pool, rng=random.Random(0))

    # Usage history stays across calls, so entries used more keep a higher count.
    for _ in range(3):
        roster.join("John")
        roster.end_call()
    for _ in range(2):
        roster.join("Donald")
        roster.end_call()
    roster.join("Kate")
    roster.end_call()

    participant = roster.join()
    assert participant.name == "Kate"
    assert participant.usage == 2


def test_usage_counts_are_kept_across_calls():
    pool = [("John", "alice"), ("Donald", "bob")]
    roster = Roster(pool=pool, rng=random.Random(0))
    first = roster.join()
    used = first.name

    assert used in ("John", "Donald")
    assert roster.usage_counts[used] == 1

    roster.end_call()
    assert roster.usage_counts == {used: 1}
    assert roster.participants == []

    # In a new call nothing is present, so history decides: the other name is given.
    second = roster.join()
    assert second.name != used


def test_the_name_gets_a_word_as_the_taken_part_when_names_run_out():
    pool = [("John", "alice")]
    roster = Roster(pool=pool, words=["compiling", "reading"], rng=random.Random(0))
    first = roster.join()

    assert first.name == "John"

    # The name is taken in the call, so the second part comes from the words.
    second = roster.join()
    assert second.name.split(" ")[0] == "John"
    assert second.name.split(" ")[1] in ("compiling", "reading")
    assert second.name != first.name


def test_a_quiet_participant_is_dropped_and_its_entry_is_released():
    roster = Roster(pool=[("John", "alice")], quiet_for=3000)
    participant = roster.join()
    participant.last_seen = 0.0

    assert roster.drop_quiet(now=2999.0) == []
    dropped = roster.drop_quiet(now=3000.0)

    assert [p.name for p in dropped] == ["John"]
    assert participant.state == "left"
    assert roster.participants == []

    # The entry is free again for the next pick, and the usage history stays.
    assert roster.usage_counts == {"John": 1}
    assert roster.join().name == "John"


def test_a_participant_on_hold_is_not_counted_by_the_timer():
    roster = Roster(pool=[("John A.", "alice")], quiet_for=100)
    participant = roster.join()
    participant.last_seen = 0.0
    participant.hold()

    assert roster.drop_quiet(now=10_000.0) == []
    assert participant.state == "held"


def test_get_roster_uses_the_configured_words():
    class settings:
        roster_pool = [("John", "alice", "")]
        roster_words = ["compiling"]
        roster_avatar = "single-frame"
        roster_quiet_for = 3000

    import ziomek.roster as module

    module._roster = None
    # With no names left in the pool or the lists, the second part comes from the words.
    roster = module.build_roster(settings())
    roster.name_lists = {}
    first = roster.join()
    second = roster.join()

    assert first.name == "John"
    assert second.name == "John compiling"


def test_the_voice_for_a_combined_name_stays_on_the_pool_entry_of_its_first_part():
    roster = Roster(pool=[("John", "alice")], words=["compiling"], rng=random.Random(0))

    first = roster.join()
    assert first.name == "John"
    assert first.voice == "alice"

    second = roster.join()
    assert second.name.startswith("John")
    assert second.voice == "alice"
