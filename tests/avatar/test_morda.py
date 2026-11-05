"""Tests for reading a skin definition from a folder or an archive."""

import io
import json
import tarfile

import pytest

from tests.avatar.morda_helpers import (
    first_answer,
    first_problem,
    make_archive,
    make_bundle,
    make_folder,
    png,
    sheet_definition,
)
from ziomek.avatar.morda import Definition, DefinitionError, fallback_target, read_definitions


def read_errors(root, definition, sizes=None):
    folder = make_folder(root, definition, sizes)
    answer = read_definitions(folder)[0]
    assert isinstance(answer, DefinitionError)
    return answer.errors


def test_a_source_with_one_definition_answers_that_definition(tmp_path):
    definition = first_answer(make_folder(tmp_path / "cosette", sheet_definition()))
    assert definition.name == "cosette"
    assert definition.type == "sheet"
    assert (definition.grid.rows, definition.grid.columns) == (6, 1)
    assert definition.sheet.file == "sheet.png"
    assert definition.targets["rest"].cell.row == 0
    assert definition.targets["cry"].file == "parts/cry.png"
    order = definition.expressions["sad"]
    assert [entry.name for entry in order.entries] == ["cry", "rest"]
    assert order.interval_ms == 400


def test_an_archive_with_one_definition_answers_that_definition(tmp_path):
    folder = make_folder(tmp_path / "cosette", sheet_definition())
    archive = tmp_path / "cosette.morda"
    with tarfile.open(archive, "w") as out:
        for name in sorted(["morda.json", "sheet.png", "parts/cry.png"]):
            data = (folder / name).read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            out.addfile(info, io.BytesIO(data))

    definition = first_answer(archive)
    assert definition.name == "cosette"
    assert definition.targets["cry"].file == "parts/cry.png"
    assert definition.expressions["happy"].entries[0].name == "rest"


def test_a_source_that_holds_no_definition_answers_that_error(tmp_path):
    folder = tmp_path / "cosette"
    folder.mkdir()
    (folder / "sheet.png").write_bytes(png(100, 600))

    answer = read_definitions(folder)[0]
    assert isinstance(answer, DefinitionError)
    assert any("no definition file in" in error for error in answer.errors)


def test_referenced_file_not_present(tmp_path):
    folder = make_folder(tmp_path / "cosette", sheet_definition())
    (folder / "parts/cry.png").unlink()

    answer = read_definitions(folder)[0]
    assert isinstance(answer, DefinitionError)
    assert any("parts/cry.png is referenced but not present" in error for error in answer.errors)


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

    answer = read_definitions(folder)[0]
    assert isinstance(answer, DefinitionError)
    assert any("is a symlink, which is not followed" in error for error in answer.errors)


def test_loop_defaults_to_true(tmp_path):
    definition = first_answer(make_folder(tmp_path / "cosette", sheet_definition()))
    assert definition.expressions["sad"].loop is True


def test_loop_can_be_read_as_false(tmp_path):
    expression = {"neutral": "rest", "sad": {"frame_order": ["cry", "rest"], "interval_ms": 400, "loop": False}}
    definition = first_answer(make_folder(tmp_path / "cosette", sheet_definition(expressions=expression)))
    assert definition.expressions["sad"].loop is False


def test_loop_on_a_single_frame_is_accepted_and_changes_nothing(tmp_path):
    expression = {"neutral": "rest", "happy": {"frame_order": ["rest"], "loop": True}}
    definition = first_answer(make_folder(tmp_path / "cosette", sheet_definition(expressions=expression)))
    order = definition.expressions["happy"]
    assert len(order.entries) == 1
    assert order.interval_ms is None
    assert order.loop is True


def test_undefined_expression_uses_the_declared_fallback(tmp_path):
    definition = first_answer(make_folder(tmp_path / "cosette", sheet_definition(fallback="rest")))
    assert fallback_target(definition).cell.row == 0


def test_a_name_that_is_not_covered_shows_the_expression_named_neutral(tmp_path):
    definition = first_answer(
        make_folder(
            tmp_path / "cosette",
            sheet_definition(
                frames={"rest": {"cell": {"row": 0, "column": 0}}, "blue": {"cell": {"row": 1, "column": 0}}},
                expressions={"neutral": "blue"},
            ),
            {"sheet.png": (100, 600)},
        )
    )
    assert fallback_target(definition).cell.row == 1


def test_the_expression_named_neutral_resolves_through_the_first_entry_it_states(tmp_path):
    definition = first_answer(
        make_folder(
            tmp_path / "cosette",
            sheet_definition(
                expressions={"neutral": {"frame_order": ["cry", "rest"], "interval_ms": 400}},
            ),
        )
    )
    assert fallback_target(definition).file == "parts/cry.png"


def test_a_definition_with_neither_is_reported_as_an_error(tmp_path):
    errors = read_errors(
        tmp_path / "cosette",
        sheet_definition(
            frames={"cry": {"file": "parts/cry.png"}, "rest": {"cell": {"row": 0, "column": 0}}},
            expressions={"sad": "cry"},
        ),
    )
    assert any("expressions" in error and "neutral" in error for error in errors)


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
    definition = first_answer(make_folder(tmp_path / "cosette", definition))
    assert definition.fit == "cover"


def test_nothing_stated_keeps_the_default_that_the_reader_applies(tmp_path):
    # A default written in the schema is an annotation, so the reader is what applies it.
    definition = first_answer(make_folder(tmp_path / "cosette", sheet_definition()))
    assert definition.fit == "contain"
    assert definition.targets["rest"].fit is None


def test_a_target_can_state_the_setting_for_itself(tmp_path):
    definition = dict(sheet_definition())
    definition["frames"] = {
        "rest": {"cell": {"row": 0, "column": 0}, "object-fit": "fill"},
        "cry": {"file": "parts/cry.png"},
        "neutral": {"cell": {"row": 1, "column": 0}},
    }
    definition = first_answer(make_folder(tmp_path / "cosette", definition))
    assert definition.targets["rest"].fit == "fill"
    assert definition.targets["cry"].fit is None  # nothing stated for itself, so the definition answers


def test_a_setting_that_is_not_one_of_the_values_is_reported(tmp_path):
    definition = dict(sheet_definition())
    definition["object-fit"] = "stretch"
    errors = read_errors(tmp_path / "cosette", definition)
    assert any("object-fit" in error for error in errors)


def test_a_bundle_answers_each_definition_it_holds(tmp_path):
    bundle = make_bundle(
        tmp_path / "single-frame",
        {
            "morda.json": sheet_definition(name="single-frame"),
            "blue.morda.json": sheet_definition(
                name="single-frame-blue", expressions={"neutral": "rest", "happy": "cry"}
            ),
            "green.morda.json": sheet_definition(
                name="single-frame-green", expressions={"neutral": "rest", "happy": "rest"}
            ),
        },
    )

    answers = read_definitions(bundle)
    assert [answer.name for answer in answers] == ["single-frame", "single-frame-blue", "single-frame-green"]


def test_an_archive_answers_each_definition_it_holds(tmp_path):
    bundle = make_bundle(
        tmp_path / "single-frame",
        {
            "morda.json": sheet_definition(name="single-frame"),
            "blue.morda.json": sheet_definition(
                name="single-frame-blue", expressions={"neutral": "rest", "happy": "cry"}
            ),
        },
    )
    archive = make_archive(bundle, tmp_path / "single-frame.morda")

    answers = read_definitions(archive)
    assert [answer.name for answer in answers] == ["single-frame", "single-frame-blue"]


def test_the_definition_at_the_top_of_a_bundle_is_answered_before_the_names_for_avatars(tmp_path):
    bundle = make_bundle(
        tmp_path / "single-frame",
        {
            "blue.morda.json": sheet_definition(name="single-frame-blue"),
            "morda.json": sheet_definition(name="single-frame"),
        },
    )

    answers = read_definitions(bundle)
    assert [answer.name for answer in answers] == ["single-frame", "single-frame-blue"]


def test_a_bundle_that_holds_only_names_for_avatars_answers_that_definition(tmp_path):
    bundle = make_bundle(tmp_path / "single-frame", {"blue.morda.json": sheet_definition(name="single-frame-blue")})

    answers = read_definitions(bundle)
    assert [answer.name for answer in answers] == ["single-frame-blue"]


def test_a_name_inside_a_bundle_is_not_read_as_a_definition(tmp_path):
    bundle = make_bundle(tmp_path / "single-frame", {"morda.json": sheet_definition(name="single-frame")})
    (bundle / "frames").mkdir()
    (bundle / "frames" / "blue.morda.json").write_text(
        json.dumps(sheet_definition(name="single-frame-blue")), encoding="utf-8"
    )

    answers = read_definitions(bundle)
    assert [answer.name for answer in answers] == ["single-frame"]


def test_a_definition_that_does_not_read_does_not_stop_the_other_definitions_in_the_bundle(tmp_path):
    broken = {"name": "single-frame", "type": "image", "expressions": {}}
    bundle = make_bundle(
        tmp_path / "single-frame",
        {
            "morda.json": broken,
            "blue.morda.json": sheet_definition(
                name="single-frame-blue", expressions={"neutral": "rest", "happy": "cry"}
            ),
        },
    )

    answers = read_definitions(bundle)
    assert isinstance(answers[0], DefinitionError)
    assert isinstance(answers[1], Definition)
    assert answers[1].name == "single-frame-blue"


def test_a_problem_in_one_definition_names_the_definition_it_came_from(tmp_path):
    bundle = make_bundle(
        tmp_path / "single-frame",
        {
            "morda.json": sheet_definition(name="single-frame", expressions={"happy": "smile"}),
            "blue.morda.json": sheet_definition(name="single-frame-blue", expressions={"happy": "smile"}),
        },
    )

    errors = [answer.errors for answer in read_definitions(bundle) if isinstance(answer, DefinitionError)]
    assert any(error.startswith("morda.json") for problem in errors for error in problem)
    assert any(error.startswith("blue.morda.json") for problem in errors for error in problem)
