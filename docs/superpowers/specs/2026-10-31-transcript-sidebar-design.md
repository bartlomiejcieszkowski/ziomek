# Transcript sidebar on the roster page

## Intent

The roster page gains a right-hand panel that shows what the agents said during the current call, in the order it happened, attributed to the name of the participant who wrote it — a conversation like Teams shows. It is for a person watching the page; agents cannot read it back yet (that is idea 10 in `docs/internal/IDEAS.md`).

## Goals

- One stream across the whole call, not per tile.
- Lines from the agent and lines from the system, in the order they happened. Join, hold and leave appear as system lines in the stream, worded as sentences: `John joined.`, `John is on hold.`, `John left.`
- Open or closed on load from a config setting, and the user can flip it on the page.
- A **Save** button with a `(...)` menu that opens the formats available — Markdown and JSON, both wired. Choosing one downloads the file in the browser, so nothing is written by the server and nothing stays on disk. Markdown is assembled from the entries; JSON is `JSON.stringify(roster.transcript)` from the payload. This is the one part of the feature that outlives a call, as a file in the user's own downloads.

## Non-goals

- No transcript tool for agents, no read-side on the record.
- No timestamps on the lines (the record appends in order; times would only be needed to show them).
- No changes to the single view (`src/ziomek/resources/renderer.html`) — it only receives one participant's payload.

## Constraints

- TDD, red test first; `docs/internal/` is not committed; nothing is pushed by the agent.
- The roster page reads values with `textContent`, never `innerHTML` (pi-lens warning).
- Config keys stay in the existing `roster_*` group in `src/ziomek/config.py`.

## Approaches

1. **Transcript data.** Built from `roster.events` on the server (chosen) — that list is already one chronological stream across participants, so the order is correct and every entry of the record is shown as written. Rejected: merging `tile.events` in the browser, which loses cross-participant order.
2. **Default reaching the page.** Injected into the served page (chosen): `roster_transcript_default` (`open` / `closed`) in the settings, and `src/ziomek/api/roster_view.py` substitutes the value when `src/ziomek/resources/roster.html` is served. Rejected: a field in the `/api/roster` payload (needs a data change for a display setting) and a separate config endpoint (a second request for one value).

Chosen: transcript built from the record on the server, default injected into the page at serve time.

## Decided parts

- **Layout:** fixed two-pane grid — tiles on the left, the panel on the right, both visible at once. The toggle hides only the right pane; when hidden the tiles take the full width. On a narrow window the panel stacks below (my call: a fixed two-pane breaks at a width I cannot read from config, so stacking is what keeps it usable).
- **Toggle:** a control in the panel header on the page, outside the part the toggle hides, so a closed panel can be opened again. The page opens with the value from config; after that the last click is remembered in a cookie (`ziomek_panel`, read by page JS), which survives reloads and later visits of the same browser session. Config decides when there is nothing stored; a value the reader cannot parse falls back to config (the cookie carries `open` or `closed`, not a number). The toggle label says `hide` while the panel is shown and `show` while it is hidden — one class on the layout decides visibility, and the label follows it.
- **Line format:** an agent line is `name — text` with the author kept; a system line is a sentence built from the action in the record, `name joined.` / `name is on hold.` / `name left.`, and the two kinds can be told apart by author.
- **Shape:** `transcript()` in `src/ziomek/api/roster_view.py` returns every entry from the record in order: entries with text and an author render as the agent line, action entries render as the system sentence. The served page carries the panel, its toggle, and the configured default. `tiles()` keeps its own per-tile event list unchanged.
- **Saved file:** the same single stream as the panel shows — participant names inline, system lines as sentences, no grouping by participant, no timestamps (the record has no time). Built with `Blob` and a download link, so no route and no path rules. JSON is the payload stringified, which is what makes the second format cheap.
- **Filename:** `ziomek_{YYYY-MM-DD}_{HHMM}_transcript.{md|json}`, built in the browser from the clock at download time (the record carries no timestamps), underscores as separators, no `:` since Windows filenames cannot have one. The first file for a call is the last file — nothing accumulates as `transcript (1).md`.
- **Lines are not rewritten.** A line is written once, with the wording it had at the time it happened, and never changed afterwards — `John is on hold.` stays in the stream even if that participant is later dropped. The panel is a record of what happened, not a live status view.

## Left to the builder

- Wording of the panel header and the toggle label (the system sentence wording is fixed by the examples above).
- The token used for the injected value in `roster.html`.
- A JSON download is an option, **not wired as its own code path** beyond `JSON.stringify` — no formatting logic. Markdown is the readable form; the menu picks which one to write.
