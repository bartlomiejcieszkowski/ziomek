"""Find skin definitions in the package resources and in the configured skins directory."""

import logging
import tarfile
from dataclasses import replace
from pathlib import Path

from ziomek.avatar.morda import DefinitionError, definition_names, read_definitions, read_entries

logger = logging.getLogger(__name__)

DEFAULT_SKINS_DIR = Path(__file__).parent.parent / "resources"


def find_definitions(skins_dir: Path, default_dir: Path = DEFAULT_SKINS_DIR) -> list:
    """Definitions in registration order, with the names each one is registered under.

    The default skin comes first, so it keeps a name it claims and anything found in the
    searched directory that claims the same name is registered with a suffix. A definition
    that does not read is reported and skipped rather than answered as a problem on the whole
    source, so one broken definition does not stop the others in the same bundle. A name that
    another definition already claimed is reported with the file carrying each claim, so two
    definitions in one bundle can be told apart.
    """
    found = []
    claimed_by = {}
    claims = {}

    for source, entries, problems in _sources(default_dir) + _sources(skins_dir):
        for answer in read_definitions(source, entries, problems):
            if isinstance(answer, DefinitionError):
                logger.error("%s: %s", source, answer)
                continue

            definition = answer
            name = definition.name
            carrier = source / definition.definition_file
            if name not in claimed_by:
                claimed_by[name] = carrier
            else:
                claims[name] = claims.get(name, 1) + 1
                suffixed = f"{name}_{claims[name]}"
                logger.error(
                    "the name %s is claimed by %s, so %s registers as %s",
                    name,
                    claimed_by[name],
                    carrier,
                    suffixed,
                )
                definition = replace(definition, name=suffixed)

            found.append(definition)

    return found


def _sources(directory: Path) -> list[tuple[Path, dict[str, bytes], list[str]]]:
    """One reading for each source in a directory, with the names it holds.

    A source counts when the names it holds are definitions, which is what makes a folder with
    several definitions for avatars a skin as well. A folder or an archive that holds only
    pictures is not a skin. Only the top is looked at, since what sits inside a source is a name
    and not a directory. An archive is read once, so deciding what a source is does not open it
    again for the definitions it holds.
    """
    if not directory.is_dir():
        return []

    sources = []
    for candidate in [directory, *sorted(directory.iterdir())]:
        if candidate.is_dir():
            names = [entry.name for entry in sorted(candidate.iterdir()) if entry.is_file()]
            if not definition_names(names):
                continue

            problems: list[str] = []
            entries = read_entries(candidate, problems)
            sources.append((candidate, entries, problems))
        elif candidate.suffix == ".morda":
            try:
                entries = read_entries(candidate)
            except (OSError, tarfile.TarError):
                continue

            if definition_names(entries):
                sources.append((candidate, entries, []))

    return sources
