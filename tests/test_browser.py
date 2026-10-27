"""Tests for opening the served avatar page in the local browser."""

from unittest.mock import patch

from ziomek.browser import open_view_page
from ziomek.config import Settings


class TestOpenViewPage:
    """--no-browser gates opening the page; without it the page is opened on success."""

    def test_does_not_open_when_no_browser_is_set(self):
        settings = Settings(no_browser=True)
        with patch("webbrowser.open") as opened:
            assert open_view_page(settings) is False
            opened.assert_not_called()

    def test_opens_avatar_view_page_when_allowed(self):
        settings = Settings(no_browser=False)
        with patch("webbrowser.open") as opened:
            assert open_view_page(settings) is True
            opened.assert_called_once_with("http://localhost:5004/api/avatar/view")

    def test_uses_configured_host_and_port(self):
        settings = Settings(host="127.0.0.1", port=8080)
        with patch("webbrowser.open") as opened:
            open_view_page(settings)
            opened.assert_called_once_with("http://127.0.0.1:8080/api/avatar/view")

    def test_returns_false_when_open_fails(self):
        settings = Settings()
        with patch("webbrowser.open", side_effect=RuntimeError("no browser available")):
            assert open_view_page(settings) is False
