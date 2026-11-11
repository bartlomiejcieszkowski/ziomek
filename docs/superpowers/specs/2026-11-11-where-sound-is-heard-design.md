# Sound that reaches the place it was aimed at

Date: 2026-11-11. A feature plan. Settled across the conversation of 2026-11-11; nothing here is
approved as built, this is the shape agreed before writing.

## Intent and the why

Two things are missing today. A device asked for in settings does not reach the path that plays:
`AudioPlayer` keeps `self.device_name` at `src/ziomek/tts/playback.py:21` and never uses it, and the
registry constructs a backend with no arguments at `src/ziomek/tts/backends/__init__.py:47`. So
`resolve_device()` at `src/ziomek/tts/backends/devices.py:9` answers for tests only. Second, a page can
be the thing that hears — a browser can play sound — but nothing says which side is in charge, and the
browser will not play until a person has interacted with the page.

The plan is for both: aim playback at a chosen device, pass the settings that path can take, and let a
page be allowed to hear when it says it can.

## Goals, non-goals, anti-goals

- Goal: a device named in settings is the device the sound goes to. When nothing matches that name,
  it is reported rather than played somewhere else by accident.
- Goal: extra settings reach an instance. A key that is not a field on `Settings` is dropped in silence
  at `src/ziomek/config.py:96`, so a setting that changes how a stream is opened has to be declared.
- Goal: the shape a device takes is checked before a stream is opened, and samples are converted to the
  rate the device takes.
- Goal: a page that says it can hear is given sounds; a page that has not said so is not.
- Non-goal: exclusive mode everywhere. It is the last thing here, on a machine where the app runs; it
  cannot be answered offline on this box.
- Non-goal: choosing an output device in the browser. `setSinkId` is not available in Firefox or Safari,
  so a page plays on whatever the browser plays on.
- Anti-goal: two places hearing the same utterance, so a person hears it twice.
- Anti-goal: a backend reporting a thing it cannot honour. A path that hands the sound to a browser
  cannot say when a page finished, so it does not claim to wait.

## The decisions taken

- Order of work: device wiring, then the completion answer when a sound ends, then the check as a probe,
  then exclusive mode last, then the browser path with its gate and its indicator.
- A sound that arrives before a page accepts is dropped, not queued. A queue needs a rule for how many
  can be kept and in what order, and a burst of old utterances out of order is worse than silence. The
  indicator says what was not heard, so silence is not left unexplained.
- Only the page knows whether it has been interacted with, so the page reports acceptance over the
  socket that already exists (`src/ziomek/api/roster_ws.py`, which holds plain websockets with no state
  per connection). That needs a flag per connection, not a machine-wide fact.
- The page also has to know which side is in charge. Today the only thing gated like that is dev mode,
  through `get_dev_mode()` at `src/ziomek/api/roster_view.py:27`. The first message on a connection
  states both facts — which side plays, and that accepting is needed — and the indicator is drawn from
  that message. A page that loads again is asked again: the gate is per load, not per machine.
- The gate is a state of the connection, so a connection that drops takes the answer with it.
- A name a machine states wrong (headphones exposed as speakers) is answered by a table of names written
  by hand, because only the jack description and the name reading are reliable, and vendors get the jack
  description wrong in a minority of cases. The key for that table has to be a string, since a device
  index changes when the hardware changes.
- For the completion answer: `finished_callback` is called when a stream becomes inactive, and for an
  output stream not until all generated sample data has been played (the library's own wording). So a
  per-sound answer needs a stream that stops after that sound. The guard that reports a stream showing
  no space stays as the limit on the wait.
- Conversion uses `scipy.signal.resample_poly` on samples already read as mono float32
  (`read_samples()` in `src/ziomek/tts/backends/raw_stream.py`). scipy is already a dependency, so this
  adds none.

## Constraints

- No new dependency without asking. `comtypes` is not installed here; the device class used for the jack
  property is not registered on this machine, so the property route cannot be reached from here.
- `check_output_settings()` takes `WasapiSettings(exclusive=True, explicit_sample_format=True)` as its
  first argument and reports nothing but success or failure; a device reports only its default rate, not
  the format it wants, so the check is the only way to know a combination can be opened.
- `check_output_settings()` cannot run inside a callback thread with the GIL held, so it is called from
  the main thread before a stream is opened.
- `.env` values are read as strings only (`_read_env` in `src/ziomek/config.py`), so the table of names
  has to be written as one value that can be read as a table, not as several keys.
- No test can see a render or hear audio (`tests/test_js_runtime_is_available.py` states this), so the
  gate rule must be readable as a value, in its own part, in the style of `signal.mjs`. The look and the
  sound are confirmed by the person viewing and listening.
- Pages hold markup and links only; behaviour lives in parts. A gate that applies to every page cannot
  live in a debug-only part, so it is its own part, linked by both pages.
- A path that cannot be reached from this machine (the WASAPI property route, the browser gate itself)
  is not asserted in the suite; what is asserted is the rule that decides from a value.

## Approaches

- **A — one place decides, the path takes what it was given.** `resolve_device()` already answers for a
  name; a backend that can be aimed takes the index, a backend that cannot says so. Chosen, because it
  keeps one decision and makes a path that cannot honour an aim answer rather than play by accident.
- **B — the backend resolves its own device.** Rejected: it puts the same decision in six files and lets
  a backend that cannot be aimed fall back to the default in silence.

Chosen: **A**.

## The name for a side that is not confirmed

`device_type.py` already reads a side out of a name. The word `device_type` names a class rather than
the behaviour, and `speaker_or_headphone.md` keeps its title for the same reason. Left open, and it does
not change behaviour: only rename with the author agreeing.
