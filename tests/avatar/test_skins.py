"""Tests for ziomek avatar skins, which are read through their definitions."""

from pathlib import Path

from ziomek.avatar.morda import Cell
from ziomek.avatar.skins import Skin, SkinRegistry, build_registry, get_registry
from ziomek.config import Settings

from .morda_helpers import first_answer, make_folder, sheet_definition


def test_a_skin_draws_the_cells_its_definition_declares(tmp_path):
    definition = first_answer(make_folder(tmp_path / "cosette", sheet_definition()))
    skin = Skin(definition=definition)
    assert skin.cell_for("happy") == Cell(row=0, column=0)  # happy names the frame called rest
    assert skin.expression_names() == ["neutral", "sad", "happy"]  # the order the definition declares them in


def test_a_frame_that_names_a_file_is_drawn_as_its_own_picture(tmp_path):
    definition = first_answer(
        make_folder(
            tmp_path / "cosette",
            sheet_definition(
                expressions={"neutral": "cry", "sad": {"frame_order": ["cry"], "interval_ms": 400}, "happy": "rest"}
            ),
        )
    )
    skin = Skin(definition=definition)
    # An image definition states no size, so the size a file reports comes from its own header.
    frame = skin.frame_descriptor(skin.entry_for("sad"))
    assert frame["kind"] == "file" and frame["file"] == "parts/cry.png"
    assert (frame["width"], frame["height"]) == (100, 100)
    # An expression the definition does not cover reaches the first entry of its neutral expression.
    assert skin.entry_for("not-a-name").file == "parts/cry.png"
    assert skin.frame_count("sad") == 1


def test_the_order_and_the_timing_are_read_as_they_are_declared(tmp_path):
    definition = first_answer(
        make_folder(
            tmp_path / "cosette",
            sheet_definition(
                frames={
                    "cry": {"cell": {"row": 2, "column": 1}},
                    "rest": {"cell": {"row": 0, "column": 0}},
                    "neutral": {"cell": {"row": 1, "column": 0}},
                },
                expressions={
                    "neutral": "rest",
                    "sad": {"frame_order": ["cry", "rest"], "interval_ms": 400, "loop": False},
                },
            ),
        )
    )
    skin = Skin(definition=definition)
    assert [frame.cell for frame in skin.order("sad")] == [Cell(row=2, column=1), Cell(row=0, column=0)]
    assert skin.interval_ms("sad") == 400
    assert skin.loops("sad") is False


def test_the_default_skin_is_read_through_its_own_definition(tmp_path):
    # A name the definition does not cover reaches what it falls back to, which is row 1.
    registry = SkinRegistry(tmp_path / "nothing")
    skin = registry.get("single-frame")
    assert skin is not None
    assert skin.cell_for("happy") == Cell(row=0, column=0)
    assert skin.cell_for("not-a-name") == Cell(row=1, column=0)


def test_a_skin_that_names_only_files_is_registered_and_drawn_as_its_own_picture(tmp_path):
    # A valid definition names at least one frame, so there is nothing here for the registry to skip.
    definition = sheet_definition(
        frames={"cry": {"file": "parts/cry.png"}, "neutral": {"file": "parts/neutral.png"}},
        expressions={"neutral": "cry", "sad": "cry"},
    )
    make_folder(
        tmp_path / "cosette",
        definition,
        sizes={"sheet.png": (100, 600), "parts/cry.png": (100, 100), "parts/neutral.png": (100, 100)},
    )
    registry = SkinRegistry(tmp_path / "nothing", default_dir=tmp_path / "cosette")
    assert registry.list() == ["cosette"]
    skin = registry.get("cosette")
    assert skin.frame_descriptor(skin.entry_for("sad"))["kind"] == "file"


def test_the_registry_is_built_once_when_the_app_is_created():
    settings = Settings()
    registry = build_registry(settings)
    assert get_registry() is registry
    assert "single-frame" in registry.list()


def test_the_setting_written_for_the_definition_is_used_for_every_frame(tmp_path):
    definition = dict(sheet_definition())
    definition["object-fit"] = "cover"
    skin = Skin(definition=first_answer(make_folder(tmp_path / "cosette", definition)))
    assert skin.fit_for(skin.definition.targets["rest"]) == "cover"


def test_a_frame_that_states_its_own_setting_is_not_read_with_the_default(tmp_path):
    definition = dict(sheet_definition())
    definition["object-fit"] = "cover"
    definition["frames"] = {
        "rest": {"cell": {"row": 0, "column": 0}, "object-fit": "fill"},
        "cry": {"file": "parts/cry.png"},
        "neutral": {"cell": {"row": 1, "column": 0}},
    }
    skin = Skin(definition=first_answer(make_folder(tmp_path / "cosette", definition)))
    assert skin.fit_for(skin.definition.targets["rest"]) == "fill"  # what it stated for itself
    assert skin.fit_for(skin.definition.targets["cry"]) == "cover"  # nothing stated, so the definition answers
    assert skin.frame_descriptor(skin.definition.targets["rest"])["fit"] == "fill"
