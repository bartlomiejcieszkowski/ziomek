"""Packaging tests: data files must be shipped in the wheel.

Root cause ([tool.hatch.build] only-packages = true): hatchling includes only Python
files within package directories, so `renderer.html`, `debug.html`,
the default skin (`src/ziomek/resources/single-frame/sheet.png` with its `morda.json`),
and `morda.schema.json` are missing from an installed
wheel and `GET /avatar` answers 404 when run through `uvx ziomek[mcp,stt]`, while the skin
reader cannot validate a definition without the schema.

The build config must therefore force-include the resource directories, and those
directories must be reachable as package data at runtime.
"""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _wheel_config() -> dict:
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["tool"]["hatch"]["build"]["targets"]["wheel"]


def test_force_include_covers_the_single_resources_folder():
    force_include = _wheel_config().get("force-include") or {}
    assert force_include.get("src/ziomek/resources") == "ziomek/resources"


def test_data_files_exist_where_the_build_config_maps_them():
    for path in (
        REPO_ROOT / "src/ziomek/resources/renderer.html",
        REPO_ROOT / "src/ziomek/resources/debug.html",
        REPO_ROOT / "src/ziomek/resources/single-frame/sheet.png",
        REPO_ROOT / "src/ziomek/resources/single-frame/morda.json",
        REPO_ROOT / "src/ziomek/resources/morda.schema.json",
        REPO_ROOT / "src/ziomek/resources/polish_male.names.json",
        REPO_ROOT / "src/ziomek/resources/polish_female.names.json",
    ):
        assert path.is_file(), f"missing data file: {path}"
    assert not (REPO_ROOT / "src/ziomek/client/resources").exists()


def _sdist_config() -> dict:
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["tool"]["hatch"]["build"]["targets"].get("sdist", {})


def test_sdist_force_include_ships_the_resource_directories():
    """CI builds the wheel from an sdist, so only-packages drops the data files.

    The sdist must carry the resource directories or the wheel build fails with
    'Forced include not found' (release-build exit code 1).
    """
    force_include = _sdist_config().get("force-include") or {}
    assert force_include.get("src/ziomek/resources") == "src/ziomek/resources"


def test_code_resolves_the_single_resources_folder():
    for path in (
        REPO_ROOT / "src/ziomek/api/avatar.py",
        REPO_ROOT / "src/ziomek/server.py",
    ):
        text = path.read_text(encoding="utf-8")
        assert '/ "resources" /' in text, f"{path} does not build the path from the resources folder"
        assert '"client" / "resources"' not in text, f"{path} still points at client/resources"
