"""Tests for finding skins in the default directory and in the configured skins directory."""

import io
import json
import tarfile

from tests.avatar.morda_helpers import make_folder, png, sheet_definition
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
