"""Tests for opening the served avatar page in the local browser."""

from unittest.mock import patch

from ziomek.browser import open_view_page, print_page_urls
from ziomek.config import Settings


class TestOpenViewPage:
    """--no-browser gates opening the page; without it the page is opened on success."""

    def test_does_not_open_when_no_browser_is_set(self):
        settings = Settings(no_browser=True)
        with patch("webbrowser.open") as opened:
            assert open_view_page(settings) is False
            opened.assert_not_called()

    def test_opens_roster_page_when_allowed(self):
        settings = Settings(no_browser=False)
        with patch("webbrowser.open") as opened:
            assert open_view_page(settings) is True
            opened.assert_called_once_with("http://localhost:5004/roster")

    def test_uses_configured_host_and_port(self):
        settings = Settings(host="127.0.0.1", port=8080)
        with patch("webbrowser.open") as opened:
            open_view_page(settings)
            opened.assert_called_once_with("http://127.0.0.1:8080/roster")

    def test_returns_false_when_open_fails(self):
        settings = Settings()
        with patch("webbrowser.open", side_effect=RuntimeError("no browser available")):
            assert open_view_page(settings) is False

    def test_opened_page_is_the_roster(self):
        # The default page that opens is the roster, not the avatar view.
        settings = Settings()
        with patch("webbrowser.open") as opened:
            assert open_view_page(settings) is True
            opened.assert_called_once_with("http://localhost:5004/roster")

    def test_both_pages_are_printed_to_stdout(self, capsys):
        # Both addresses are printed so the user can reach either page from the terminal.
        settings = Settings()
        with patch("webbrowser.open"):
            print_page_urls(settings)
        out = capsys.readouterr().out
        assert "http://localhost:5004/roster" in out
        assert "http://localhost:5004/avatar" in out
