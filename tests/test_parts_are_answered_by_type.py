"""What a browser gets when it asks for a file the page links to."""

from fastapi.testclient import TestClient

from tests.roster_page_helpers import RESOURCES, page_shell
from ziomek import server
from ziomek.config import Settings


def app(dev_mode):
    return TestClient(server.create_app(Settings(no_gamepad=True), dev_mode=dev_mode))


def test_a_link_on_the_page_names_a_file_that_is_there():
    for name in page_shell().split('"'):
        if "/static/" in name:
            assert (RESOURCES / "static" / name.split("/static/")[1]).exists(), f"{name} is not in the folder"


def test_a_stylesheet_is_answered_as_a_stylesheet():
    client = app(False)
    assert client.get("/static/roster.css").headers["content-type"].startswith("text/css")


def test_a_part_of_the_page_is_answered_as_code_the_browser_runs():
    client = app(False)
    for name in [name.split("/static/")[1] for name in page_shell().split('"') if "/static/" in name]:
        wants = "text/css" if name.endswith(".css") else "application/javascript"
        assert client.get("/static/" + name).headers["content-type"].startswith(wants), (
            f"{name} is not answered as {wants}"
        )


def test_the_page_is_answered_as_a_document():
    assert app(False).get("/roster").headers["content-type"].startswith("text/html")


def test_a_page_that_is_asked_for_is_not_answered_through_the_debug_path():
    assert "roster_debug" not in app(False).get("/roster").text


def test_a_page_asked_for_in_dev_mode_is_answered_through_the_debug_path():
    assert "roster_debug" in app(True).get("/roster").text
