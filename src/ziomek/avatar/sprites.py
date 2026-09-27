"""ziomek avatar sprite sheet parser."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SpriteMetadata:
    spriteWidth: int
    spriteHeight: int
    frameWidth: int
    frameHeight: int
    rows: int


def parse_png_sprite(data: bytes) -> SpriteMetadata:
    """Parse a PNG sprite sheet.

    Extracts dimensions from the PNG header (bytes 16-23 for width/height),
    then calculates frame count from the height/width ratio.

    Same logic as avatar-panel.ts `_loadSprite()`.
    """
    if len(data) < 24:
        raise ValueError("PNG file too small")
    if data[0] != 0x89 or data[1] != 0x50:  # 'P' in PNG magic
        raise ValueError("Not a valid PNG file")

    sprite_width = (data[16] << 24) | (data[17] << 16) | (data[18] << 8) | data[19]
    sprite_height = (data[20] << 24) | (data[21] << 16) | (data[22] << 8) | data[23]

    rows = max(1, round(sprite_height / sprite_width))
    frame_width = sprite_width // 1  # single column
    frame_height = sprite_height // rows

    return SpriteMetadata(
        spriteWidth=sprite_width,
        spriteHeight=sprite_height,
        frameWidth=frame_width,
        frameHeight=frame_height,
        rows=rows,
    )


def sprite_to_base64(data: bytes) -> str:
    import base64
    return f"data:image/png;base64,{base64.b64encode(data).decode('utf-8')}"
