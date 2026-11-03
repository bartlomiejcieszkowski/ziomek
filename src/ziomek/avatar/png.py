"""Read the size a PNG reports in its header."""

from __future__ import annotations

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_png_dimensions(buffer: bytes) -> tuple[int, int] | None:
    """Return the width and height an image reports, or None when it does not.

    Only the header is read. The PNG signature is eight bytes and the IHDR chunk
    carries width and height as big-endian numbers, so the pair starts at byte 16.
    """
    if not buffer or not buffer.startswith(SIGNATURE):
        return None
    if len(buffer) < 24 or buffer[12:16] != b"IHDR":
        return None
    width = int.from_bytes(buffer[16:20], "big")
    height = int.from_bytes(buffer[20:24], "big")
    return width, height
