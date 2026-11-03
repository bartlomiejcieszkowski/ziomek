"""Read the default name lists from the package resources.

Only files in resources ending with `.names.json` are read. A user-provided name list is
not read yet, so the files in resources are the whole of what is available. A file that cannot
be read is reported as an error and the other files are still loaded.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

NAME_LIST_SUFFIX = ".names.json"
RESOURCES_DIR = Path(__file__).parent / "resources"


def list_name(path: str) -> str:
    """The name a list file is known by, which is its file name without the suffix."""
    return path.removesuffix(NAME_LIST_SUFFIX)


def read_list(path: Path) -> list[str] | None:
    """Read one list file, or report why it cannot be read."""
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.error("%s is not JSON", path.name)
        return None

    if not isinstance(content, list):
        logger.error("%s is not a list of names", path.name)
        return None

    names: list[str] = []
    for entry in content:
        if not isinstance(entry, str) or not entry.strip():
            logger.error("%s holds an entry that is not a name", path.name)
            return None
        names.append(entry.strip())

    if not names:
        logger.error("%s is empty", path.name)
        return None

    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        logger.error("%s holds %s more than once", path.name, ", ".join(repeated))
        return None

    return names


def load_name_lists(resources_dir: Path | None = None) -> dict[str, list[str]]:
    """Read every file in resources ending with the suffix, keeping each list under its file name.

    Every loaded list is used as one pool of names, so a list is not read back as a group
    that belongs to one participant.
    """
    root = resources_dir or RESOURCES_DIR
    lists: dict[str, list[str]] = {}

    for path in sorted(root.glob(f"*{NAME_LIST_SUFFIX}")):
        names = read_list(path)
        if names:
            lists[list_name(path.name)] = names

    return lists
