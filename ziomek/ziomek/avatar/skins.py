"""ziomek avatar skin registry — ported from TypeScript."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Row index map: expression name → sprite sheet row
_ROW_MAP: dict[str, int] = {
    "happy": 0,
    "surprised": 1,
    "curious": 2,
    "looking": 2,
    "thinking": 2,
    "focused": 3,
    "bored": 3,
    "dying": 4,
    "neutral": 1,
}


@dataclass
class SingleFrameSkin:
    """A skin that uses a single frame per expression."""

    name: str
    _sprite_path: str  # path to PNG file
    _sprite_buffer: bytes | None = field(default=None, repr=False)

    _sprite_width: int = 0
    _sprite_height: int = 0
    _frame_width: int = 0
    _frame_height: int = 0

    @property
    def sprite_path(self) -> str:
        return self._sprite_path

    def _parse_png(self) -> None:
        """Parse PNG header to extract dimensions and compute frame size."""
        if not self._sprite_buffer:
            return
        # Width: bytes 16-19 (big-endian)
        self._sprite_width = int.from_bytes(self._sprite_buffer[16:20], "big")
        # Height: bytes 20-23 (big-endian)
        self._sprite_height = int.from_bytes(self._sprite_buffer[20:24], "big")
        # Auto-calculate rows from sprite ratio (single column)
        rows = max(1, round(self._sprite_height / self._sprite_width))
        self._frame_width = self._sprite_width
        self._frame_height = self._sprite_height // rows

    def _load_sprite(self) -> None:
        """Load sprite sheet from disk."""
        if self._sprite_buffer is not None:
            return
        path = Path(self._sprite_path)
        if path.is_file():
            try:
                with open(path, "rb") as f:
                    self._sprite_buffer = f.read()
                self._parse_png()
            except OSError as exc:
                logger.warning("Failed to load sprite %s: %s", self._sprite_path, exc)

    def getFrameRow(self, expression_name: str, cycle_index: int) -> int:
        """Get the sprite sheet row index for an expression."""
        return _ROW_MAP.get(expression_name, _ROW_MAP.get("neutral", 1))

    def getFrameCount(self, expression_name: str) -> int:
        """Get number of frames for an expression."""
        return 1  # single frame per expression

    def getExpressionNames(self) -> list[str]:
        return sorted(_ROW_MAP.keys())

    def getSpriteBuffer(self) -> bytes:
        self._load_sprite()
        if self._sprite_buffer is None:
            raise FileNotFoundError(f"Sprite sheet not found: {self._sprite_path}")
        return self._sprite_buffer

    @property
    def spriteWidth(self) -> int:
        return self._sprite_width

    @property
    def spriteHeight(self) -> int:
        return self._sprite_height

    @property
    def frameWidth(self) -> int:
        return self._frame_width

    @property
    def frameHeight(self) -> int:
        return self._frame_height


class SkinRegistry:
    """Registry of avatar skins."""

    _instance: SkinRegistry | None = None

    def __init__(self) -> None:
        self._skins: dict[str, SingleFrameSkin] = {}
        self._register_default()

    @classmethod
    def getInstance(cls) -> SkinRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _register_default(self) -> None:
        default_path = str(Path(__file__).parent.parent / "resources" / "single_frame_sprite_sheet.png")
        self._skins["single-frame"] = SingleFrameSkin(
            name="single-frame",
            _sprite_path=default_path,
        )

    def get(self, name: str) -> SingleFrameSkin | None:
        return self._skins.get(name)

    def list(self) -> list[str]:
        return list(self._skins.keys())
