"""ziomek avatar skin registry — ported from TypeScript."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SingleFrameSkin:
    """A skin that uses a single frame per expression."""

    name: str
    sprite_width: int
    sprite_height: int
    frame_width: int
    frame_height: int
    sprite_path: str  # path to PNG file

    _sprite_buffer: Optional[bytes] = field(default=None, repr=False)
    _row_map: dict[str, int] = field(default_factory=dict, repr=False)

    def _load_sprite(self) -> None:
        """Load sprite sheet from disk."""
        if self._sprite_buffer is not None:
            return
        if os.path.isfile(self.sprite_path):
            with open(self.sprite_path, "rb") as f:
                self._sprite_buffer = f.read()

    def getFrameRow(self, expression_name: str, cycle_index: int) -> int:
        """Get the sprite sheet row index for an expression."""
        row_map = {
            "happy": 0, "surprised": 1, "curious": 2, "looking": 2, "thinking": 2,
            "focused": 3, "bored": 3, "dying": 4, "neutral": 1,
        }
        return row_map.get(expression_name, 1)

    def getFrameCount(self, expression_name: str) -> int:
        """Get number of frames for an expression."""
        return 1  # single frame per expression

    def getExpressionNames(self) -> list[str]:
        return ["idle", "bored", "happy", "surprised", "curious", "looking", "focused", "thinking", "dying", "neutral"]

    def getSpriteBuffer(self) -> bytes:
        self._load_sprite()
        if self._sprite_buffer is None:
            raise FileNotFoundError(f"Sprite sheet not found: {self.sprite_path}")
        return self._sprite_buffer

    @property
    def spriteWidth(self) -> int:
        return self.sprite_width

    @property
    def spriteHeight(self) -> int:
        return self.sprite_height

    @property
    def frameWidth(self) -> int:
        return self.frame_width

    @property
    def frameHeight(self) -> int:
        return self.frame_height


class SkinRegistry:
    """Registry of avatar skins."""

    _instance: Optional["SkinRegistry"] = None

    def __init__(self) -> None:
        self._skins: dict[str, SingleFrameSkin] = {}
        self._register_default()

    @classmethod
    def getInstance(cls) -> SkinRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _register_default(self) -> None:
        self._skins["single-frame"] = SingleFrameSkin(
            name="single-frame",
            sprite_width=0,  # set at runtime from PNG
            sprite_height=0,
            frame_width=0,
            frame_height=0,
            sprite_path="",  # set at runtime
        )

    def get(self, name: str) -> Optional[SingleFrameSkin]:
        return self._skins.get(name)

    def list(self) -> list[str]:
        return list(self._skins.keys())
