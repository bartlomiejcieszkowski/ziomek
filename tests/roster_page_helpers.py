"""Read the pages the way a browser does: a page holds its markup and links to its parts."""

from pathlib import Path

RESOURCES = Path(__file__).parent.parent / "src" / "ziomek" / "resources"


def page_shell(name="roster.html"):
    """The file as stored, for rules about what a page holds."""
    return (RESOURCES / name).read_text(encoding="utf-8")


def static_source(name):
    """One part of a page, as stored."""
    return (RESOURCES / "static" / name).read_text(encoding="utf-8")


def asked_for(name="roster.html"):
    """What a page asks for: the files its links name, then what each part asks for."""
    parts = []
    for line in [line for line in page_shell(name).splitlines() if "/static/" in line]:
        for quoted in line.split('"'):
            if "/static/" in quoted:
                parts.append(quoted.split("/static/")[1])
    ordered = []
    pending = list(parts)
    while pending:
        part = pending.pop(0)
        if part in ordered:
            continue
        ordered.append(part)
        for target in static_source(part).split('from "'):
            name_part = target.split('"')[0].replace("./", "")
            if name_part.endswith(".mjs") and name_part not in ordered:
                pending.append(name_part)
    return ordered


def loaded_parts(name="roster.html"):
    """The files a page loads, in the order it asks for them."""
    return asked_for(name)


def served_page(client, name="roster.html"):
    """What a browser gets for a page: the page itself, then the files its links name."""
    return client.get("/roster").text + "".join(client.get("/static/" + part).text for part in loaded_parts(name))


def parts_of_page(name="roster.html"):
    """What a page is made of, by file name: its shell plus every part it asks for."""
    found = {name: page_shell(name)}
    for part in loaded_parts(name):
        found[part] = static_source(part)
    return found


def part_of_page(name, part):
    """One file a page asks for; a test reads the file it is about, not the whole page."""
    assert part in loaded_parts(name), f"{part} is not a part the page asks for"
    return static_source(part)


def page_source(name="roster.html"):
    """The page as a browser assembles it: its shell, then the parts in the order it loads them."""
    return page_shell(name) + "".join(static_source(part) for part in loaded_parts(name))


def debug_page_source():
    """The page served in dev mode: the same parts with the part that states values added to it."""
    return page_source("roster_debug.html")
