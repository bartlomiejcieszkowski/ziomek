# Changelog

All notable changes to this project are documented here.

## [0.7.2] - 2026-11-05

### Fixed

- A closing brace that ended the loop drawing tiles early is gone from `src/ziomek/resources/roster.html` and from `src/ziomek/resources/roster_debug.html`; it came from separating the page from the part that states values. The rest of the loop body fell outside the loop, so the parser stopped at the brace that closes the function and the page script ran nothing at all: no participant count, no tiles, and no handler on the buttons.

## [0.7.1] - 2026-11-05

### Added

- The avatars defined by their own files are part of the repository, so a package built from a clean checkout ships them: `blue.morda.json`, `green.morda.json`, `orange.morda.json`, `purple.morda.json`, `red.morda.json` and `teal.morda.json` in `src/ziomek/resources/single-frame/`. Before this only `morda.json` and `sheet.png` were tracked there, so a wheel built elsewhere carried the original skin and not the bundle.

## [0.7.0] - 2026-11-05

### Added

- Cells are sized from the room as measured rather than from a fixed minimum. The grid is divided by splitting the biggest block along its longer edge until there are as many blocks as there are names to draw, so the number of cells matches the number of participants instead of overshooting to the next whole grid. Grid tracks stay whole numbers of pixels and a block spans a whole number of tracks, which is how a split becomes a span, and blocks of the same size are taken in position order. A tile is capped at the largest size a whole number of frames fits into, because pixels stay even only under whole-number scaling, and the smallest frame among the skins present is used so every tile on the page is measured the same way. A capped tile stays in the middle of its cell, and a tile keeps its own size when no frame size was read for its skin.
- A page can state what it measured. It asks through a function it does not define, and `src/ziomek/resources/roster_debug.html`, served instead of `roster.html` only when the server runs with `--dev`, is the part that carries the values to `POST /api/debug/render`. The report states the room, the base cell, the frame size and the whole frames it fitted, and each block with the place it took in the grid and the size its own tile was given; a page that drew one block states no blocks, since that block is the whole grid the cell part already describes. A report that changed nothing is not sent again.
- `debug_get_render_state`, the first tool carrying a `debug_` prefix, answers the last report kept in memory. It is not listed outside dev mode, since a tool that cannot answer should not appear in a client's list, and a call made anyway is refused. Nothing is persisted.
- `src/ziomek/dev_mode.py` keeps the mode as one value, read both by the paths that answer only in dev mode and by the choice of which page is served, so a page that states values is only given where something can read them back.
- A bundle can hold several definitions, each named for one avatar as `<name>.morda.json`, and all of them are read from one folder or one `.morda` archive. They are answered in the order they are read: the file at the top first, then the names for avatars in name order, which is what decides who keeps a name they both claim. A definition that does not read is answered as its error without stopping the other definitions in the same bundle, and each error names the definition it came from. `scripts/morda.py` still writes one definition per archive, so a bundle holding several is outside its scope.
- The panel follows to the end only when the viewer was already there, since the position is read before a line is added. A position within four pixels of the bottom counts as being at the end.

### Changed

- The requirement that a definition has something to show for a name it does not cover points at an expression named `neutral` instead of a frame called `neutral`, because expressions reference a frame by name and a frame is not required to carry that name. A definition that states no fallback has to state that expression, and the fallback resolves through the first entry the expression states.

### Fixed

- A long run of characters with no space in it breaks inside the boxes instead of pushing past them, which is what made the page scroll sideways.
- `src/ziomek/resources/morda.schema.json` no longer carries an identifier pointing at a domain we do not hold. The schema is read as data and nothing reads that identifier, so this changes no behavior.

## [0.6.0] - 2026-11-04

### Added

- Drawing follows the definition. The registry builds from the definitions found in `skins_dir`, a cell is cut from its sheet and a frame that names a file is read as its own picture, so nothing is skipped by the registry; each page places what it was given inside the box it draws.
- `object-fit` for a definition, with the values `fill`, `contain`, `cover`, `none` and `scale-down`, defaulting to `contain` as applied by the reader; a target states its own in the object form. Frames are placed from the centre and scaled with nearest neighbour so pixels do not blur.
- `/api/avatar/image` answers one image by name with its size, for a frame that names a file.
- Two audio backends, `raw_stream` and `raw_stream_overlap`, chosen with `audio_backend`. The second sums samples at the position they are heard and scales only a region that would pass full scale. A stream that shows no space for 1 second, or holds samples for more than 5 seconds, is reported once per sound.
- A voice and a face are drawn in order for a name that is not in a pool entry, skipping what the call holds, and the pair is remembered for that name, so a rejoin gets the same voice and face.
- The join entry records the voice and the face assigned to a name. The transcript panel shows them in its own color, and the saved file writes the same words as text, since a color cannot show there.
- `src/ziomek/tts/voices.py` is one source for the voice names, read by the API and by the MCP resource; the status endpoint answered a shorter subset before.
- An icon served at `/favicon.svg` (`src/ziomek/resources/favicon.svg`) and linked by the three pages.

### Changed

- `/api/avatar/sprite` answers for one skin: the grid, the sizes and the frames each expression shows come from its definition, so nothing is inferred from the ratio between height and width; `src/ziomek/avatar/sprites.py` is gone.
- A tile carries the frame to draw (its kind, position, placement and size) instead of a row number.
- A request returns before the device has taken the samples. Single-shot playback waits for the device instead of guessing a duration, overlapping playback is not stopped before the device has taken what it was given, and the wait is for the space measured when the first sample was written.
- `AudioPlayer.play()` routes to mixing when another sound is on the device and the backend reports mixing; what is on the device is counted under a lock.
- An action line states only what happened, because the name belongs to the block that holds it.
- The corner labels of a tile are painted above its avatar and placed at the same inset as the text.
- The page uses the image address the server answers with instead of building another prefix around it.

### Fixed

- Tools that take no arguments answer a call (`src/ziomek/mcp/tools.py`), since the dispatch path passes arguments to every handler.
- The config resource no longer reports a level, which settings does not have; its test builds real settings instead of a stand-in that answers any name.

## [0.5.1] - 2026-11-03

### Added

- The skin format: a definition file `morda.json` in a skin folder, or an uncompressed tar archive (`.morda`) carrying the image files and that definition. A definition names the skin, states the sheet grid or the single frame, says which frames belong to each expression, the order they are shown in and the interval between them, and names a fallback used when the requested expression is not there. `scripts/morda.py` packages a skin folder into an archive and warns when the definition is missing.
- `src/ziomek/resources/morda.schema.json`, the machine-readable schema for a definition, checked with `jsonschema` (now a dependency). A definition is reported with all its problems listed together, and a sheet whose picture does not match the grid it declares is not read.
- Name lists in the package resources: every file ending with `.names.json` is read as one pool of names (`polish_male.names.json`, `polish_female.names.json`). A name already used in the call is not picked, the least used name is picked next, and a file that cannot be read is reported as an error without stopping the other files.
- `skins_dir` in the settings, where regular skins are looked up (default `skins`), with the package resources read first, so the default skin keeps a name it claims and a skin that claims it again is registered with a suffixed name.

### Changed

- The default skin is its own folder, `src/ziomek/resources/single-frame/`, with its definition and its sheet instead of a single PNG file. Its definition maps the same rows as before, so nothing about what is drawn changes.
- `roster_avatar` names a skin instead of a file path and defaults to `single-frame`; an entry in `roster_pool` also names the skin that draws that participant's face, and a name that is not registered draws nothing.
- Each tile shows the row its own skin maps to for the expression that participant is showing, and the page asks for the sheet of that skin through `/api/avatar/sprite?skin=`.
- Names are taken in this order: the name a participant joined with, then a free entry in `roster_pool`, then any name from the loaded lists, then the words in `roster_words` as the second part.
- The baseline expression is named `neutral` instead of `idle`, which is what is used when the requested expression is not known.
- PNG dimensions are read through one helper (`src/ziomek/avatar/png.py`) shared by the registry and the reader, so a picture that is not a PNG is reported instead of read as bytes.

### Fixed

- An entry added to an archive carries its size, so a packaged definition reads back with content instead of as an empty entry.

## [0.5.0] - 2026-11-02

### Added

- A roster of participants for a call: join, hold, leave, and a page that shows one tile per participant with the expression of that participant
- A transcript panel on the roster page: the lines of the call in order, with the author kept, and a Save button that downloads them as Markdown or JSON
- `roster_transcript_default` in the settings, which decides whether that panel starts open or closed (a value outside those two words is read as `closed`); `roster_pool`, `roster_words`, `roster_quiet_for` and `roster_check_interval` carry the rules for names and quiet drop
- MCP tools `say`, `play` and `write`: `say` says as a participant and records the text unless `record` is set to false, `play` plays text with a voice without taking part in a call, `write` records text for a participant without producing audio

### Changed

- The HTML pages are served outside `/api`: `/roster` and `/avatar`
- The sidebar has a fixed width bound to the right side of the window, and the roster takes the rest of the window; below 900 px the stacked fallback is kept
- Tool descriptions state what a tool does instead of giving usage instructions, so `speak` became `say` and `play`

### Fixed

- The plugin manifest carries the same version as the project instead of claiming its own
- `-webkit-line-clamp` needs `display: -webkit-box`, so the ellipsis is drawn by the clamp instead of a marker written by JavaScript

## [0.4.3] - 2026-10-30

### Changed

- Data files (pages and sprite sheet) live in one folder, `src/ziomek/resources`, and the code builds paths from it
- Generated config files (`ziomek_config.yaml`, `ziomek_server_config.yaml`) are no longer tracked in git

### Fixed

- The release build: `[tool.hatch.build] only-packages` dropped data files from the sdist, and CI builds the wheel from that sdist, so `uv build` failed with `Forced include not found: src/ziomek/resources`; the force-include now applies to the sdist as well as the wheel
- Stale default port in the launcher scripts, which still showed `5003` instead of `5004`

## [0.4.2] - 2026-10-29

### Fixed

- Installed wheel ships the page assets and the sprite sheet through `[tool.hatch.build.targets.wheel.force-include]`; `only-packages` dropped them, so an installed package answered 404 for the avatar view under `uvx`
- Packaging guard test reads `pyproject.toml` with `tomllib` so data files cannot be dropped from the wheel again

## [0.4.1] - 2026-10-29

### Fixed

- Avatar view page restored, with `/api/avatar/ws` pushing the current expression to connected clients
- STT callbacks scheduled on the event loop captured at startup instead of the running loop
- The STT worker's shutdown-time connection error is logged at debug level only; genuine errors stay visible

## [0.4.0] - 2026-10-28

### Added

- `--no-stt` flag and `no_stt` config key; the STT engine is created only when the optional `stt` extra is installed, and the install hint names `ziomek[stt]` rather than the library alone
- CLI exits with an error when MCP flags are used without the `mcp` package installed
- `--no-browser` now works: the served avatar page is opened on successful startup unless it is set
- File-based transcription path (`start_from_file()`) for benchmarks and tests; microphone mode is unchanged for the server
- STT benchmark results record the voice used; summary and CSV group by voice, model, and category
- `ruff format` gate in CI, with formatting applied across the codebase

### Changed

- `--no-vscode` renamed to `--no-gamepad` (its only real effect was skipping gamepad polling); stale `no_vscode` keys in existing config files are ignored — breaking for flag users
- Default-port references corrected to 5004 in CLI help, the config scaffold, docstrings, and the pi-ziomek client defaults
- Benchmark per-iteration output moved to debug level; the summary prints the test text snippet
- `.gitignore` narrowed from all `*.csv` to `tts_accuracy.csv` plus `benchmarks/`

### Fixed

- MCP HTTP endpoint answers JSON-RPC at `/mcp` (it returned 405); the session manager runs inside the app lifespan; the info page moved to `/mcp/info`; `/mcp/sse` and `/mcp/message` stay as aliases
- RealtimeSTT worker processes are reaped on stop, so pytest no longer hangs at exit on Windows
- Audio handed to transcription is normalized float32 (int16 caused ONNX dtype errors)
- TTS model is loaded before the accuracy benchmark runs
- Missing `.close()` on FasterWhisperEngine suppressed during shutdown
- Third-party loggers (RealtimeSTT, whisper, ctranslate2, torch) silenced; stdout and stderr wrapped as UTF-8 for non-ASCII transcriptions
- pi-ziomek TTS client calls the endpoints the server actually exposes (`/generate`, `/speak`, `/voices`); unsupported `cancel()` and `getLastWavPath()` removed
- MCP server version reads from `VERSION` instead of a hardcoded string

## [0.3.0] - 2026-10-22

### Added

- Merged server and client into single process (port 5004)
- STT streaming endpoint via WebSocket (`/api/stt/stream`) for live transcription
- STT HTTP API: status, start, stop, transcribe, reconfigure, models endpoints
- STT engine reconfiguration at runtime (engine/model switching)
- Debug mode (`--dev`) with debug endpoints and debug webpage
- Verbose logging (`--verbose`/`-v`) with STT event logging
- Colored stdout logging (uvicorn-style) with JSON log files
- Log ring buffer with `/api/debug/logs` and `/api/debug/logs/clear` endpoints
- Version centralization via single `VERSION` file at repo root
- Automated release workflow on VERSION bump
- Health endpoint enriched with STT info, audio backend/device, cache stats
- Request ID middleware for structured logging
- `conftest.py` with STT engine cleanup fixture for test isolation
- MCP server implementation with 8 tools (speak, transcribe, start/stop listening, transcription, set/get expression, status)
- MCP resources (voices, models, expressions, config) with read-only default
- MCP HTTP transport with streamable_http_app() (port-based routing)
- Benchmark CLI: `ziomek benchmark run tts|stt` with --store flag
- Benchmark result store with versioned history (save, list, diff)
- TTS accuracy round-trip benchmark (Levenshtein ratio + WER metrics)
- STT quality benchmark (Levenshtein ratio + WER metrics)
- BenchmarkWav output with configurable output directory
- Pi Voice Assistant extension scaffold (keyword gating, gamepad, dashboard)
- Marketplace config (plugin.json, mcp.json) for Agent Plugins 1.0
- UTF-8 stderr wrapping to handle non-ASCII STT transcription output

### Changed

- Default port changed from 5003 to 5004 (merged server/client)
- CLI unified: `ziomek` instead of `ziomek server`/`ziomek client`
- Config file renamed: `ziomek_server_config.yaml` → `ziomek_config.yaml` (backward compatible)
- Default STT engine changed from whisper_cpp to faster_whisper (whisper_cpp segfaults on Windows)
- STT engine starts recording immediately on startup

### Fixed

- Async transcription callback handling via `asyncio.run_coroutine_threadsafe`
- `transcribe_chunk` timeout to avoid blocking on RealtimeSTT.text()
- Debug endpoint JSON serialization for STTState enum
- WebSocket tests with proper mock engine setup

## [0.2.0] - 2026-09-30

### Added

- Pluggable audio playback backend system with support for sounddevice, pygame.mixer, pyaudio, playsound, python-rtmixer, and noop backends
- Configurable device selection by index, name, or system default
- YAML config file loading with `ziomek_server_config.yaml` (current dir)
- Configuration precedence: CLI flags > environment variables > config file > hardcoded defaults
- `scaffold-config` subcommand to generate default configuration files
- `IBackend` protocol for extensible audio backends
- OpenAPI documentation for ziomek server -- Swagger UI at `/docs` and ReDoc at `/redoc`
- OpenAPI documentation for ziomek client -- Swagger UI at `/docs` and ReDoc at `/redoc`
- Pydantic schemas for API request/response documentation

### Changed

- CORS now uses regex pattern `http://localhost:\d+` for proper origin matching
- Server version now read dynamically from package `__version__`

### Fixed

- Type annotation for `VoiceStateCache.cache_dir` to accept `str | None`
- `test_cors` — CORS headers now correctly returned for localhost requests
- PNG sprite test data generation for `test_skin_load_sprite_from_file`
- Added `excited` expression to skin registry
- Import sorting across 8+ files

## [0.1.2] - 2026-09-28

### Changed

- Updated version bump
- Added `readme` field to `pyproject.toml`

## [0.1.1] - 2026-09-28

### Changed

- Version bump

## [0.1.0] - 2026-09-27

### Added

- Standalone ziomek package with TTS synthesis, avatar state machine, and gamepad integration
- VS Code extension for gamepad-controlled avatar with TTS
- Launcher scripts for server management
- CI build workflow and PyPI publishing workflow
- MIT license file
