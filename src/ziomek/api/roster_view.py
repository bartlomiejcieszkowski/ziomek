"""ziomek roster API endpoints — the call page."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from ziomek.avatar.skins import SkinRegistry
from ziomek.roster import get_roster

router = APIRouter(tags=["Roster"])

_page_html = Path(__file__).parent.parent / "resources" / "roster.html"
_resources = Path(__file__).parent.parent / "resources"


def expression_for(participant) -> str | None:
    """The expression that this participant's own machine is showing."""
    machine = getattr(participant, "state_machine", None)
    if machine is None:
        return None
    current = machine.getCurrentState()
    return None if current is None else current.expressionName


def skin_name(participant, settings=None) -> str:
    """The skin for this participant: its entry wins, otherwise the configured default."""
    if settings is None:
        from ziomek.server import _settings

        settings = _settings
    return participant.skin or getattr(settings, "roster_avatar", "")


def avatar_for(participant, settings=None) -> dict | None:
    """The skin and the row that draw this participant's avatar.

    Only a registered skin can be drawn, so a name that is not in the registry shows nothing;
    an expression the row map does not know is read as neutral.
    """
    name = skin_name(participant, settings)
    skin = SkinRegistry.getInstance().get(name)
    if skin is None:
        logging.warning("Skin %s is not registered, so the tile draws no avatar", name)
        return None
    expression = expression_for(participant) or ""
    return {"skin": name, "row": skin.getFrameRow(expression, 0)}


def tiles(settings=None) -> list[dict]:
    """One tile per participant in the call."""
    roster = get_roster()
    return [
        {
            "name": participant.display_name,
            "status_text": participant.status_text,
            "system_text": participant.system_text,
            "state": participant.state,
            "held_seconds": participant.held_seconds,
            "texts": [entry.as_dict() for entry in participant.texts],
            "events": list(participant.events),
            "expression": expression_for(participant),
            "avatar": avatar_for(participant, settings),
        }
        for participant in roster.participants
    ]


@router.get("/api/roster", summary="Roster tiles", description="List the participants of the current call.")
async def get_roster_view() -> JSONResponse:
    """Serve the tiles for the participants of the current call."""
    return JSONResponse(content=tiles())


def panel_default() -> str:
    """The state the page starts with: config decides, and a value outside open/closed is read as closed."""
    from ziomek.server import _settings

    if not _settings:
        return "open"  # settings not loaded: the documented default
    return _settings.roster_transcript_default  # validated to open or closed by Settings


@router.get("/roster", summary="Roster page", description="Serve the roster page HTML.")
async def get_roster_page() -> HTMLResponse:
    """Serve the roster page HTML with the configured panel default (one tile per participant)."""
    html = _page_html.read_text(encoding="utf-8").replace("__TRANSCRIPT_DEFAULT__", panel_default())
    return HTMLResponse(html)


_PAST = {"join": "joined", "hold": "is on hold", "left": "left", "leave": "left"}


def transcript() -> list[dict]:
    """The call record as one ordered stream."""
    return list(get_roster().events)


def format_line(entry: dict) -> str:
    """Build one line for one entry.

    A name and an author belong to the block that holds them, so a written text is the text as
    it was recorded; an action becomes a sentence. One rule, used by the panel and the file.
    """
    if entry.get("action") == "text":
        return entry.get("text", "")

    if not (entry.get("action") or entry.get("text")):
        return ""  # Review focus line 1: an entry with nothing to show produces no line
    return sentence(entry)


def blocks(entries: list[dict]) -> list[dict]:
    """Group the ordered stream into runs of the same participant.

    A run is the consecutive text entries of one participant; a system line stays where it
    happened, so the order is what the page sees. A run with no lines produces nothing, and a
    later run is never merged into an earlier group."""
    grouped = []
    for entry in entries:
        if not (entry.get("name") or entry.get("action") or entry.get("text")):
            continue  # Review focus line 1: an entry with nothing to show produces no line
        if entry.get("action") == "text" and entry.get("author") == "agent":
            line = format_line(entry)
            if not line:
                continue
            key = (entry.get("name", ""), entry.get("author", ""))
            if grouped and grouped[-1]["kind"] == "group" and (grouped[-1]["name"], grouped[-1]["author"]) == key:
                grouped[-1]["lines"].append(line)
                continue
            grouped.append(
                {"kind": "group", "name": entry.get("name", ""), "author": entry.get("author", ""), "lines": [line]}
            )
            continue
        line = format_line(entry)
        if line:
            # Anything written by the system is not what the participant said, so it stays
            # as its own item and keeps the name and the author for the line that shows it.
            item = {"kind": "system", "name": entry.get("name", ""), "text": line}
            if entry.get("author"):
                item["author"] = entry["author"]
            grouped.append(item)
    return [g for g in grouped if g["kind"] == "system" or g["lines"]]


def sentence(entry: dict) -> str:
    """Build the system line for one entry, in the words the record stores."""
    word = _PAST.get(entry.get("action", ""), entry.get("action", ""))
    name = entry.get("name", "")
    return f"{name} {word}." if name else f"{word}."


@router.get("/api/roster/transcript", summary="Transcript", description="List what happened in the call, in order.")
async def get_transcript_view() -> JSONResponse:
    """Serve the entries of the current call record."""
    return JSONResponse(content={"entries": transcript(), "blocks": blocks(transcript())})


def markdown_text(grouped: list[dict], timestamp: str) -> str:
    """Build the file content from blocks."""
    parts = [f"# transcript — {timestamp}", ""]
    for block in grouped:
        if block["kind"] == "system":
            author = block.get("author")
            # The author stays as text: colors cannot show in a file, so both sides keep it.
            head = f"{block.get('name', '')} ({author})" if author else block.get("name", "")
            parts.append(f"> {head} — {block['text']}" if head else f"> {block['text']}")
            continue
        name = block.get("name", "")
        author = block.get("author")
        header = f"{name} ({author})" if author else name
        parts.append(f"### {header}")
        for line in block["lines"]:
            parts.append(f"{line}  ")
        parts.append("")
    return "\n".join(parts) + "\n"


def clock() -> str:
    """Format the current time as the filename wants it."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


@router.get(
    "/api/roster/transcript/markdown", summary="Transcript", description="The file content for the current call record."
)
async def get_markdown(request: Request) -> Response:
    """Serve the file content, with the clock the page asked for."""
    at = request.query_params.get("at") or clock()
    return Response(content=markdown_text(blocks(transcript()), at), media_type="text/markdown")
