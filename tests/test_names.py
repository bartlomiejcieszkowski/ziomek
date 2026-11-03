"""Tests for reading the default name lists from resources."""

import json
import logging
import pathlib
import random

from ziomek.names import load_name_lists
from ziomek.roster import Roster


def write_list(root, name, content):
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.names.json").write_text(json.dumps(content), encoding="utf-8")
    return root


def test_reads_every_file_ending_with_the_suffix(tmp_path, caplog):
    write_list(tmp_path, "polish_male", ["uśmiech", "zdzwienie"])
    write_list(tmp_path, "polish_female", ["smutek"])
    (tmp_path / "not_a_list.json").write_text("[]", encoding="utf-8")

    lists = load_name_lists(tmp_path)
    assert sorted(lists) == ["polish_female", "polish_male"]
    assert lists["polish_male"] == ["uśmiech", "zdzwienie"]
    assert not caplog.records


def test_other_files_in_resources_are_not_read(tmp_path):
    write_list(tmp_path, "names", ["one"])
    (tmp_path / "names.json").write_text('["not read"]', encoding="utf-8")
    (tmp_path / "readme.md").write_text("not read", encoding="utf-8")

    assert load_name_lists(tmp_path) == {"names": ["one"]}


def test_a_file_that_cannot_be_read_is_reported_and_the_others_are_still_loaded(tmp_path, caplog):
    caplog.set_level(logging.ERROR)
    write_list(tmp_path, "polish_female", ["Ula"])

    problems = {
        "not_json": "not json",
        "not_a_list": {"names": ["one"]},
        "empty": [],
        "bad_entry": ["one", " "],
        "repeated": ["Ula", "Ula"],
    }
    for name, content in problems.items():
        (tmp_path / f"{name}.names.json").write_text(
            content if isinstance(content, str) else json.dumps(content), encoding="utf-8"
        )

    lists = load_name_lists(tmp_path)

    # Only the file that cannot be read is missing; the one that reads is kept.
    assert lists == {"polish_female": ["Ula"]}
    reported = " ".join(record.getMessage() for record in caplog.records)
    assert len(caplog.records) == len(problems)
    assert "not JSON" in reported
    assert "not a list of names" in reported
    assert "is empty" in reported
    assert "not a name" in reported
    assert "more than once" in reported


def test_names_that_differ_only_by_diacritics_are_kept_as_different_names(tmp_path):
    assert load_name_lists(write_list(tmp_path, "polish_female", ["Łucja", "Lucja"])) == {
        "polish_female": ["Łucja", "Lucja"]
    }


def test_a_name_is_taken_from_any_loaded_list_when_no_name_is_given():
    roster = Roster(
        name_lists={"polish_male": ["Albin", "Bartosz"], "polish_female": ["Łucja", "Ula"]},
        rng=random.Random(3),
    )
    taken_names = {roster.join().name for _ in range(4)}

    assert taken_names == {"Albin", "Bartosz", "Łucja", "Ula"}


def test_a_name_that_is_in_the_call_is_not_taken_again_from_the_lists():
    roster = Roster(name_lists={"polish_female": ["Ula"]})
    first = roster.join()
    second = roster.join("Zuzanna")

    assert first.name == "Ula"
    assert second.name == "Zuzanna"


def test_the_least_used_name_is_taken_when_names_from_earlier_calls_have_all_been_used():
    roster = Roster(name_lists={"polish_male": ["Albin", "Bartosz"]})
    for name in ("Albin", "Bartosz", "Bartosz"):
        roster.join(name)
        roster.end_call()

    # Usage history stays across calls, so the name used less is handed out again.
    assert roster.join().name == "Albin"


def test_a_name_listed_in_the_pool_is_taken_before_the_loaded_lists():
    roster = Roster(pool=[("John", "alice")], name_lists={"polish_female": ["Ula"]})

    assert roster.join().name == "John"


def test_get_roster_uses_the_lists_loaded_from_resources(tmp_path, monkeypatch):
    class settings:
        roster_pool = []
        roster_words = []
        roster_avatar = "single-frame"
        roster_quiet_for = 3000

    import ziomek.names as names_module
    import ziomek.roster as module

    monkeypatch.setattr(names_module, "RESOURCES_DIR", write_list(tmp_path, "kept", ["Ula"]))
    module._roster = None

    roster = module.build_roster(settings())
    assert roster.name_lists == {"kept": ["Ula"]}
    assert roster.join().name == "Ula"


def test_a_bad_list_file_does_not_stop_the_roster_from_being_built(tmp_path, monkeypatch, caplog):
    class settings:
        roster_pool = []
        roster_words = []
        roster_avatar = "single-frame"
        roster_quiet_for = 3000

    caplog.set_level(logging.ERROR)
    import ziomek.names as names_module
    import ziomek.roster as module

    write_list(tmp_path, "kept", ["Ula"])
    (tmp_path / "broken.names.json").write_text("not json", encoding="utf-8")
    monkeypatch.setattr(names_module, "RESOURCES_DIR", pathlib.Path(tmp_path))
    module._roster = None

    roster = module.build_roster(settings())

    # The bad file is reported, the good one still loads, and the roster works.
    assert roster.name_lists == {"kept": ["Ula"]}
    assert any("broken.names.json" in record.getMessage() for record in caplog.records)
    assert roster.join().name == "Ula"
