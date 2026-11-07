"""Tests for the names `scripts/morda.py` writes into an archive."""

import sys
from pathlib import Path
from tarfile import TarFile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import morda

ROOT = Path(__file__).resolve().parent.parent


def test_files_in_the_folder_are_written_under_their_own_names(tmp_path: Path):
    source = tmp_path / "cosette"
    source.mkdir()
    (source / "morda.json").write_text("{}", encoding="utf-8")
    (source / "happy.png").write_bytes(b"png")

    target = tmp_path / "cosette.morda"
    morda.package(source, target)

    with TarFile.open(target) as archive:
        names = {member.name for member in archive}
    assert names == {"morda.json", "happy.png"}


def test_files_in_a_subfolder_are_written_as_entries_with_the_path(tmp_path: Path):
    source = tmp_path / "cosette"
    (source / "frames").mkdir(parents=True)
    (source / "morda.json").write_text("{}", encoding="utf-8")
    (source / "frames" / "happy.png").write_bytes(b"png")

    target = tmp_path / "cosette.morda"
    morda.package(source, target)

    with TarFile.open(target) as archive:
        entries = {member.name: member.size for member in archive}
    assert entries == {"morda.json": 2, "frames/happy.png": 3}


def test_a_subfolder_with_no_files_writes_no_entry(tmp_path: Path):
    source = tmp_path / "cosette"
    (source / "frames").mkdir(parents=True)
    (source / "morda.json").write_text("{}", encoding="utf-8")

    target = tmp_path / "cosette.morda"
    morda.package(source, target)

    with TarFile.open(target) as archive:
        names = {member.name for member in archive}
    assert names == {"morda.json"}


def test_the_script_reads_a_root_file_when_names_carry_paths(tmp_path: Path):
    """A definition that names a path inside the skin is read through the reader, not through a folder listing."""
    source = tmp_path / "cosette"
    (source / "frames").mkdir(parents=True)
    (source / "morda.json").write_text("{}", encoding="utf-8")
    (source / "frames" / "happy.png").write_bytes(b"png")

    target = tmp_path / "cosette.morda"
    morda.package(source, target)

    with TarFile.open(target) as archive:
        definition = archive.extractfile("morda.json").read()
    assert definition == b"{}"


def test_the_script_warns_when_a_folder_holds_no_definition(tmp_path, capsys):
    """A folder with only pictures is not a skin, so the script says what it could not find."""
    source = tmp_path / "cosette"
    source.mkdir()
    (source / "happy.png").write_bytes(b"png")

    sys.argv = ["morda.py", str(source), str(tmp_path / "cosette.morda")]
    morda.main()

    assert "no definition in the folder" in capsys.readouterr().err


def test_the_script_does_not_warn_when_a_definition_is_named_for_an_avatar(tmp_path, capsys):
    """A folder that holds definitions for avatars is a skin, so the script does not say a definition is missing."""
    source = tmp_path / "cosette"
    source.mkdir()
    (source / "blue.morda.json").write_text("{}", encoding="utf-8")

    sys.argv = ["morda.py", str(source), str(tmp_path / "cosette.morda")]
    morda.main()

    assert "warning" not in capsys.readouterr().err


def test_the_script_stays_within_repo_rules():
    """No abbreviations, no short names, no single-letter names, no underscore word separators."""
    source = (ROOT / "scripts" / "morda.py").read_text(encoding="utf-8")
    assert "_morda" not in source
    assert "$X" not in source
