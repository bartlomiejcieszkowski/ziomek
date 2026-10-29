"""Packaging tests: data files must be shipped in the wheel.

Root cause ([tool.hatch.build] only-packages = true): hatchling includes only Python
files within package directories, so `renderer.html`, `debug.html`, and
`single_frame_sprite_sheet.png` are missing from an installed wheel and
`GET /api/avatar/view` answers 404 when run through `uvx ziomek[mcp,stt]`.

The build config must therefore force-include the resource directories, and those
directories must be reachable as package data at runtime.
"""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _wheel_config() -> dict:
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["tool"]["hatch"]["build"]["targets"]["wheel"]


def test_force_include_covers_the_resource_directories():
    force_include = _wheel_config().get("force-include") or {}
    assert force_include.get("src/ziomek/client/resources") == "ziomek/client/resources"
    assert force_include.get("src/ziomek/resources") == "ziomek/resources"


def test_data_files_exist_where_the_build_config_maps_them():
    for path in (
        REPO_ROOT / "src/ziomek/client/resources/renderer.html",
        REPO_ROOT / "src/ziomek/client/resources/debug.html",
        REPO_ROOT / "src/ziomek/resources/single_frame_sprite_sheet.png",
    ):
        assert path.is_file(), f"missing data file: {path}"
