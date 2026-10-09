"""ziomek — Humanize AI backend server."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ziomek")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
