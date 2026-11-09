# A page that asks only when something changed

Date: 2026-11-09. Small change. Approved at m19163, with the parts named here settled by me as the
builder; the approach is the one chosen at m19161.

## Intent and the why

The roster page stops asking for things it can be told about. It is for the person watching a room that
is usually quiet. Today `refresh()` in `src/ziomek/resources/static/roster.mjs:414` asks for the room
(`/api/roster`) and then for the record (`/api/roster/transcript`) on a timer set in `start()` at
`:459-461` — two requests every second, around 120 a minute for one open tab, even when nothing
happened. The goal is the number of requests; how fast a change appears is not what this is for.

## Goals, non-goals, anti-goals

- Goal: after the first picture, the page asks only when something actually changed, and asks only for
  the part that changed. A quiet room costs nothing.
- Goal: what the page draws does not change; only how it is told to draw.
- Non-goal: a timing target. A page may learn about a change a moment later than it would by polling.
- Non-goal: `debug.html`, which polls six things of its own (`:536-541`) and already keeps its own
  connection for STT (`:351`). It stays as it is.
- Anti-goal: a change missed because a connection dropped and the page never got the picture back.
- Anti-goal: a timer kept "just in case", which is the thing being removed.

## Constraints

- A signal carries no content, only which part changed. The shapes the page reads stay in
  `src/ziomek/api/roster_view.py`, so nothing is written twice.
- No test here can see a render, so the rule that decides what to ask for must be callable as a value.
  That is why it lives in its own part, in the style of `numbers.mjs` and `roster_grid.mjs`.
- Changes that reach the app from a synchronous path (a join through the tools or the api) are pushed on
  the server's event loop, as `src/ziomek/api/avatar_ws.py` already does with `call_on_event_loop`.
- The app must keep working when no page is connected to be told.

## Approaches

- **A — tell the page that something changed, let it ask once.** The signal carries only which part
  changed; the drawing path stays where it is. A quiet room costs zero requests after the load; a change
  costs the one request for the part that changed. Chosen, because it is the smallest shape that reaches
  the goal and keeps the existing reading path.
- **B — send what the page would have asked for.** Zero requests after the load, but it needs a message
  shape per part and a second way to feed the drawing, so the same content is reached through two paths.
- **C — long-polling.** Fewer requests without a connection, but trades one kind of failure for another:
  requests that stay open, timeouts, and proxies. Dropped: a connection is already part of this project
  (`src/ziomek/api/avatar_ws.py`, used by `renderer.html:222`).

## Decided

- A signal path of its own, `/api/roster/ws`, in `src/ziomek/api/roster_ws.py`. It is not added to
  `/api/avatar/ws`, because that path belongs to the single view and its first message is the current
  state of one participant; a page watching the room would have to understand two shapes. One message
  shape here: which part changed, as `room` or `record`.
- The app reports a change where it makes one: a participant is added (`Roster.join`, `src/ziomek/roster.py:156`), removed (`release` at `:198`, `Participant.leave` at `:83`, `drop_quiet` at `:190`), or its state changes (`hold` at `:66`, `resume` at `:73`) — those are a room change; an entry written to the record (`Participant.record`, the append at `:325`) is a record change. A join that also writes to the record is reported as two changes, not one.
- Two hooks, not one. `machine.on_change = self.push_hook` (`:216`) stays as it is for the single view; the roster gets a hook for what changed, called with the name of the part.
- The page asks once for both parts at load, as it does today, then only for what a signal named. On a connection that comes back after a drop it asks for both parts once, and retries after 3 seconds, as `debug.html:387` does. No timer.
- The rule that maps a signal to what to ask for lives in `src/ziomek/resources/static/signal.mjs`, so it can be tested as values; the page part calls it. A signal that names nothing leaves the page asking for nothing.

## Left to the builder

Test names and the exact signatures. My choices, stated so they can be checked: the hook is
`Roster(changed=...)`, called as `self.changed("room")` and `self.changed("record")`; the signal path
broadcasts with `tell_page(kind)`; the rule module exports `what_to_ask_for(signal)` and
`what_to_ask_on_connection()`. Tests first, red. A string test is used only for what cannot be checked
as a value: that the page no longer asks on its own. The plan is
`docs/superpowers/plans/2026-11-09-page-asks-only-when-something-changed.md`.
