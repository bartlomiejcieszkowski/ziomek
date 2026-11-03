"""ziomek avatar skin registry — a skin is a definition that can be drawn."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ziomek.avatar.discovery import DEFAULT_SKINS_DIR, find_definitions
from ziomek.avatar.morda import (
    Cell,
    Definition,
    Reference,
    Target,
    fallback_target,
    read_entries,
    resolve_reference,
)

logger = logging.getLogger(__name__)


@dataclass
class Skin:
    """A definition with the contents it names, read from where it came from."""

    definition: Definition
    _entries: dict[str, bytes] | None = field(default=None, repr=False)

    @property
    def name(self) -> str:
        return self.definition.name

    def read_file(self, name: str) -> bytes | None:
        """The bytes behind a name, from the folder or the archive the definition was read from."""
        if self.definition.source is None:
            return None
        if self._entries is None:
            self._entries = read_entries(self.definition.source)
        return self._entries.get(name)

    def sheet(self) -> bytes | None:
        """The image a page draws from, which is the sheet the definition names."""
        sheet = self.definition.sheet
        if sheet is None:
            return None
        return self.read_file(sheet.file or "")

    def order(self, expression_name: str) -> list[Target]:
        """The frames an expression shows, in the order it declares them.

        An expression the definition does not cover reaches what it falls back to, so the name
        itself is never used as a frame.
        """
        declared = self.definition.expressions.get(expression_name)
        if declared is None:
            return _fallback_order(self.definition)
        frames = []
        for reference in declared.entries:
            resolved = resolve_reference(self.definition, reference)
            if resolved is not None:
                frames.append(resolved)
        return frames

    def cell_for(self, expression_name: str) -> Cell | None:
        """The cell that draws an expression, which is the first frame in its order."""
        for frame in self.order(expression_name):
            if frame.cell is not None:
                return frame.cell
        return None

    def frame_count(self, expression_name: str) -> int:
        """How many frames an expression shows; a frame that names a file is not one."""
        return len([frame for frame in self.order(expression_name) if frame.cell is not None])

    def interval_ms(self, expression_name: str) -> int | None:
        declared = self.definition.expressions.get(expression_name)
        return None if declared is None else declared.interval_ms

    def loops(self, expression_name: str) -> bool:
        declared = self.definition.expressions.get(expression_name)
        return True if declared is None else declared.loop

    def expression_names(self) -> list[str]:
        """The names this definition covers, in the order it declares them."""
        return list(self.definition.expressions)

    def draws_any_frame(self) -> bool:
        """Whether anything here can be drawn, which needs a cell to show."""
        return any(frame.cell is not None for frame in self.definition.targets.values())


def _fallback_order(definition: Definition) -> list[Target]:
    fallback = fallback_target(definition)
    return [] if fallback is None else [fallback]


class SkinRegistry:
    """Skins that can be drawn, keyed by the name each one registered under."""

    def __init__(self, skins_dir: Path, default_dir: Path = DEFAULT_SKINS_DIR) -> None:
        self._skins: dict[str, Skin] = {}
        for definition in find_definitions(skins_dir, default_dir):
            skin = Skin(definition=definition)
            if not skin.draws_any_frame():
                logger.error("%s names no cell, so it cannot be drawn yet", definition.name)
                continue
            self._skins[definition.name] = skin

    def get(self, name: str) -> Skin | None:
        return self._skins.get(name)

    def list(self) -> list[str]:
        return list(self._skins.keys())


_registry: SkinRegistry | None = None


def build_registry(settings) -> SkinRegistry:
    """Build the registry from the settings, once, where the app is created."""
    global _registry
    _registry = SkinRegistry(Path(settings.skins_dir))
    return _registry


def get_registry() -> SkinRegistry | None:
    """The registry built at app creation. Nothing is drawn when none was built."""
    return _registry
