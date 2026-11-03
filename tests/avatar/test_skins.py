"""Tests for ziomek avatar skins, which are read through their definitions."""

from pathlib import Path

from ziomek.avatar.morda import Cell, read_definition
from ziomek.avatar.skins import Skin, SkinRegistry, build_registry, get_registry
from ziomek.config import Settings

from .morda_helpers import make_folder, sheet_definition


def test_a_skin_draws_the_cells_its_definition_declares(tmp_path):
    definition = read_definition(make_folder(tmp_path / "cosette", sheet_definition()))
    skin = Skin(definition=definition)
    assert skin.cell_for("happy") == Cell(row=0, column=0)  # happy names the frame called rest
    assert skin.expression_names() == ["sad", "happy"]  # the order the definition declares them in


def test_an_expression_that_names_only_files_cannot_be_drawn(tmp_path):
    definition = read_definition(
        make_folder(
            tmp_path / "cosette",
            sheet_definition(expressions={"sad": {"frame_order": ["cry"], "interval_ms": 400}}),
        )
    )
    skin = Skin(definition=definition)
    # cry is a file, so the drawing path has nothing to show for that expression.
    assert skin.cell_for("sad") is None
    assert skin.frame_count("sad") == 0
    # A name the definition does not cover still reaches the frame it falls back to.
    assert skin.cell_for("not-a-name") == Cell(row=1, column=0)


def test_the_order_and_the_timing_are_read_as_they_are_declared(tmp_path):
    definition = read_definition(
        make_folder(
            tmp_path / "cosette",
            sheet_definition(
                frames={
                    "cry": {"cell": {"row": 2, "column": 1}},
                    "rest": {"cell": {"row": 0, "column": 0}},
                    "neutral": {"cell": {"row": 1, "column": 0}},
                },
                expressions={"sad": {"frame_order": ["cry", "rest"], "interval_ms": 400, "loop": False}},
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


def test_a_skin_that_names_no_cell_is_not_registered_and_is_reported(caplog, tmp_path):
    # Every frame here names a file, so nothing in this definition can be drawn.
    definition = sheet_definition(
        frames={"cry": {"file": "parts/cry.png"}, "neutral": {"file": "parts/neutral.png"}},
        expressions={"sad": "cry"},
    )
    make_folder(
        tmp_path / "cosette",
        definition,
        sizes={"sheet.png": (100, 600), "parts/cry.png": (100, 100), "parts/neutral.png": (100, 100)},
    )
    registry = SkinRegistry(tmp_path / "nothing", default_dir=tmp_path / "cosette")
    assert registry.list() == []
    assert "cosette names no cell, so it cannot be drawn yet" in caplog.text


def test_the_registry_is_built_once_when_the_app_is_created():
    settings = Settings()
    registry = build_registry(settings)
    assert get_registry() is registry
    assert "single-frame" in registry.list()
