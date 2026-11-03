"""Shared builders for tests that read a skin definition."""

import json
import struct

from ziomek.avatar.morda import DEFINITION_FILE


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
        "expressions": {"sad": {"frame_order": ["cry", "rest"], "interval_ms": 400}, "happy": "rest"},
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
