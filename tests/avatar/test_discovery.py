"""Tests for finding skins in the default directory and in the configured skins directory."""

import io
import json
import tarfile

from tests.avatar.morda_helpers import make_archive, make_bundle, make_folder, png, sheet_definition
from ziomek.avatar import discovery
from ziomek.avatar.discovery import find_definitions


def test_the_default_skin_is_found_before_the_searched_directory(tmp_path):
    package = tmp_path / "package"
    make_folder(package / "single-frame", sheet_definition(name="single-frame"))
    make_folder(tmp_path / "skins" / "cosette", sheet_definition())

    found = find_definitions(tmp_path / "skins", default_dir=package)
    assert [definition.name for definition in found] == ["single-frame", "cosette"]


def test_a_definition_at_the_root_of_a_directory_counts_as_a_skin(tmp_path):
    make_folder(
        tmp_path / "skins",
        sheet_definition(
            frames={"rest": {"cell": {"row": 0, "column": 0}}},
            expressions={"happy": "rest"},
            fallback="rest",
        ),
        sizes={"sheet.png": (100, 600)},
    )

    found = find_definitions(tmp_path / "skins", default_dir=tmp_path / "nothing")
    assert [definition.name for definition in found] == ["cosette"]


def test_the_first_claimer_keeps_its_name_and_the_rest_get_a_suffix(tmp_path, caplog):
    make_folder(tmp_path / "skins/a", sheet_definition())
    make_folder(tmp_path / "skins/b", sheet_definition(name="cosette"))
    make_folder(tmp_path / "skins/c", sheet_definition(name="cosette"))

    found = find_definitions(tmp_path / "skins", default_dir=tmp_path / "nothing")
    assert [definition.name for definition in found] == ["cosette", "cosette_2", "cosette_3"]
    messages = [record.message for record in caplog.records if record.levelname == "ERROR"]
    assert any("the name cosette is claimed by" in message for message in messages)
    assert len(messages) == 2


def test_a_definition_that_does_not_read_is_reported_and_skipped(tmp_path, caplog):
    make_folder(
        tmp_path / "skins/broken",
        {"name": "broken", "type": "image", "expressions": {}},
        sizes={},
    )
    make_folder(tmp_path / "skins/working", sheet_definition())

    found = find_definitions(tmp_path / "skins", default_dir=tmp_path / "nothing")
    assert [definition.name for definition in found] == ["cosette"]
    assert any("broken" in record.message for record in caplog.records if record.levelname == "ERROR")


def test_a_folder_without_a_definition_is_not_a_skin(tmp_path):
    (tmp_path / "skins/pictures").mkdir(parents=True)
    (tmp_path / "skins/pictures/happy.png").write_bytes(png(100, 100))

    assert find_definitions(tmp_path / "skins", default_dir=tmp_path / "nothing") == []


def test_an_archive_in_the_directory_is_read_without_extracting(tmp_path):
    archive = tmp_path / "skins/cosette.morda"
    archive.parent.mkdir(parents=True)
    text = json.dumps(
        sheet_definition(
            frames={"rest": {"cell": {"row": 0, "column": 0}}},
            expressions={"happy": "rest"},
            fallback="rest",
        )
    ).encode("utf-8")
    image = png(100, 600)
    with tarfile.open(archive, "w") as out:
        for name, data in (("morda.json", text), ("sheet.png", image)):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            out.addfile(info, io.BytesIO(data))

    found = find_definitions(tmp_path / "skins", default_dir=tmp_path / "nothing")
    assert [definition.name for definition in found] == ["cosette"]


def test_a_bundle_that_holds_only_names_for_avatars_counts_as_a_skin(tmp_path):
    bundle = make_bundle(tmp_path / "single-frame", {"blue.morda.json": sheet_definition(name="single-frame-blue")})

    assert [definition.name for definition in find_definitions(tmp_path, default_dir=tmp_path / "nothing")] == [
        "single-frame-blue"
    ]


def test_an_archive_that_holds_no_definition_is_not_a_skin(tmp_path):
    skins = tmp_path / "skins"
    skins.mkdir()
    archive = skins / "pictures.morda"
    with tarfile.open(archive, "w") as out:
        data = png(100, 100)
        info = tarfile.TarInfo("cry.png")
        info.size = len(data)
        out.addfile(info, io.BytesIO(data))

    assert find_definitions(skins, default_dir=tmp_path / "nothing") == []


def test_the_order_inside_a_bundle_decides_who_keeps_a_name(tmp_path, caplog):
    bundle = make_bundle(
        tmp_path / "single-frame",
        {
            "aaa.morda.json": sheet_definition(name="cosette"),
            "morda.json": sheet_definition(name="cosette"),
        },
    )

    found = find_definitions(tmp_path, default_dir=tmp_path / "nothing")
    assert [definition.name for definition in found] == ["cosette", "cosette_2"]
    messages = [record.message for record in caplog.records if record.levelname == "ERROR"]
    assert any("the name cosette is claimed by" in message for message in messages)


def test_a_name_taken_by_another_definition_is_reported_with_the_file_that_carries_it(tmp_path, caplog):
    """Several definitions in one bundle can claim the same name, so what is reported has to say which file carries which claim."""
    folder = make_bundle(
        tmp_path / "single-frame",
        {"aaa.morda.json": sheet_definition(name="cosette"), "morda.json": sheet_definition(name="cosette")},
    )

    find_definitions(tmp_path, default_dir=tmp_path / "nothing")
    messages = [record.message for record in caplog.records if record.levelname == "ERROR"]
    claim = [message for message in messages if "the name cosette is claimed by" in message]
    assert claim
    assert all(str(folder / "morda.json") in message and str(folder / "aaa.morda.json") in message for message in claim)


def test_a_source_is_decided_from_the_same_reading_that_answers_its_definitions(tmp_path, monkeypatch):
    """Deciding whether something is a skin and answering what it holds are one reading, so an archive is not opened twice for the same run."""
    bundle = make_bundle(
        tmp_path / "build",
        {"morda.json": sheet_definition(name="cosette"), "aaa.morda.json": sheet_definition(name="cosette-blue")},
    )
    (tmp_path / "skins").mkdir()
    make_archive(bundle, tmp_path / "skins" / "single-frame.morda")

    reads = []
    read_once = discovery.read_entries

    def counting_read(source, errors=None):
        reads.append(source)
        return read_once(source, errors)

    monkeypatch.setattr(discovery, "read_entries", counting_read)
    found = find_definitions(tmp_path / "skins", default_dir=tmp_path / "nothing")

    assert [definition.name for definition in found] == ["cosette", "cosette-blue"]
    assert len(reads) == 1, f"the source was read {len(reads)} times"
