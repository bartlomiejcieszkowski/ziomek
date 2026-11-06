"""Read the pages the way a browser does: a page holds its markup and links to its parts."""

from pathlib import Path

RESOURCES = Path(__file__).parent.parent / "src" / "ziomek" / "resources"


def page_shell(name="roster.html"):
    """The file as stored, for rules about what a page holds."""
    return (RESOURCES / name).read_text(encoding="utf-8")


def static_source(name):
    """One part of a page, as stored."""
    return (RESOURCES / "static" / name).read_text(encoding="utf-8")


def loaded_parts(name="roster.html"):
    """The files a page loads, in the order its links name them."""
    shell = page_shell(name)
    return [line.split("/static/")[1].split('"')[0] for line in shell.splitlines() if "/static/" in line]


def served_page(client, name="roster.html"):
    """What a browser gets for a page: the page itself, then the files its links name."""
    return client.get("/roster").text + "".join(client.get("/static/" + part).text for part in loaded_parts(name))


def page_source(name="roster.html"):
    """The page as a browser assembles it: its shell, then the parts in the order it loads them."""
    return page_shell(name) + "".join(static_source(part) for part in loaded_parts(name))


def debug_page_source():
    """The page served in dev mode: the same parts with the part that states values added to it."""
    return page_source("roster_debug.html")
