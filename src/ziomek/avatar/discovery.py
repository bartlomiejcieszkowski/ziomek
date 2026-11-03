"""Find skin definitions in the package resources and in the configured skins directory."""

import logging
from dataclasses import replace
from pathlib import Path

from ziomek.avatar.morda import DEFINITION_FILE, DefinitionError, read_definition

logger = logging.getLogger(__name__)

DEFAULT_SKINS_DIR = Path(__file__).parent.parent / "resources"


def find_definitions(skins_dir: Path, default_dir: Path = DEFAULT_SKINS_DIR) -> list:
    """Definitions in registration order, with the names each one is registered under.

    The default skin comes first, so it keeps a name it claims and anything found in the
    searched directory that claims the same name is registered with a suffix. A definition
    that does not read is reported and skipped rather than raised, so one broken skin does
    not stop the others.
    """
    found = []
    claimed_by = {}
    claims = {}

    for source in _sources(default_dir) + _sources(skins_dir):
        try:
            definition = read_definition(source)
        except DefinitionError as error:
            logger.error("%s: %s", source, error)
            continue

        name = definition.name
        if name not in claimed_by:
            claimed_by[name] = source
        else:
            claims[name] = claims.get(name, 1) + 1
            suffixed = f"{name}_{claims[name]}"
            logger.error(
                "the name %s is claimed by %s, so %s registers as %s",
                name,
                claimed_by[name],
                source,
                suffixed,
            )
            definition = replace(definition, name=suffixed)

        found.append(definition)

    return found


def _sources(directory: Path) -> list[Path]:
    """Skin folders and archives inside one directory.

    A definition at the root of the directory counts as a skin, which is the layout used
    when a definition sits beside its image. Subfolders are found by their definition file,
    since a folder without one is not a skin.
    """
    if not directory.is_dir():
        return []

    sources = []
    if (directory / DEFINITION_FILE).is_file():
        sources.append(directory)

    for entry in sorted(directory.iterdir()):
        if entry.is_dir() and (entry / DEFINITION_FILE).is_file():
            sources.append(entry)
        elif entry.suffix == ".morda":
            sources.append(entry)

    return sources
