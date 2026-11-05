"""Find skin definitions in the package resources and in the configured skins directory."""

import logging
import tarfile
from dataclasses import replace
from pathlib import Path

from ziomek.avatar.morda import DefinitionError, definition_names, read_definitions

logger = logging.getLogger(__name__)

DEFAULT_SKINS_DIR = Path(__file__).parent.parent / "resources"


def find_definitions(skins_dir: Path, default_dir: Path = DEFAULT_SKINS_DIR) -> list:
    """Definitions in registration order, with the names each one is registered under.

    The default skin comes first, so it keeps a name it claims and anything found in the
    searched directory that claims the same name is registered with a suffix. A definition
    that does not read is reported and skipped rather than answered as a problem on the whole
    source, so one broken definition does not stop the others in the same bundle.
    """
    found = []
    claimed_by = {}
    claims = {}

    for source in _sources(default_dir) + _sources(skins_dir):
        for answer in read_definitions(source):
            if isinstance(answer, DefinitionError):
                logger.error("%s: %s", source, answer)
                continue

            definition = answer
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

    A source counts when it holds a definition name at its top level, which is what makes a
    folder with several definitions for avatars a skin as well. A folder or an archive that
    holds only pictures is not a skin.
    """
    if not directory.is_dir():
        return []

    sources = []
    if _holds_definition(directory):
        sources.append(directory)

    for entry in sorted(directory.iterdir()):
        if entry.is_dir() and _holds_definition(entry):
            sources.append(entry)
        elif entry.suffix == ".morda" and _holds_definition(entry):
            sources.append(entry)

    return sources


def _holds_definition(path: Path) -> bool:
    """The names a source holds, which is what decides whether it is a skin.

    Only the top is looked at, since what sits inside a source is a name and not a directory.
    """
    if path.is_dir():
        names = [entry.name for entry in sorted(path.iterdir()) if entry.is_file()]
        return bool(definition_names(names))

    try:
        with tarfile.open(path) as archive:
            names = [member.name for member in archive.getmembers() if member.isfile()]
    except (OSError, tarfile.TarError):
        return False

    return bool(definition_names(names))
