"""Tests for ziomek avatar skin registry."""
import pytest
import os
import tempfile

from ziomek.avatar.skins import SkinRegistry, SingleFrameSkin


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
        sprite_width=100,
        sprite_height=400,
        frame_width=100,
        frame_height=100,
        sprite_path="/dev/null",  # won't be loaded in test
    )
    assert skin.getFrameRow("happy", 0) == 0
    assert skin.getFrameRow("surprised", 0) == 1
    assert skin.getFrameRow("unknown", 0) == 1  # default row


def test_skin_getExpressionNames():
    """Verify getExpressionNames returns full list."""
    skin = SingleFrameSkin(
        name="test", sprite_width=100, sprite_height=400,
        frame_width=100, frame_height=100, sprite_path="/dev/null",
    )
    names = skin.getExpressionNames()
    assert "happy" in names
    assert "dying" in names
    assert len(names) == 10


def test_skin_getFrameCount():
    """Verify getFrameCount returns 1 for single-frame skin."""
    skin = SingleFrameSkin(
        name="test", sprite_width=100, sprite_height=400,
        frame_width=100, frame_height=100, sprite_path="/dev/null",
    )
    assert skin.getFrameCount("happy") == 1


def test_skin_registry_list():
    """Verify SkinRegistry.list() returns registered skins."""
    registry = SkinRegistry.getInstance()
    skins = registry.list()
    assert "single-frame" in skins


def test_skin_load_sprite_from_file():
    """Verify skin loads sprite from file."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"fake png data")
        f.flush()
        temp_path = f.name

    try:
        skin = SingleFrameSkin(
            name="test", sprite_width=100, sprite_height=400,
            frame_width=100, frame_height=100, sprite_path=temp_path,
        )
        buffer = skin.getSpriteBuffer()
        assert buffer == b"fake png data"
    finally:
        os.unlink(temp_path)


def test_skin_sprite_not_found():
    """Verify getSpriteBuffer raises when file doesn't exist."""
    skin = SingleFrameSkin(
        name="test", sprite_width=100, sprite_height=400,
        frame_width=100, frame_height=100, sprite_path="/nonexistent.png",
    )
    with pytest.raises(FileNotFoundError):
        skin.getSpriteBuffer()
