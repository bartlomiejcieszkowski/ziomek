# A pill that says the page is the dev one

Date: 2026-11-09. Small change.

## Intent and the why

A page served while the app runs with `--dev` shows two things: a small pill in light grey in the
bottom-right corner saying `debug mode`, so the person looking at it can tell which page is loaded, and
a box in the bottom-left corner that prints what the page measured. The reason is not decoration: dev
mode cannot be seen any other way in a page, and together the two settle an open question — the pill
proves the debug part ran, and the box shows whether a measurement was ever reached.

## Goals, non-goals, anti-goals

- Goal: both appear only on a page that loaded the debug part; never on a normal page.
- Goal: what is printed is the same report the page posts, so what you see and what the server stored
  cannot disagree.
- Non-goal: printing a poll that failed before it measured anything. That needs `refresh()` to say
  something instead of returning in silence (`src/ziomek/resources/static/roster.mjs:424-426`), which is
  a separate change.
- Anti-goal: a look that competes with the call view — it is an indicator, not part of the record.

## Constraints

- Only the debug part knows dev mode. `get_roster_page` serves `roster_debug.html` when
  `settings.dev_mode`, and nothing else in a page can tell. So the element can only come from
  `roster_debug.mjs`.
- No test here can see a render (`tests/test_js_runtime_is_available.py` states this plainly), so a
  test can check definitions only: which page links which part, which part makes the indicator. The
  look is confirmed by the person viewing the page.
- Pages hold markup and links only; behaviour lives in parts (rule 4 in `docs/internal/tests.md`), so
  no markup element for the pill in a page.

## Approaches

- **A — one rule in the shared `roster.css`.** Fewer files, but a selector that only ever appears in
  dev mode lives in a file both pages load, and a test about the debug indicator would read a shared
  part.
- **B — a debug-only part: `roster_debug.css` linked only by `roster_debug.html`.** Everything that
  exists only in dev mode stays together: the page that links the debug part, the part that makes the
  indicator, the rule that styles it. Costs one more part file and one more link.

Chosen: **B**, because debug-only things are already kept in debug-only files (`roster_debug.html`,
`roster_debug.mjs`) and a test reads the part it is about.

## Decided

- The indicator is a pill in the bottom-right corner, fixed to the window, with the text `debug mode`
  and class `.debug_mode`.
- The box that prints what was measured is fixed in the bottom-left corner, class `.debug_values`, and
  updates whenever a report is sent.
- Both elements are created by `roster_debug.mjs` and appended to the document; their rules live in
  `roster_debug.css`; `roster_debug.html` links that stylesheet. Pages hold no markup for them.
- Printing uses the same values that `state_sizes.report` already builds (`build_report` in
  `src/ziomek/resources/static/state_sizes.mjs`), so one call serves both the page and the server. The
  text of a report is its first argument, which `build_report` keeps under the name `path`; on screen
  that is what says why nothing was measured.

## Left to the builder

The greys and sizes: my proposal is a light grey fill with readable text, in the style of the values
already used (`rgba(0,0,0,.1)` fill, `#666` text, small size and radius). I avoided `#999` because it
is already reserved for the held state (`docs/internal/project_naming_rules.md`), and showing a state is
not what this is. I kept the values inside the debug-only rule rather than `colours.css`, because the
roster pages do not load `colours.css`; if you want palette values in one place, that would mean the
debug page linking it too, which is a bigger change.

Tests first, red, in `tests/test_roster_debug.py`: the page that loads the debug part links its own
stylesheet part and its part makes the indicator; the page without the debug part links no stylesheet
for it and makes no indicator. Name them as behaviours, not as code facts. Commit only after both are
green and `uv run ruff format --check .` is clean on the files touched.
