"""Read a skin definition from a skin folder or a .morda archive."""

from __future__ import annotations

import json
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import jsonschema

from ziomek.avatar.png import read_png_dimensions

SCHEMA_PATH = Path(__file__).parent.parent / "resources" / "morda.schema.json"
DEFINITION_FILE = "morda.json"
FILE_MARKER = "file:"


class DefinitionError(Exception):
    """Every problem found in one definition, reported together."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class Cell:
    row: int
    column: int


@dataclass(frozen=True)
class FrameSize:
    width: int
    height: int


@dataclass(frozen=True)
class GridSize:
    rows: int
    columns: int


@dataclass(frozen=True)
class Reference:
    """What something points at: a declared name, or a file named directly."""

    name: str | None = None
    file: str | None = None


@dataclass(frozen=True)
class Target:
    name: str
    cell: Cell | None = None
    file: str | None = None


@dataclass(frozen=True)
class FrameOrder:
    """The names an expression shows, in order, the time between them, and what happens after the last one."""

    entries: tuple[Reference, ...]
    interval_ms: int | None = None
    loop: bool = True


@dataclass(frozen=True)
class Definition:
    name: str
    type: str
    sheet: Reference | None
    frame: FrameSize | None
    grid: GridSize | None
    targets: dict[str, Target]
    expressions: dict[str, FrameOrder]
    fallback: Reference | None
    source: Path | None = None


def read_definition(source: Path) -> Definition:
    """Read a definition from a skin folder or an archive, then report what is wrong.

    Both forms are read as the same thing: names to files. Nothing is extracted, since a
    reference is read by name. Symlinks are not followed, and an entry name must stay
    inside the folder or the archive.
    """
    errors: list[str] = []
    entries = read_entries(source, errors)
    if errors:
        raise DefinitionError(errors)

    text = entries.get(DEFINITION_FILE)
    if text is None:
        raise DefinitionError([f"no {DEFINITION_FILE} in {source}"])

    try:
        raw = json.loads(text.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DefinitionError([f"{DEFINITION_FILE} is not readable: {exc}"]) from exc

    for error in _schema_errors(raw):
        errors.append(error)

    names = sorted(_file_names(raw))
    for name in names:
        if not _entry_name_is_allowed(name):
            errors.append(f"{name} is not an entry name, it is a path that reaches outside")

    for name in names:
        if name not in entries:
            errors.append(f"{name} is referenced but not present")

    frame = raw.get("frame")
    grid = raw.get("grid")
    sheet = raw.get("sheet")
    if raw.get("type") == "sheet" and frame and grid and sheet:
        sheet_name = sheet["file"] if isinstance(sheet, dict) else _strip_marker(str(sheet))
        buffer = entries.get(sheet_name)
        if buffer is not None:
            dimensions = read_png_dimensions(buffer)
            if dimensions is None:
                errors.append(f"{sheet_name} does not report its size")
            elif dimensions != (frame["width"] * grid["columns"], frame["height"] * grid["rows"]):
                errors.append(
                    f"{sheet_name} reports {dimensions[0]}x{dimensions[1]}, which is not "
                    f"{frame['width']}x{frame['height']} for {grid['rows']} rows and {grid['columns']} columns"
                )

    for value in raw.get("expressions", {}).values():
        items = [value] if isinstance(value, str) else value.get("frame_order", [])
        for item in items:
            if isinstance(item, str) and not item.startswith(FILE_MARKER) and item not in raw.get("frames", {}):
                errors.append(f"{item} is referenced but not declared")

    fallback = raw.get("fallback")
    if isinstance(fallback, str) and not fallback.startswith(FILE_MARKER) and fallback not in raw.get("frames", {}):
        errors.append(f"{fallback} is referenced but not declared")

    if errors:
        raise DefinitionError(errors)

    return Definition(
        name=raw["name"],
        type=raw["type"],
        sheet=_reference(sheet) if sheet else None,
        frame=FrameSize(frame["width"], frame["height"]) if frame else None,
        grid=GridSize(grid["rows"], grid["columns"]) if grid else None,
        targets={key: Target(key, _cell(value), _file(value)) for key, value in raw.get("frames", {}).items()},
        expressions={key: _order(value) for key, value in raw.get("expressions", {}).items()},
        fallback=_reference(raw.get("fallback")) if raw.get("fallback") else None,
        source=source,
    )


def read_entries(source: Path, errors: list[str] | None = None) -> dict[str, bytes]:
    """Names to contents, from a folder or an archive.

    A drawing path needs the bytes a name points at, so this is open to it as well; it is the
    same read the reader uses to check that a referenced file is present.
    """
    problems = errors if errors is not None else []
    if source.is_dir():
        entries: dict[str, bytes] = {}
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            if path.is_symlink():
                problems.append(f"{path.relative_to(source).as_posix()} is a symlink, which is not followed")
                continue
            entries[path.relative_to(source).as_posix()] = path.read_bytes()
        return entries

    if source.suffix == ".morda":
        with tarfile.open(source) as archive:
            members = [member for member in archive.getmembers() if member.isfile()]
            return {member.name: archive.extractfile(member).read() for member in members}

    problems.append(f"{source} is neither a skin folder nor an archive")
    return {}


def _schema_errors(raw: object) -> list[str]:
    validator = jsonschema.Draft202012Validator(_load_schema())
    return [
        f"{_json_path(error.path) or DEFINITION_FILE}: {error.message}"
        for error in sorted(validator.iter_errors(raw), key=lambda e: list(e.path))
    ]


def _load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def _json_path(path: object) -> str:
    return ".".join(str(part) for part in path)


def _entry_name_is_allowed(name: str) -> bool:
    pure = PurePosixPath(name)
    return not name.startswith("/") and ".." not in pure.parts and not pure.is_absolute()


def _file_names(raw: dict) -> list[str]:
    """Every file a definition refers to, whether it names one directly or through a target."""
    found: list[str] = []
    sheet = raw.get("sheet")
    if sheet:
        found.append(sheet["file"] if isinstance(sheet, dict) else _strip_marker(str(sheet)))

    for value in raw.get("frames", {}).values():
        file = value.get("file") if isinstance(value, dict) else None
        if file:
            found.append(file)

    for value in raw.get("expressions", {}).values():
        items = [value] if isinstance(value, str) else value.get("frame_order", [])
        for item in items:
            if isinstance(item, str) and item.startswith(FILE_MARKER):
                found.append(_strip_marker(item))

    fallback = raw.get("fallback")
    if isinstance(fallback, str) and fallback.startswith(FILE_MARKER):
        found.append(_strip_marker(fallback))

    return sorted(set(found))


def _strip_marker(value: str) -> str:
    return value[len(FILE_MARKER) :] if value.startswith(FILE_MARKER) else value


def _reference(value: object) -> Reference:
    if isinstance(value, str):
        return Reference(file=_strip_marker(value)) if value.startswith(FILE_MARKER) else Reference(name=value)
    if isinstance(value, dict) and "file" in value:
        return Reference(file=value["file"])
    raise DefinitionError([f"{value} is not a name or a file"])


def _cell(value: object) -> Cell | None:
    if isinstance(value, dict) and "cell" in value:
        return Cell(value["cell"]["row"], value["cell"]["column"])
    return None


def _file(value: object) -> str | None:
    if isinstance(value, dict) and "file" in value:
        return value["file"]
    return None


def _order(value: object) -> FrameOrder:
    if isinstance(value, str):
        return FrameOrder(entries=(_reference(value),))
    entries = tuple(_reference(entry) for entry in value.get("frame_order", []))
    return FrameOrder(entries=entries, interval_ms=value.get("interval_ms"), loop=value.get("loop", True))


def fallback_target(definition: Definition) -> Target | None:
    """What a definition shows for a name it does not cover.

    The declared fallback first, then the entry for neutral. A definition with neither is
    reported as an error, so there is no other name to reach.
    """
    if definition.fallback is not None:
        return definition.targets.get(definition.fallback.name)
    return definition.targets.get("neutral")


def resolve_reference(definition: Definition, reference: Reference) -> Target | None:
    """The frame a reference points at, whether it names one or names a file directly."""
    if reference.name is not None:
        return definition.targets.get(reference.name)
    return Target(name=reference.file or "", file=reference.file)
