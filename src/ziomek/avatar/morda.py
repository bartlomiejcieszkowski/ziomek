"""Read the skin definitions a skin folder or a .morda archive holds."""

from __future__ import annotations

import json
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import jsonschema

from ziomek.avatar.png import read_png_dimensions

SCHEMA_PATH = Path(__file__).parent.parent / "resources" / "morda.schema.json"
DEFINITION_FILE = "morda.json"
DEFINITION_SUFFIX = ".morda.json"
FILE_MARKER = "file:"

FIT_FIELD = "object-fit"
FIT_VALUES = ("fill", "contain", "cover", "none", "scale-down")
DEFAULT_FIT = "contain"


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
    fit: str | None = None


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
    fit: str = DEFAULT_FIT
    source: Path | None = None


def definition_names(names: object) -> list[str]:
    """The names inside a source that are definitions, in the order a source answers them.

    The definition at the top is answered first, then the names given for an avatar. A name
    that reaches outside the top of the source is not a definition, since what sits inside is
    a name and not a directory.
    """
    listed = [str(name) for name in names]
    top = [name for name in listed if name == DEFINITION_FILE]
    avatars = sorted(name for name in listed if name.endswith(DEFINITION_SUFFIX) and "/" not in name)
    return top + avatars


def read_definitions(source: Path) -> list[Definition | DefinitionError]:
    """Read every definition a source holds, one answer for each.

    Both forms are read as the same thing: names to files. Nothing is extracted, since a
    reference is read by name. Symlinks are not followed, and an entry name must stay
    inside the folder or the archive. A definition that does not read is answered as its own
    problem, since one unreadable definition does not stop the others in the same source. An
    answer names the definition it came from, so definitions in one bundle can be told apart.
    """
    problems: list[str] = []
    entries = read_entries(source, problems)
    if problems:
        return [DefinitionError(problems)]

    names = definition_names(entries)
    if not names:
        return [DefinitionError([f"no definition file in {source}"])]

    return [_read(source, name, entries) for name in names]


def _read(source: Path, definition_name: str, entries: dict[str, bytes]) -> Definition | DefinitionError:
    errors: list[str] = []

    try:
        raw = json.loads(entries[definition_name].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return DefinitionError([f"{definition_name} is not readable: {exc}"])

    errors.extend(_schema_errors(raw, definition_name))

    files = sorted(_file_names(raw))
    for file_name in files:
        if not _entry_name_is_allowed(file_name):
            errors.append(f"{definition_name}: {file_name} is not an entry name, it is a path that reaches outside")

    for file_name in files:
        if file_name not in entries:
            errors.append(f"{definition_name}: {file_name} is referenced but not present")

    frame = raw.get("frame")
    grid = raw.get("grid")
    sheet = raw.get("sheet")
    if raw.get("type") == "sheet" and frame and grid and sheet:
        sheet_name = sheet["file"] if isinstance(sheet, dict) else _strip_marker(str(sheet))
        buffer = entries.get(sheet_name)
        if buffer is not None:
            dimensions = read_png_dimensions(buffer)
            if dimensions is None:
                errors.append(f"{definition_name}: {sheet_name} does not report its size")
            elif dimensions != (frame["width"] * grid["columns"], frame["height"] * grid["rows"]):
                errors.append(
                    f"{definition_name}: {sheet_name} reports {dimensions[0]}x{dimensions[1]}, which is not "
                    f"{frame['width']}x{frame['height']} for {grid['rows']} rows and {grid['columns']} columns"
                )

    for value in raw.get("expressions", {}).values():
        items = [value] if isinstance(value, str) else value.get("frame_order", [])
        for item in items:
            if isinstance(item, str) and not item.startswith(FILE_MARKER) and item not in raw.get("frames", {}):
                errors.append(f"{definition_name}: {item} is referenced but not declared")

    fallback = raw.get("fallback")
    if isinstance(fallback, str) and not fallback.startswith(FILE_MARKER) and fallback not in raw.get("frames", {}):
        errors.append(f"{definition_name}: {fallback} is referenced but not declared")

    if errors:
        return DefinitionError(errors)

    return Definition(
        name=raw["name"],
        type=raw["type"],
        sheet=_reference(sheet) if sheet else None,
        frame=FrameSize(frame["width"], frame["height"]) if frame else None,
        grid=GridSize(grid["rows"], grid["columns"]) if grid else None,
        targets={
            key: Target(key, _cell(value), _file(value), _fit(value)) for key, value in raw.get("frames", {}).items()
        },
        expressions={key: _order(value) for key, value in raw.get("expressions", {}).items()},
        fallback=_reference(raw.get("fallback")) if raw.get("fallback") else None,
        fit=_fit(raw) or DEFAULT_FIT,
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


def _schema_errors(raw: object, definition_name: str) -> list[str]:
    schema = _load_schema()
    if schema is None:
        return [f"{definition_name}: the rules for the format cannot be read"]

    validator = jsonschema.Draft202012Validator(schema)
    found = []
    for error in sorted(validator.iter_errors(raw), key=lambda e: list(e.path)):
        path = _json_path(error.path)
        if path:
            found.append(f"{definition_name}: {path}: {error.message}")
        else:
            found.append(f"{definition_name}: {error.message}")
    return found


def _load_schema() -> dict | None:
    """The rules for the format, or nothing when they cannot be read.

    Rules that are not there, or that do not read as JSON, are a problem for the definition that
    needed them rather than for the whole source, so one definition does not stop the others.
    """
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


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


def _fit(value: object) -> str | None:
    """The stated way a frame is placed, which a target can give for itself."""
    if isinstance(value, dict) and FIT_FIELD in value:
        return value[FIT_FIELD]
    return None


def _order(value: object) -> FrameOrder:
    if isinstance(value, str):
        return FrameOrder(entries=(_reference(value),))
    entries = tuple(_reference(entry) for entry in value.get("frame_order", []))
    return FrameOrder(entries=entries, interval_ms=value.get("interval_ms"), loop=value.get("loop", True))


def fallback_target(definition: Definition) -> Target | None:
    """What a definition shows for a name it does not cover.

    The declared fallback first, then the first entry of the expression named neutral. A
    definition with neither is reported as an error, so there is no other name to reach.
    """
    if definition.fallback is not None:
        return definition.targets.get(definition.fallback.name)

    order = definition.expressions.get("neutral")
    if order is None or not order.entries:
        return None
    return resolve_reference(definition, order.entries[0])


def resolve_reference(definition: Definition, reference: Reference) -> Target | None:
    """The frame a reference points at, whether it names one or names a file directly."""
    if reference.name is not None:
        return definition.targets.get(reference.name)
    return Target(name=reference.file or "", file=reference.file)
