"""Tests for reading a skin definition from a folder or an archive."""

import io
import tarfile

import pytest

from tests.avatar.morda_helpers import make_folder, png, sheet_definition
from ziomek.avatar.morda import DefinitionError, fallback_target, read_definition


def read_errors(root, definition, sizes=None):
    folder = make_folder(root, definition, sizes)
    with pytest.raises(DefinitionError) as exc:
        read_definition(folder)
    return exc.value.errors


def test_read_definition_from_folder(tmp_path):
    definition = read_definition(make_folder(tmp_path / "cosette", sheet_definition()))
    assert definition.name == "cosette"
    assert definition.type == "sheet"
    assert (definition.grid.rows, definition.grid.columns) == (6, 1)
    assert definition.sheet.file == "sheet.png"
    assert definition.targets["rest"].cell.row == 0
    assert definition.targets["cry"].file == "parts/cry.png"
    order = definition.expressions["sad"]
    assert [entry.name for entry in order.entries] == ["cry", "rest"]
    assert order.interval_ms == 400


def test_read_definition_from_archive(tmp_path):
    folder = make_folder(tmp_path / "cosette", sheet_definition())
    archive = tmp_path / "cosette.morda"
    with tarfile.open(archive, "w") as out:
        for name in sorted(["morda.json", "sheet.png", "parts/cry.png"]):
            data = (folder / name).read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            out.addfile(info, io.BytesIO(data))

    definition = read_definition(archive)
    assert definition.name == "cosette"
    assert definition.targets["cry"].file == "parts/cry.png"
    assert definition.expressions["happy"].entries[0].name == "rest"


def test_missing_definition_file(tmp_path):
    folder = tmp_path / "cosette"
    folder.mkdir()
    (folder / "sheet.png").write_bytes(png(100, 600))
    with pytest.raises(DefinitionError) as exc:
        read_definition(folder)
    assert any("no morda.json" in error for error in exc.value.errors)


def test_referenced_file_not_present(tmp_path):
    folder = make_folder(tmp_path / "cosette", sheet_definition())
    (folder / "parts/cry.png").unlink()
    with pytest.raises(DefinitionError) as exc:
        read_definition(folder)
    assert any("parts/cry.png is referenced but not present" in error for error in exc.value.errors)


def test_grid_mismatch_reported_as_one_error(tmp_path):
    errors = read_errors(
        tmp_path / "cosette", sheet_definition(), sizes={"sheet.png": (100, 500), "parts/cry.png": (100, 100)}
    )
    mismatch = [error for error in errors if "reports 100x500" in error]
    assert len(mismatch) == 1


def test_entry_name_reaching_outside(tmp_path):
    errors = read_errors(tmp_path / "cosette", sheet_definition(sheet={"file": "../secret.png"}))
    assert any("../secret.png is not an entry name" in error for error in errors)


def test_reference_to_undeclared_name(tmp_path):
    errors = read_errors(tmp_path / "cosette", sheet_definition(expressions={"happy": "smile"}))
    assert any("smile is referenced but not declared" in error for error in errors)


def test_multi_frame_order_without_interval(tmp_path):
    errors = read_errors(
        tmp_path / "cosette",
        sheet_definition(expressions={"sad": {"frame_order": ["cry", "rest"]}}),
    )
    assert any("expressions.sad" in error for error in errors)


def test_cell_in_image_definition(tmp_path):
    definition = {
        "name": "cosette",
        "type": "image",
        "frames": {"cry": {"file": "cry.png"}, "smile": {"cell": {"row": 0, "column": 1}}},
        "expressions": {"sad": "cry"},
    }
    errors = read_errors(tmp_path / "cosette", definition, sizes={"cry.png": (100, 100)})
    assert any("frames.smile" in error for error in errors)


def test_symlink_not_followed(tmp_path):
    folder = make_folder(tmp_path / "cosette", sheet_definition())
    link = folder / "link.png"
    try:
        link.symlink_to(folder / "parts/cry.png")
    except OSError:
        pytest.skip("symlinks are not available here")
    with pytest.raises(DefinitionError) as exc:
        read_definition(folder)
    assert any("is a symlink, which is not followed" in error for error in exc.value.errors)


def test_loop_defaults_to_true(tmp_path):
    definition = read_definition(make_folder(tmp_path / "cosette", sheet_definition()))
    assert definition.expressions["sad"].loop is True


def test_loop_can_be_read_as_false(tmp_path):
    expression = {"sad": {"frame_order": ["cry", "rest"], "interval_ms": 400, "loop": False}}
    definition = read_definition(make_folder(tmp_path / "cosette", sheet_definition(expressions=expression)))
    assert definition.expressions["sad"].loop is False


def test_loop_on_a_single_frame_is_accepted_and_changes_nothing(tmp_path):
    expression = {"happy": {"frame_order": ["rest"], "loop": True}}
    definition = read_definition(make_folder(tmp_path / "cosette", sheet_definition(expressions=expression)))
    order = definition.expressions["happy"]
    assert len(order.entries) == 1
    assert order.interval_ms is None
    assert order.loop is True


def test_undefined_expression_uses_the_declared_fallback(tmp_path):
    definition = read_definition(make_folder(tmp_path / "cosette", sheet_definition(fallback="rest")))
    assert fallback_target(definition).cell.row == 0


def test_no_fallback_uses_neutral(tmp_path):
    definition = read_definition(
        make_folder(
            tmp_path / "cosette",
            sheet_definition(
                frames={"neutral": {"cell": {"row": 1, "column": 0}}},
                expressions={"sad": "neutral"},
            ),
            {"sheet.png": (100, 600)},
        )
    )
    assert fallback_target(definition).cell.row == 1


def test_no_fallback_and_no_neutral_is_reported_as_an_error(tmp_path):
    errors = read_errors(
        tmp_path / "cosette",
        sheet_definition(
            frames={"cry": {"file": "parts/cry.png"}, "rest": {"cell": {"row": 0, "column": 0}}},
            expressions={"sad": "cry"},
        ),
    )
    assert any("neutral" in error for error in errors)


def test_the_setting_of_the_whole_definition_is_read(tmp_path):
    definition = dict(sheet_definition())
    definition["object-fit"] = "cover"
    definition = read_definition(make_folder(tmp_path / "cosette", definition))
    assert definition.fit == "cover"


def test_nothing_stated_keeps_the_default_that_the_reader_applies(tmp_path):
    # A default written in the schema is an annotation, so the reader is what applies it.
    definition = read_definition(make_folder(tmp_path / "cosette", sheet_definition()))
    assert definition.fit == "contain"
    assert definition.targets["rest"].fit is None


def test_a_target_can_state_the_setting_for_itself(tmp_path):
    definition = dict(sheet_definition())
    definition["frames"] = {
        "rest": {"cell": {"row": 0, "column": 0}, "object-fit": "fill"},
        "cry": {"file": "parts/cry.png"},
        "neutral": {"cell": {"row": 1, "column": 0}},
    }
    definition = read_definition(make_folder(tmp_path / "cosette", definition))
    assert definition.targets["rest"].fit == "fill"
    assert definition.targets["cry"].fit is None  # nothing stated for itself, so the definition answers


def test_a_setting_that_is_not_one_of_the_values_is_reported(tmp_path):
    definition = dict(sheet_definition())
    definition["object-fit"] = "stretch"
    errors = read_errors(tmp_path / "cosette", definition)
    assert any("object-fit" in error for error in errors)
