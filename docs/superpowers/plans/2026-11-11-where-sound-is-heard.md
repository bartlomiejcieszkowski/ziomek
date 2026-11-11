# Sound that reaches the place it was aimed at — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal:** A device named in settings is the device the sound goes to, the settings a path can take reach
its instance, and a page that says it can hear is the thing that hears.

**Architecture:** One decision about which device is meant, in `devices.py`, handed to a backend that can
take it; backends that cannot take an aim or an extra setting answer that they cannot, so nothing plays
on a default by accident. A sound is reported finished when the device says it has taken everything,
instead of being watched with a poll. The browser path is a backend that hands the sound off and does not
claim to wait; whether a page may hear is a state of its own connection, read from the first message on
that connection.

**Tech Stack:** Python 3.12, sounddevice (ctypes calls unchanged), scipy (already a dependency),
FastAPI websockets, browser parts as ES modules.

**Spec:** `docs/superpowers/specs/2026-11-11-where-sound-is-heard-design.md`

## Global Constraints

- Tests are written first and watched red; one behavior per test; names state behaviors, not code facts.
  Value tests are the authority; a string test only for what cannot be checked as a value. Rules in
  `docs/internal/tests.md`.
- Python tests run with `uv run python -m pytest`; browser value tests run per file with
  `node --test <file>` (`node --test tests/` discovers nothing here). Do not run whole files that reach
  the model or the network offline.
- Nothing in this plan can be proved by a render or by hearing: the look and the sound are confirmed by
  the person viewing and listening. A path reachable only on this machine (the WASAPI property route, the
  browser gate as it behaves in a page) is not asserted in the suite.
- No new dependency. `comtypes` is not installed here and the audio endpoint class is not registered on
  this machine, so the property route stays out of the tests.
- Code names follow `docs/internal/project_naming_rules.md` (the rules there do not apply to test names).
- Line endings: `.md` in `docs/`, `VERSION` and `plugin.json` are CRLF; files in
  `src/ziomek/resources/static/` are mixed CRLF and LF — keep each file as it is, `.mjs` and HTML are not
  ruff-formatted.
- Feature commits touch code and tests only, never `CHANGELOG.md` or `VERSION`. Commit with `--signoff`,
  no `Co-Authored-By`, subject at most 72 chars in the form `<type>(scope): description`, imperative and
  lowercase. Do not push.

---

### Task 1: A device named in settings reaches the path that plays

**Files:**
- Modify: `src/ziomek/tts/playback.py` (`__init__` at `:16-22`, `device_name` at `:21` is never used)
- Modify: `src/ziomek/tts/backends/__init__.py` (`get()` at `:47`, constructs with no arguments)
- Modify: `src/ziomek/tts/backends/base.py`, `pyaudio.py`, `sounddevice.py`, `raw_stream.py`, `playsound.py`, `noop.py`
- Test: `tests/tts/test_the_device_named_in_settings_is_the_one_that_hears.py`

**Interfaces:**
- Consumes: `resolve_device(device_spec, backend)` at `src/ziomek/tts/backends/devices.py:9`;
  `read_type_from_name(name)` at `src/ziomek/tts/backends/device_type.py:11`.
- Produces: `AudioPlayer(backend_name="sounddevice", device=None)` keeps the index it resolved;
  `BackendRegistry.get(name, device=None, extra_settings=None)`; each backend answers
  `can_be_aimed_at_a_device` and `can_take_extra_settings` as a value.

**Tests first:**
- [ ] a device named in settings is the device the sound goes to
- [ ] a name is matched to a device without case, as `resolve_device()` already does
- [ ] a name that matches nothing is reported, and nothing is played on the default
- [ ] a path that cannot be aimed says so, rather than answering with the default device
- [ ] the side meant is read from a name when a name is given as a side, not as an index

**Run:** `uv run python -m pytest tests/tts/test_the_device_named_in_settings_is_the_one_that_hears.py -q`
red on the first three; then green. Keep the existing surface in `tests/test_config.py:95-117` and
`tests/tts/test_backends.py` passing — do not rewrite a passing test to fit the new shape.

**Commit:** `feat(playback): the device named in settings is the one that hears`

---

### Task 2: A sound is reported finished when the device says it has taken everything

**Files:**
- Modify: `src/ziomek/tts/backends/raw_stream.py` (`pump()` and `wait_for_device()`, the guard at `:90`)
- Modify: `src/ziomek/tts/backends/sounddevice.py` (the wait for a single sound)
- Test: `tests/tts/test_a_sound_is_reported_finished_when_the_device_has_taken_it.py`

**Interfaces:**
- Consumes: `finished_callback()` from an output stream — called when the stream becomes inactive, and for
  an output stream not until all generated sample data has been played. So a per-sound answer needs the
  stream to stop after that sound; a stream kept open for mixing cannot answer per sound.
- Produces: `wait_for_device(stream, capacity, rate)` becomes a wait on the answer the stream gives; the
  limits `WRITE_STUCK_SECONDS` and `PLAY_STUCK_SECONDS` stay as the limit on that wait, with the same
  message shape (`the stream for %s ...`).

**Tests first:**
- [ ] a sound is reported finished when the stream says all of it has been played
- [ ] the stop of a sound is not reported before the device has taken the samples
- [ ] a stream that shows no space is still reported after its limit, rather than waited on forever
- [ ] a stream kept open for mixing is not waited on, and is not claimed as finished

**Run:** `uv run python -m pytest tests/tts/test_a_sound_is_reported_finished_when_the_device_has_taken_it.py tests/tts/test_raw_stream.py -q`

**Commit:** `feat(playback): a sound is reported finished when the device has taken it`

---

### Task 3: A setting that changes how a stream is opened reaches the instance

**Files:**
- Modify: `src/ziomek/config.py` (`Settings` fields at `:16-17`; `:96` drops a key that is not a field)
- Modify: `src/ziomek/tts/backends/__init__.py`, the backends that can take an extra setting
- Test: `tests/test_a_setting_that_changes_a_stream_reaches_the_instance.py`, and the table of names in
  `tests/tts/test_a_name_a_machine_states_wrong_is_answered_by_the_table.py`

**Interfaces:**
- Consumes: `Settings.audio_backend`, `Settings.audio_device` as they are; nothing is renamed.
- Produces: fields for what `WasapiSettings` takes — exclusive on or off, a period count — and nothing
  else, so a key stays inside what the path can honour. A key that is not a field is reported rather than
  dropped in silence; the table of names is read as one value that can be read as a table, because
  `_read_env` reads strings only.

**Tests first:**
- [ ] a setting for a stream reaches the instance that opens it
- [ ] a setting that a path cannot take is reported, not dropped in silence
- [ ] a name written in the table answers for the side it states
- [ ] the table wins over a name read, because it is what a person wrote
- [ ] a name not in the table stays unanswered, as the reading alone answers it

**Run:** `uv run python -m pytest tests/test_a_setting_that_changes_a_stream_reaches_the_instance.py tests/tts/test_a_name_a_machine_states_wrong_is_answered_by_the_table.py tests/tts/test_a_device_name_is_read_as_the_side_it_names.py tests/test_config.py -q`

**Commit:** `feat(config): a setting that changes a stream reaches the instance that opens it`

---

### Task 4: The shape a device takes is checked before a stream is opened

**Files:**
- Modify: `src/ziomek/tts/backends/raw_stream.py` (`open_stream(rate)` at `:71`, no device and no settings),
  `src/ziomek/tts/backends/sounddevice.py`
- Create: `src/ziomek/tts/backends/format.py` — the check, and the conversion to the rate the device takes
- Test: `tests/tts/test_a_device_is_checked_for_the_shape_it_takes_before_a_stream_is_opened.py`

**Interfaces:**
- Consumes: `check_output_settings(device, channels, dtype, samplerate, extra_settings)` as the first
  argument to `WasapiSettings`; `scipy.signal.resample_poly`; the existing `read_samples()` that already
  answers mono float32 and the rate it was read at.
- Produces: `can_open(settings)` answering yes or no before a stream is opened, on the main thread —
  never inside a callback thread, where the GIL cannot be released; `to_the_shape_the_device_takes(samples,
  rate, target_rate)` converting only the rate, leaving mono float32 as it is.

**Tests first:**
- [ ] a device that answers no to the shape is reported as not usable, and nothing is played through
      another path
- [ ] samples are changed to the rate the device takes, and a sound keeps its level
- [ ] a check is not asked from inside a callback thread
- [ ] a device reports its default rate, and no test claims it reports a format

**Run:** `uv run python -m pytest tests/tts/test_a_device_is_checked_for_the_shape_it_takes_before_a_stream_is_opened.py tests/tts/test_raw_stream.py -q`

**Commit:** `feat(playback): a device is checked for the shape it takes before a stream is opened`

---

### Task 5: Exclusive mode, last, on a machine where the app runs

**Files:**
- Modify: `src/ziomek/tts/backends/format.py`, `src/ziomek/tts/backends/raw_stream.py`, `src/ziomek/config.py`
- Test: `tests/tts/test_exclusive_mode_is_only_used_where_the_shape_can_be_kept.py`

**Interfaces:**
- Consumes: Task 3 (the settings reach the instance) and Task 4 (the check answers whether a combination
  can be opened, with `explicit_sample_format=True`).
- Produces: exclusive mode opened only when the check answers yes for the device named; otherwise the
  device is reported as not usable in that mode, and the shared path is used.

**Tests first:**
- [ ] exclusive mode is not opened for a combination that answers no
- [ ] exclusive mode keeps the rate it was opened at, so a rate that does not match is not opened
- [ ] a device that cannot be used in this mode is reported, and the sound is not played on the default

**Run:** `uv run python -m pytest tests/tts/test_exclusive_mode_is_only_used_where_the_shape_can_be_kept.py tests/tts/test_a_device_is_checked_for_the_shape_it_takes_before_a_stream_is_opened.py -q`

The exclusive path itself depends on this machine, so what is tested is the decision, not the hardware.
The sound on a WASAPI exclusive device is confirmed by the person listening.

**Commit:** `feat(playback): exclusive mode is opened only where the shape can be kept`

---

### Task 6: A path that hands the sound to a page, and the gate that says a page may hear

**Files:**
- Create: `src/ziomek/tts/backends/handed_to_a_page.py` — a path that hands off, does not wait
- Modify: `src/ziomek/api/roster_ws.py` (the connection keeps its own answer; the first message says
  which side plays and that being asked is needed), `src/ziomek/tts/backends/__init__.py`
- Create: `src/ziomek/resources/static/sound_gate.mjs` — the gate rule, as a value
- Test (python): `tests/test_a_sound_given_to_a_page_that_cannot_hear_is_not_played.py`
- Test (browser): `tests/ziomek/resources/static/sound_gate.test.mjs`

**Interfaces:**
- Consumes: `_connected_clients` in `src/ziomek/api/roster_ws.py` (plain websockets, no state per
  connection today); `signal.mjs` and `read_signal(text)` as they are; the kinds already in use there are
  `room` and `record`, so a third kind is added rather than an existing one being changed.
- Produces: the contract gains the third kind — a path that hands off instead of waiting — and a backend
  that reports it honestly: no wait, because nothing can tell the app when a page finished.
  `sound_gate.mjs` exports `which_side_hears(message)` and `may_hear(page_state)`; the page sets its own
  state when it is asked, and a connection that drops takes the answer with it.

**Tests first:**
- [ ] a sound given to a page that has not said it may hear is not played
- [ ] a page that says it may hear is then given sounds
- [ ] a page that loaded again is asked again, not assumed able
- [ ] the first answer on a connection names which side plays and that being asked is needed
- [ ] a path that hands off does not claim to wait, and `list_devices()` answers with nothing

**Run:** `uv run python -m pytest tests/test_a_sound_given_to_a_page_that_cannot_hear_is_not_played.py tests/test_a_page_is_told_what_changed.py -q` and
`node --test tests/ziomek/resources/static/sound_gate.test.mjs`

**Commit:** `feat(playback): a page that says it may hear is the thing that hears`

---

### Task 7: The indicator says what was not heard, and why

**Files:**
- Create: `src/ziomek/resources/static/sound_gate.css` and the element made by `sound_gate.mjs`
- Modify: `src/ziomek/resources/roster.html`, `src/ziomek/resources/roster_debug.html` (links only)

**Interfaces:**
- Consumes: `sound_gate.mjs` from Task 6; the debug-mode pill (`docs/superpowers/specs/2026-11-09-debug-mode-pill-design.md`,
  built by `roster_debug.mjs`, styled in `roster_debug.css`) stays what it is — it says which page was
  loaded, and this says something different.
- Produces: an indicator drawn by the part, not by markup in a page (pages hold markup and links only),
  on any page that cannot hear, because the browser policy is not a thing only dev pages have. When a
  sound was dropped, it says what was not heard; it does not blame.

**Tests first:**
- [ ] a page links the part that draws the indicator, and holds no element for it
- [ ] the part makes the indicator when a page cannot hear
- [ ] the indicator says nothing will be heard until the page is asked
- [ ] after a sound was dropped, the indicator names what was not heard

A test here can only read definitions: which page links which part, which part makes the indicator. The
look is confirmed by the person viewing the page.

**Run:** `node --test tests/ziomek/resources/static/sound_gate.test.mjs tests/ziomek/resources/static/page_parts.test.mjs`

**Commit:** `feat(page part): the page says what it can hear and what was not heard`

---

## Review Focus

The reviewer checks one thing at a time, reads the code and reports; does not run anything. For each
question there is an expected answer, so a finding is a yes or a no with a line in the package.

1. **A device that cannot be aimed** — expected: it says which device was asked for and plays nothing.
   Not: the default device answering for it in silence. Test in Task 1.
2. **A device that wants a shape the sound cannot be given in** — expected: reported as not usable, not
   played through another path, and no answer that says a sound was played when nothing was heard. Test in Task 4.
3. **A sound that arrives before a page is asked** — expected: dropped, and the indicator says what was
   not heard. Not: held and replayed later out of order. Tests in Task 6 and Task 7.
4. **A connection that drops, or a page that loads again** — expected: the answer goes with the
   connection, so the next load is asked again; nothing keeps answering for a page that is gone. Test in Task 6.
5. **A check asked from a callback thread** — expected: never; it is asked on the main thread before a
   stream is opened. Test in Task 4.

---

## Out of this plan, still open

- The word `device_type` in `src/ziomek/tts/backends/device_type.py` names a class rather than the
  behaviour, and the period count carried by `WasapiSettings` (`buffer_frames_ms`) is a different word from
  `block_length`. Only rename with the author agreeing.
- A `.env` cannot carry the table of names as several keys, because `_read_env` reads strings only; the
  shape of that value is decided in Task 3 and needs a rule for what happens when it cannot be read as a
  table.
- The key for the table has to be a string; an index changes when the hardware changes, so it is not the
  name to write.
- `tests/test_version.py` cannot be verified while the server runs; it needs `uv sync`.
- Nothing in this plan is pushed, and tagging is the human's work.
