# Pages are served outside `/api`

Date: 2026-11-01. Scope: the two HTML routes of the server. Status: decision made, implemented.

## Decision

An HTML page is not an API endpoint, so the page routes do not live under `/api`:

- `GET /roster` serves the roster page (`src/ziomek/api/roster_view.py`, reading `src/ziomek/resources/roster.html`).
- `GET /avatar` serves the renderer page (`src/ziomek/api/avatar.py`, reading `src/ziomek/resources/renderer.html`).

The data routes keep their `/api` prefix: `GET /api/roster`, `GET /api/roster/transcript`, `GET /api/roster/transcript/markdown`, `GET /api/avatar/state`, `POST /api/avatar/input`, the STT and TTS routes under their prefixes, and the WebSocket routes.

The health payload separates the two kinds, so the list it returns does not mix a page with an endpoint: a `pages` key with `GET /roster` and `GET /avatar`, and no page path inside the `avatar` endpoint list (`src/ziomek/api/health.py`).

The URL opened by default and the URLs printed on stdout follow these paths, so `view_page_url()` returns `/roster` and `avatar_page_url()` returns `/avatar` (`src/ziomek/browser.py`).

## Why

Only `/` and `/status` were outside `/api` before this change, and those are not pages either — they are the health payload. A path under `/api` that returns an HTML document reads as an endpoint that is not one, which is why the two page routes looked out of place.

## Affected files

Route strings, the URLs in `src/ziomek/browser.py`, the health payload, the tests that request the pages (`tests/test_roster_view.py`, `tests/avatar/test_view.py`, `tests/test_browser.py`, `tests/test_server_gates.py`, `tests/test_packaging.py`), and the fetches inside the served HTML (`src/ziomek/resources/roster.html`). The page HTML does not fetch its own route, so the fetch paths in the pages stay under `/api`.
