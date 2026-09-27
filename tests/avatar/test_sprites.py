"""Tests for ziomek avatar sprite parser."""
import pytest

from ziomek.avatar.sprites import parse_png_sprite, SpriteMetadata


def test_parse_png_sprite():
    """Test basic PNG parsing."""
    # Create a minimal valid PNG (2x2 pixels)
    png_data = (
        b'\x89PNG\r\n\x1a\n'  # PNG magic
        + b'\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x02\x00\x00\x00\x90wS\xde'  # IHDR: 2x2
        + b'\x00\x00\x00\x0cIDAT\x08\x00\x00\x00\xff\xff\xff\x00\x00\x00\x00\x05\xfe\x10'
        + b'\x00\x00\x00\x00IEND'  # rest of data
    )

    meta = parse_png_sprite(png_data)
    assert meta.spriteWidth == 2
    assert meta.spriteHeight == 2
    assert meta.rows == 1  # 2/2 = 1 row per expression frame


def test_parse_png_sprite_2x4():
    """Test 2x4 sprite (2 wide, 4 high) → 2 rows."""
    png_data = (
        b'\x89PNG\r\n\x1a\n'
        + b'\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x04\x08\x06\x00\x00\x00\xd4\xd8\x07'
        + b'\x00\x00\x00\x0cIDAT\x08\x00\x00\x00\xff\xff\xff\x00\x00\x00\x00\x05\xfe\x10'
        + b'\x00\x00\x00\x00IEND'
    )
    meta = parse_png_sprite(png_data)
    assert meta.spriteWidth == 2
    assert meta.spriteHeight == 4
    assert meta.rows == 2  # 4/2 = 2 rows


def test_parse_invalid_png():
    """Test invalid PNG raises ValueError."""
    with pytest.raises(ValueError, match="Not a valid PNG file"):
        parse_png_sprite(b"not a valid png file at all")  # >24 bytes but invalid magic


def test_parse_too_small():
    """Test too-small PNG raises ValueError."""
    with pytest.raises(ValueError, match="too small"):
        parse_png_sprite(b"short")
