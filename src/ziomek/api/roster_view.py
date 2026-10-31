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


@router.get("/api/roster/view", summary="Roster page", description="Serve the roster page HTML.")
async def get_roster_page() -> HTMLResponse:
    """Serve the roster page HTML (one tile per participant)."""
    return HTMLResponse(_page_html.read_text(encoding="utf-8"))


def transcript() -> list[dict]:
    """The call record as one ordered stream."""
    return list(get_roster().events)


@router.get("/api/roster/transcript", summary="Transcript", description="List what happened in the call, in order.")
async def get_transcript_view() -> JSONResponse:
    """Serve the entries of the current call record."""
    return JSONResponse(content=transcript())
