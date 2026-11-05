"""Shared builders for tests that read a skin definition."""

import io
import json
import struct
import tarfile

from ziomek.avatar.morda import DEFINITION_FILE, Definition, DefinitionError, read_definitions


def png(width: int, height: int) -> bytes:
    """A PNG that only reports its size, which is all the reader reads."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        crc = 0x811C9DC5
        for byte in body:
            crc ^= byte
            for _ in range(8):
                crc = (crc << 1) ^ 0x82F63B78 if crc & 0x80000000 else crc << 1
        return struct.pack(">I", len(data)) + body + struct.pack(">I", crc & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", b"\x00\xff\x00\x00") + chunk(b"IEND", b"")


def sheet_definition(**changes):
    base = {
        "name": "cosette",
        "type": "sheet",
        "sheet": {"file": "sheet.png"},
        "frame": {"width": 100, "height": 100},
        "grid": {"rows": 6, "columns": 1},
        "frames": {
            "rest": {"cell": {"row": 0, "column": 0}},
            "cry": {"file": "parts/cry.png"},
            "neutral": {"cell": {"row": 1, "column": 0}},
        },
        "expressions": {
            "neutral": "rest",
            "sad": {"frame_order": ["cry", "rest"], "interval_ms": 400},
            "happy": "rest",
        },
    }
    base.update(changes)
    return base


def make_folder(root, definition, sizes=None):
    root.mkdir(parents=True, exist_ok=True)
    (root / DEFINITION_FILE).write_text(json.dumps(definition), encoding="utf-8")
    for name, size in (sizes or {"sheet.png": (100, 600), "parts/cry.png": (100, 100)}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png(*size))
    return root


def make_bundle(root, definitions, sizes=None):
    """Several definitions over the files they share.

    Names are given as they are written in the bundle, so a test can say what a bundle holds
    without a test relying on the reader finding one name instead of another.
    """
    root.mkdir(parents=True, exist_ok=True)
    for name, definition in definitions.items():
        (root / name).write_text(json.dumps(definition), encoding="utf-8")
    for name, size in (sizes or {"sheet.png": (100, 600), "parts/cry.png": (100, 100)}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png(*size))
    return root


def make_archive(bundle, target):
    """The contents of a bundle written as entries in an archive."""
    with tarfile.open(target, "w") as out:
        for path in sorted(p for p in bundle.rglob("*") if p.is_file()):
            data = path.read_bytes()
            info = tarfile.TarInfo(path.relative_to(bundle).as_posix())
            info.size = len(data)
            out.addfile(info, io.BytesIO(data))
    return target


def first_answer(source):
    """The first thing a source answers.

    A source with one definition answers that definition, so a test that is about what a
    definition carries can take it as the first answer.
    """
    answer = read_definitions(source)[0]
    assert isinstance(answer, Definition)
    return answer


def first_problem(source):
    """The first thing a source answers when nothing in it reads."""
    answer = read_definitions(source)[0]
    assert isinstance(answer, DefinitionError)
    return answer
