"""ziomek roster API endpoints — the call page."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from ziomek.roster import get_roster

router = APIRouter(tags=["Roster"])

_page_html = Path(__file__).parent.parent / "resources" / "roster.html"


def expression_for(participant) -> str | None:
    """The expression that this participant's own machine is showing."""
    machine = getattr(participant, "state_machine", None)
    if machine is None:
        return None
    current = machine.getCurrentState()
    return None if current is None else current.expressionName


def tiles() -> list[dict]:
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


@router.get("/api/roster/view", summary="Roster page", description="Serve the roster page HTML.")
async def get_roster_page() -> HTMLResponse:
    """Serve the roster page HTML with the configured panel default (one tile per participant)."""
    html = _page_html.read_text(encoding="utf-8").replace("__TRANSCRIPT_DEFAULT__", panel_default())
    return HTMLResponse(html)


_PAST = {"join": "joined", "hold": "is on hold", "left": "left", "leave": "left"}


def transcript() -> list[dict]:
    """The call record as one ordered stream."""
    return list(get_roster().events)


def blocks(entries: list[dict]) -> list[dict]:
    """Group the ordered stream into runs of the same participant.

    A run is the consecutive text entries of one participant; a system line stays where it
    happened, so the order is what the page sees. A run with no lines produces nothing, and a
    later run is never merged into an earlier group."""
    grouped = []
    for entry in entries:
        if entry.get("action") == "text" and entry.get("author") and entry["author"] != "system":
            if not entry.get("text"):
                continue
            if (
                grouped
                and grouped[-1]["kind"] == "group"
                and grouped[-1]["name"] == entry["name"]
                and grouped[-1]["author"] == entry["author"]
            ):
                grouped[-1]["lines"].append(entry.get("text", ""))
                continue
            grouped.append(
                {"kind": "group", "name": entry["name"], "author": entry["author"], "lines": [entry.get("text", "")]}
            )
            continue
        grouped.append({"kind": "system", "text": sentence(entry)})
    return [g for g in grouped if g["kind"] == "system" or g["lines"]]


def sentence(entry: dict) -> str:
    """Build the system line for one entry, in the words the record stores."""
    word = _PAST.get(entry.get("action", ""), entry.get("action", ""))
    return f"{entry.get('name', '')} {word}."


@router.get("/api/roster/transcript", summary="Transcript", description="List what happened in the call, in order.")
async def get_transcript_view() -> JSONResponse:
    """Serve the entries of the current call record."""
    return JSONResponse(content={"entries": transcript(), "blocks": blocks(transcript())})
