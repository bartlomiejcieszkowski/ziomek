"""Tests for ziomek avatar skin registry."""

import os
import tempfile

import pytest

from ziomek.avatar.skins import SingleFrameSkin, SkinRegistry


def test_skin_registry_returns_default():
    """Verify SkinRegistry returns default single-frame skin."""
    registry = SkinRegistry.getInstance()
    skin = registry.get("single-frame")
    assert skin is not None
    assert skin.name == "single-frame"


def test_skin_getFrameRow():
    """Verify getFrameRow returns correct row for expressions."""
    skin = SingleFrameSkin(
        name="test",
        _sprite_path="/dev/null",
        _sprite_width=100,
        _sprite_height=400,
        _frame_width=100,
        _frame_height=100,
    )
    assert skin.getFrameRow("happy", 0) == 0
    assert skin.getFrameRow("surprised", 0) == 1
    assert skin.getFrameRow("unknown", 0) == 1  # default row


def test_skin_getExpressionNames():
    """Verify getExpressionNames returns full list."""
    skin = SingleFrameSkin(
        name="test",
        _sprite_path="/dev/null",
    )
    names = skin.getExpressionNames()
    assert "happy" in names
    assert "dying" in names
    assert len(names) == 10


def test_skin_getFrameCount():
    """Verify getFrameCount returns 1 for single-frame skin."""
    skin = SingleFrameSkin(
        name="test",
        _sprite_path="/dev/null",
        _sprite_width=100,
        _sprite_height=400,
        _frame_width=100,
        _frame_height=100,
    )
    assert skin.getFrameCount("happy") == 1


def test_skin_registry_list():
    """Verify SkinRegistry.list() returns registered skins."""
    registry = SkinRegistry.getInstance()
    skins = registry.list()
    assert "single-frame" in skins


def test_skin_load_sprite_from_file():
    """Verify skin loads sprite from file."""
    import struct

    def make_minimal_png(width: int, height: int) -> bytes:
        """Create a minimal valid PNG with IHDR and a single IDAT chunk."""

        def chunk(ct: bytes, data: bytes) -> bytes:
            c = ct + data
            crc = 0x811C9DC5
            for b in c:
                crc ^= b
                for _ in range(8):
                    crc = (crc << 1) ^ 0x82F63B78 if crc & 0x80000000 else crc << 1
            return struct.pack(">I", len(data)) + ct + data + struct.pack(">I", crc & 0xFFFFFFFF)

        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        return (
            b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", b"\x00\xff\x00\x00") + chunk(b"IEND", b"")
        )

    png_data = make_minimal_png(200, 400)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(png_data)
        f.flush()
        temp_path = f.name

    try:
        skin = SingleFrameSkin(
            name="test",
            _sprite_path=temp_path,
        )
        buffer = skin.getSpriteBuffer()
        assert len(buffer) == len(png_data)
        assert skin.spriteWidth == 200
        assert skin.spriteHeight == 400
        assert skin.frameHeight == 200  # 400 / 2 rows (ratio 1:2)
    finally:
        os.unlink(temp_path)


def test_skin_sprite_not_found():
    """Verify getSpriteBuffer raises when file doesn't exist."""
    skin = SingleFrameSkin(
        name="test",
        _sprite_path="/nonexistent.png",
        _sprite_width=100,
        _sprite_height=400,
        _frame_width=100,
        _frame_height=100,
    )
    with pytest.raises(FileNotFoundError):
        skin.getSpriteBuffer()
