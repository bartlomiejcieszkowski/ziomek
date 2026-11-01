"""Open the served avatar page in the local browser."""

import logging
import webbrowser

from ziomek.config import Settings

_logger = logging.getLogger(__name__)


def view_page_url(settings: Settings) -> str:
    """URL of the page that opens by default: the roster."""
    return f"http://{settings.host}:{settings.port}/roster"


def avatar_page_url(settings: Settings) -> str:
    """URL of the served avatar view page for the given settings."""
    return f"http://{settings.host}:{settings.port}/avatar"


def print_page_urls(settings: Settings) -> None:
    """Print both page addresses so the user can reach either page from the terminal."""
    print(view_page_url(settings))
    print(avatar_page_url(settings))


def open_view_page(settings: Settings) -> bool:
    """Open the roster page unless opening is disabled.

    Returns True when the page was opened, False when it was skipped (no_browser)
    or the browser could not be opened.
    """
    if settings.no_browser:
        return False

    url = view_page_url(settings)
    try:
        opened = webbrowser.open(url)
    except Exception as exc:  # browser backends raise assorted errors
        _logger.warning("Could not open browser: %s", exc)
        return False

    if not opened:
        _logger.warning("Could not open browser: %s", url)
        return False

    _logger.info("Opened roster page in browser: %s", url)
    return True
