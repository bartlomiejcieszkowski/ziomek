# Ziomek — Humanize AI

Humanize AI interaction by making it more natural. Work in progress.

**One process:**

- **ziomek** — the call record (participants, what happened in order), TTS synthesis, STT, avatar state machine, gamepad polling, the pages it serves, and an MCP server (port 5004)

**One extension:**

- **Pi Voice Assistant** — keyword-gated listening, gamepad input, and a TUI dashboard on top of the same server

## Quick Start

### Run from the repository

```bash
uv run ziomek
```

`uv` creates a `.venv`, downloads dependencies, and installs `ziomek` in development mode from the local package. The speech part is not installed by default:

```bash
uv run --extra stt python -m ziomek.cli               # STT with the server
uv sync --extra stt                                   # once, then plain uv run works in this shell
```

### Run the published package

```bash
uvx ziomek
uvx "ziomek[stt]"
```

Extras are declared in `pyproject.toml` under `[project.optional-dependencies]` (`stt`), so an install without it has no STT engine. The tools are part of the package itself, so nothing extra is needed to answer an MCP call.

The browser is opened at the roster page on startup; pass `--no-browser` to skip it. Alternative launch scripts:

| Command | What runs |
|---------|-----------|
| `run-ziomek.sh 5004` | ziomek (Linux/macOS) |
| `run-ziomek.bat 5004` | ziomek (Windows) |

## Pages

| Path | What it shows |
|------|---------------|
| `/roster` | The participants of the current call and the transcript panel; this is the page opened on startup |
| `/avatar` | One face, drawn from the skin definition it was given |
| `/debug` | Controls and state, served only when the server runs with `--dev` |
| `/favicon.svg` | The icon the pages link to; a browser asks for it on its own |

The call record lives in server memory. Nothing is written to disk, so a restart clears the call; the transcript is read through `/api/roster/transcript` and formatted as text through `/api/roster/transcript/markdown`.

## The Call Record

A participant joins, is on hold, or leaves. Each action is recorded with the name it happened to, and the pages show that record in order. A line states only the action — the name belongs to the block that holds it — and the voice and the face drawn for a name are carried as separate fields so they can be shown apart from the text.

The roster is built once per server start, in the startup handler, and `get_roster()` raises when no roster was built. There is no lazy path.

### Where a name comes from

1. A name given when joining is kept as it is.
2. Otherwise a free entry from `roster_pool`, preferring an entry that has not been used.
3. Otherwise a name from any loaded list, as one pool, preferring a name not in the current call and then the least used across calls.
4. Otherwise the second part of a name is built from `roster_words`, only when nothing is left in the pool or the lists.

Default lists are read from `src/ziomek/resources` — every file ending with `.names.json`. A file that cannot be read is reported as an error and the other files are still loaded. Usage history and the pairs assigned to a name stay for the life of the process, not per call.

### Voice and face

A pool entry names a voice and a skin, and that setting wins. Otherwise a voice is drawn in order from `src/ziomek/tts/voices.py`, and a face in order from the skins registered for this server, skipping what another participant already holds; when everything is in use it wraps. Once something is drawn for a name it is remembered, so a rejoining name gets the same voice and the same face. `roster_avatar` is used only when no skin is registered.

## Skins Read as Definitions

A skin is a definition, read either as a folder or as an archive, and known by the name inside it — not by the folder name. A duplicate claim is suffixed `_2`, `_3`, and the second claimer is reported as an error.

| Field | Meaning |
|-------|---------|
| `name` | The name the skin answers under |
| `type` | `sheet` or `image` |
| `frame` | Width and height of one frame (a sheet declares it) |
| `grid` | Rows and columns of a sheet |
| `frames` | Map of expression names to a cell or to a file (`name`, or `file:` for a direct picture) |
| `expressions` | The order the frames are shown in, with `interval_ms` and an optional `loop` |
| `fallback` | What to show for a name the definition does not cover |
| `object-fit` | How a frame sits inside the box that draws it, for the whole definition or for one target |

`loop` is true unless stated otherwise: a list that loops returns to its first entry, one that does not stops at its last. An interval is required when more than one frame is listed. A path inside an archive is a name, not a directory; absolute paths and `..` are rejected. An expression that states no fallback is reported as an error, so `neutral` is required inside `frames`.

Placement values are taken from CSS so the format does not name the same thing twice:

| Value | What it does |
|-------|--------------|
| `fill` | Stretches to the box, ignoring aspect |
| `contain` | Keeps the whole frame inside, bars possible on one pair of sides (the default) |
| `cover` | Fills the box so nothing is left empty; overflow is cut |
| `none` | Draws at natural size, which can overflow |
| `scale-down` | Never enlarges — the smaller of `none` and `contain` |

The format states no display size, because the box belongs to the view drawing it. Frames are anchored at the centre and scaled with nearest-neighbour, so pixels do not blur. A target states its own placement in its object form; a marker cannot carry a second part.

The machine-readable schema is `src/ziomek/resources/morda.schema.json`, shipped with the package. Definitions are looked for in `skins_dir`, relative to the directory the server runs in; the package resources are read first, so the default skin keeps a name it claims. The default skin is `src/ziomek/resources/single-frame/`.

Official expression names are the six Ekman expressions — happy, surprised, anger, disgust, fear, sad — plus `neutral` as the baseline. Any other name is allowed in a definition and is not officially supported.

## Audio Playback

A request does not wait for the device; the worker does. Single-shot playback waits until the device has taken what was written, and a second sound is summed with the first only when another sound is on the device and the backend reports that it can mix. Raw data stays mono float32 at the rate it carries — there is no resample step in the library.

| Backend | Behaviour |
|---------|-----------|
| `sounddevice` (default) | One call per sound; a second sound replaces what is already playing |
| `raw_stream` | One explicit stream, written as space allows; no mixing, so a second sound waits |
| `raw_stream_overlap` | One shared stream with samples summed at the position where they are heard; returns while samples are pending |
| `pygame`, `pyaudio`, `playsound` | Alternate backends, skipped at startup when the module cannot be imported |
| `noop` | Does nothing, for tests and for running without a device |

A stream that cannot be opened is reported as an error rather than played through another path, so a test of one backend stays answerable. A stream that shows no space to write for `WRITE_STUCK_SECONDS` (1s) or holds samples for `PLAY_STUCK_SECONDS` (5s) is reported once per sound. Scaling applies to a summed region only when its peak would pass full scale; a single sound keeps its level.

A device choice in settings is not applied by any backend, so it does not reach these paths.

## Gamepad

Polling exists (`src/ziomek/gamepad.py`, a background thread, `--no-gamepad` to skip it), but polled input is not applied to anything: `handle_gamepad_input` is inert because the gamepad is meant to be a control method, not an expression source. The button-to-action mapping for agents is not decided yet. The mapping table below belongs to the Pi extension.

## Launch Commands

```bash
uv run ziomek --host 0.0.0.0 --port 5004 --log-level INFO --voice cosette --cache-dir ./voices
```

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | 5004 | HTTP port |
| `--host` | localhost | Host to bind (0.0.0.0 for remote/Docker) |
| `--model-path` | — | Path to the TTS model |
| `--voice` | default | Voice name; no speaking path reads it, a participant's own voice is used instead |
| `--cache-dir` | ~ | Voice cache directory |
| `--audio-backend` | sounddevice | sounddevice, raw_stream, raw_stream_overlap, pygame, pyaudio, playsound, noop |
| `--audio-device` | — | Device index, name, or `default` (not applied by any backend) |
| `--log-level` | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--no-gamepad` | false | Do not poll gamepad buttons |
| `--no-browser` | false | Do not open the roster page on startup |
| `--no-stt` | false | Do not start the STT engine |
| `--stt-engine` | faster_whisper | STT engine (needs the `stt` extra) |
| `--stt-model` | tiny.en | STT model |
| `--stt-model-dir` | — | Model download directory |
| `--no-mcp` | false | Do not serve the tools; they are served unless this is set |
| `--mcp-stdio` | false | Serve the tools over stdio instead of the transport taken by default |
| `--mcp-port` | same as `--port` | Separate MCP port; a different port means a separate process with its own empty roster |
| `--mcp-config` | false | Expose the full config through MCP (read-only by default) |
| `--scaffold-config` | false | Write a default `ziomek_config.yaml` and exit |
| `--dev` | false | Debug endpoints and the `/debug` page |
| `-v, --verbose` | false | DEBUG logging |

**Usage modes:**

| Command | What runs |
|---------|-----------|
| `uv run ziomek` | Full server (roster page + STT + MCP) |
| `uv run ziomek --no-browser` | Headless server (page not opened) |
| `uv run ziomek --no-browser --no-gamepad` | Standalone API only |
| `uv run ziomek --no-stt` | Server without speech-to-text |
| `uv run ziomek --dev` | Full server with the debug page |

Settings are read from the config file, then the environment, then the command line. A restart is needed for a change to apply, and a restart clears the call.

## Configuration

`ziomek_config.yaml` is written by `--scaffold-config`. Fields that belong to the call record:

| Setting | Default | Description |
|---------|---------|-------------|
| `port` | 5004 | HTTP port |
| `mcp_port` | 5004 | MCP port; same as `port` means one process |
| `no_mcp` | false | Do not serve the tools through MCP |
| `mcp_transport` | http | `http` or `stdio` |
| `audio_backend` | sounddevice | See the backend table |
| `audio_device` | — | Device index or name; not applied by any backend |
| `skins_dir` | skins | Where definitions are looked for, relative to the run directory |
| `roster_pool` | `[]` | Entries of `(name, voice, skin)` — a defined combination, so a join with no name can reach it first |
| `roster_words` | `[]` | Second part of a name, used only when nothing is left in the pool or the lists |
| `roster_avatar` | single-frame | The face used for a participant whose entry names none; read through the registry, never as a path |
| `roster_quiet_for` | 3000 | Milliseconds of quiet before a participant is dropped by the event loop |
| `roster_check_interval` | 1.0 | Seconds between those checks |
| `roster_transcript_default` | open | Whether the transcript panel starts open or closed |

## API Endpoints

### Call record

```bash
# The participants of the current call
curl http://localhost:5004/api/roster

# What happened, in order
curl http://localhost:5004/api/roster/transcript

# The same record as text
curl http://localhost:5004/api/roster/transcript/markdown
```

### Avatar

```bash
# Current expression and cycle (no name is taken here; the state machine answers for the global face)
curl http://localhost:5004/api/avatar/state

# Force an expression
curl -X POST http://localhost:5004/api/avatar/expression \
  -H "Content-Type: application/json" \
  -d '{"name": "John", "expression": "happy"}'

# The picture and the frames a skin declares
curl "http://localhost:5004/api/avatar/sprite?skin=single-frame"

# One picture for a frame that names a file
curl "http://localhost:5004/api/avatar/image?skin=cosette&file=cry.png"

# Feed gamepad or client input
curl -X POST http://localhost:5004/api/avatar/input \
  -H "Content-Type: application/json" \
  -d '{"buttons": [1, 0], "axes": [0, 0, 0], "connected": true}'

# Speak a line, optionally with an expression; the voice is taken as a name, not as a participant
curl -X POST http://localhost:5004/api/avatar/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello", "voice": "cosette", "expression": "happy"}'
```

`ws://localhost:5004/api/avatar/ws` carries state changes to the page.

### TTS

```bash
# Synthesize speech (returns WAV)
curl -X POST http://localhost:5004/api/tts/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, this is a test"}' -o speech.wav

# The names in src/ziomek/tts/voices.py
curl http://localhost:5004/api/tts/voices
```

### STT

```bash
curl http://localhost:5004/api/stt/status
curl -X POST http://localhost:5004/api/stt/start
curl -X POST http://localhost:5004/api/stt/stop
curl -X POST http://localhost:5004/api/stt/transcribe \
  -H "Content-Type: application/json" \
  -d '{"audio_b64": "<base64>", "sample_rate": 16000}'
curl -X POST http://localhost:5004/api/stt/reconfigure \
  -H "Content-Type: application/json" \
  -d '{"engine": "faster_whisper", "model": "base.en"}'
curl http://localhost:5004/api/stt/models
```

`ws://localhost:5004/api/stt/stream` takes `start`, `stop`, `status`, and `reconfigure`.

### Health and debug

```bash
curl http://localhost:5004/status          # uptime, model readiness, which backend is in use
curl http://localhost:5004/                # server identification and key routes
curl http://localhost:5004/api/debug/state # only with --dev
```

Debug endpoints: `/api/debug/state`, `/api/debug/cache`, `/api/debug/config`, `/api/debug/logs`, `POST /api/debug/logs/clear`, `POST /api/debug/config/reload`. The debug page shows TTS, STT, avatar, gamepad, server and cache state. Config reload does not restart the process, so anything read at startup is not changed by it.

## MCP Server

The tools are served unless something says otherwise. On the default transport (HTTP) the routes are added to the main process, so tools see the roster that page shows. Choosing `--mcp-stdio` runs the tools in the process through stdio instead. With a different `--mcp-port`, it is a separate process with its own empty roster — a join there does not appear on the page. Routes: `/mcp`, `/mcp/sse`, `/mcp/message`, `/mcp/health`, `/mcp/info`. `--no-mcp` serves nothing.

| Tool | What it does |
|------|--------------|
| `join` | Add a participant; answers name, voice, call id and state |
| `hold` | Put a participant on hold |
| `leave` | Remove a participant |
| `say` | Speak a line for a participant |
| `write` | Record text as what a participant said |
| `play` | Play an audio file for a participant |
| `transcribe` | Transcribe base64 audio (needs an engine loaded) |
| `start_listening`, `stop_listening`, `get_transcription` | Capture and read what is heard |
| `set_expression`, `get_expression` | Change and read the face |
| `status` | Model readiness, STT state, uptime, the backend in use |

Resources: `voices://`, `models://`, `expressions://`, `config://`. The config resource answers only fields settings has. Running it standalone:

```bash
uv run python -m ziomek.mcp.server
```

A name that is not in the call is answered by the global state machine, so a tool does not say the name was unknown. A join does not report the face it drew; that is in the record, not in the tool response.

## Pi Voice Assistant Extension

Work in progress and not usable yet.

```bash
cd pi-ziomek
npm install
npm run build
```

Add the compiled output to your Pi configuration:

```json
{ "extensions": ["pi-ziomek/dist/index.js"] }
```

The extension reads its configuration from `~/.pi/agent/extensions/pi-ziomek/config.json` (`voice.serverUrl`, `voice.keyword`, `voice.keywords`, `voice.maxListenDuration`, `gamepad.enabled`, `gamepad.pollIntervalMs`, `gamepad.debounceMs`, `gamepad.buttonMap`, `dashboard.enabled`, `dashboard.autoShow`, `dashboard.refreshIntervalMs`). Tool definitions are in `pi-ziomek/src/tools.ts`.

Keyword gating: a keyword is a case-insensitive prefix match, stripped from the transcription before the text is sent to the agent — saying `ziomek, continue` sends only `continue`.

The TUI dashboard shows connection state, engine and model info, the last few transcriptions, gamepad state, and recent actions. It is toggled with the `toggle_dashboard` action or the `/dashboard` slash command.

Default button mapping for the extension: A short listening, B cycle responses, X long listening, Y re-speak the last output, D-pad up/down scroll history, LB/RB previous and next response, Start toggle dashboard, Select show status.

## Testing

```bash
uv run python -m pytest tests/            # plain `uv run pytest` fails on the trampoline script path
uv run python -m pytest tests/ -m "not integration"   # integration tests start a real uvicorn process
uv run ruff check . && uv run ruff format --check .
```

The offline part of the suite covers the call record, the roster, skins and definitions, audio paths, MCP tools and resources, pages, config, packaging. Tests that touch STT or TTS models need downloads; they are not part of an offline run. Tests are named for the behavior they prove. Formatting scope is `src tests scripts`; `docs` is excluded because Markdown plans are historical records.

## Project Layout

```text
.
├── src/ziomek/                  # ziomek package (src layout)
│   ├── cli.py                   # CLI and argument parsing
│   ├── server.py                # App, startup handler, pages, icon
│   ├── config.py                # Settings (file, environment, command line)
│   ├── names.py                 # Reads the default name lists
│   ├── roster.py                # Call record: joining, holding, leaving, names, assignment
│   ├── gamepad.py               # pygame polling; polled input is not applied to anything
│   ├── browser.py               # Opens the roster page unless disabled
│   ├── stt/                     # STT engines and VAD
│   ├── tts/                     # TTS model wrapper, generation, playback and backends
│   │   └── backends/            # sounddevice, raw stream, pygame, pyaudio, playsound, noop
│   ├── avatar/                  # Definitions, discovery, skin registry, state machine
│   │   ├── morda.py             # Reads a definition from a folder or an archive
│   │   ├── discovery.py         # Where definitions are found and how names are claimed
│   │   ├── png.py               # Sizes read from a PNG header
│   │   └── skins.py             # Registry and what each expression shows
│   ├── api/                     # FastAPI endpoints
│   │   ├── roster_view.py       # /api/roster, /roster, transcript and its text form
│   │   ├── avatar.py            # /avatar, state, expression, sprite, image
│   │   ├── avatar_ws.py         # /api/avatar/ws
│   │   ├── stt.py + stt_ws.py   # /api/stt/* and its websocket
│   │   ├── tts.py               # /api/tts/*
│   │   ├── health.py            # /status and /
│   │   └── debug.py             # /api/debug/* (dev mode only)
│   ├── mcp/                     # Tools, resources, HTTP routes, stdio server
│   ├── benchmark/               # Runs stored for comparison
│   └── resources/               # Pages, schema, name lists, default skin, icon
├── tests/                       # Python tests
├── scripts/                     # morda.py packages a skin; extract-changelog.py reads a release section
├── pyproject.toml               # Package config (hatchling), extras, ruff rules
├── VERSION                      # Single source of the version, read by hatch
├── plugin.json                  # Pi plugin manifest, carries the same version
├── mcp.json                     # MCP client config
├── CHANGELOG.md                 # One section per release, in the form the release workflow reads
├── docs/                        # Documentation; docs/internal is gitignored
├── debug_tools/                 # JS debug utilities
└── voices/                      # Voice safetensors (gitignored)
```

## Contributing

1. New MCP tools in `src/ziomek/mcp/tools.py` and resources in `src/ziomek/mcp/resources.py`.
2. New audio backends as a module in `src/ziomek/tts/backends/`, registered by name.
3. New expression names are allowed in a definition; only the six Ekman expressions plus `neutral` are officially supported.
4. New gamepad actions in `pi-ziomek/src/gamepad.ts`; the server-side mapping is still to be decided.

The version comes from `VERSION`. A release commit changes `CHANGELOG.md`, `VERSION`, and `plugin.json` together, with the section heading in the form `scripts/extract-changelog.py` reads.
