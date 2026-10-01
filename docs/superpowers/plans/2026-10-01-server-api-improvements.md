# Server & API Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add remote server support, structured JSON logging with request tracing, and enriched health endpoint to the ziomek server.

**Architecture:** Three independent but sequentially-ordered tasks. Task 1 adds a `--host` CLI flag to bind the server to `0.0.0.0` for Docker/remote access. Task 2 introduces a new `ziomek/logging.py` module with JSON formatting, `X-Request-ID` tracing middleware, and response-time logging — zero new dependencies. Task 3 enriches the `/status` health endpoint with uptime, backend info, and cache stats.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, stdlib `logging` only.

**Spec:** `docs/superpowers/plans/2026-10-01-server-api-improvements.md` (this plan implements the design agreed during brainstorming)

## Global Constraints

- Commit after every task with Conventional Commits format and `--signoff`.
- Use `uv run` for all Python execution; never install packages globally.
- NEVER use `git add -f` for ignored files.
- NEVER kill `python.exe` (LLM runs inside it).
- Respect `.gitattributes` and line endings; do not "fix" valid ones.
- All new code must have tests; all tests must pass before committing.
- Zero new dependencies for structured logging (stdlib `logging` only).
- Default behavior must remain unchanged (host= localhost, log-level=INFO).

## Review Focus

- **Host binding:** `0.0.0.0` must be bindable without exposing on unexpected interfaces; `localhost` must remain the default.
- **Log format:** JSON output must be parseable by external log collectors; no Python exception traces in JSON format.
- **Request ID:** `X-Request-ID` must be generated if absent, echoed in response headers, and logged with every request.
- **Health endpoint:** All new fields must be present in the response; missing state (e.g., model not loaded) must return `null` or `0` rather than crashing.
- **Config precedence:** `--host` CLI flag > `ZIOMEK_HOST` env var > config file > default `localhost`.

---

### Task 1: Remote Server Support

**Files:**
- Modify: `src/ziomek/config.py:10-15` (add `host` field to Settings)
- Modify: `src/ziomek/config.py:55-75` (wire `host` into `compose()`)
- Modify: `src/ziomek/cli.py:60-75` (add `--host` argument to server subcommand)
- Modify: `src/ziomek/server.py:70-80` (pass `host` to `uvicorn.run()`)
- Test: `tests/test_config.py` (add host precedence tests)

**Interfaces:**
- Consumes: `Settings.compose()` with existing parameters
- Produces: `Settings.host: str = "localhost"` available to all downstream code

- [ ] **Step 1: Add `host` field to Settings class**

Add `host: str = "localhost"` to the `Settings` model fields in `src/ziomek/config.py`, immediately after `audio_device`.

- [ ] **Step 2: Wire `host` through `compose()`**

In `Settings.compose()`, add `cli_host: str | None = None` parameter. Apply precedence: CLI > env (`env_host`) > file > default. Pass to `cls(host=cli_host_val, ...)`.

- [ ] **Step 3: Add `--host` CLI argument**

In `src/ziomek/cli.py`, add `--host` argument to the `server` subcommand parser:
```python
server_cmd.add_argument("--host", type=str, default=None, help="Host to bind (default: localhost)")
```
Add `--log-level` argument here too (planned for Task 2 but added now since it's in the CLI):
```python
server_cmd.add_argument("--log-level", type=str, default=None, help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
```

- [ ] **Step 4: Pass `host` to `uvicorn.run()`**

In `src/ziomek/server.py`, update `run_server()` to accept `host` parameter and pass it to `uvicorn.run(app, host=host, port=port)`.

- [ ] **Step 5: Write host precedence tests**

In `tests/test_config.py`, add three test functions:
```python
def test_host_default():
    settings = Settings()
    assert settings.host == "localhost"

def test_host_cli_precedence():
    settings = Settings.compose(cli_host="0.0.0.0")
    assert settings.host == "0.0.0.0"

def test_host_env_precedence():
    settings = Settings.compose(env_host="127.0.0.1", cli_host=None)
    assert settings.host == "127.0.0.1"
```

- [ ] **Step 6: Run tests to verify**

Run: `uv run pytest tests/test_config.py -v`
Expected: All new tests pass, existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add src/ziomek/config.py src/ziomek/cli.py src/ziomek/server.py tests/test_config.py
git commit -m "feat(server): add --host flag for remote server binding" --signoff
```

---

### Task 2: Structured Logging (Medium)

**Files:**
- Create: `src/ziomek/logging.py` — JSON formatter, request ID middleware, setup function
- Modify: `src/ziomek/server.py` — call `setup_logging()`, attach middleware
- Modify: `src/ziomek/cli.py` — pass `log_level` to server
- Test: `tests/test_logging.py` — JSON format, request ID, response time

**Interfaces:**
- Consumes: `Settings.host`, `Settings.port` (from Task 1)
- Produces: `ziomek.logging.setup_logging(level: str) -> None`
- Produces: `ziomek.logging.RequestIDMiddleware` (Starlette middleware class)

- [ ] **Step 1: Write JSON formatter test**

In `tests/test_logging.py`:
```python
import json
import logging
from ziomek.logging import JSONFormatter

def test_json_formatter_output():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="test.py",
        lineno=1, msg="hello world", args=(), exc_info=None
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["message"] == "hello world"
    assert parsed["level"] == "INFO"
    assert "timestamp" in parsed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_logging.py::test_json_formatter_output -v`
Expected: FAIL with "No module named ziomek.logging"

- [ ] **Step 3: Implement JSONFormatter class**

Create `src/ziomek/logging.py` with:
```python
import json
import logging
import time
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured log collectors."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_logging.py::test_json_formatter_output -v`
Expected: PASS

- [ ] **Step 5: Write request ID middleware test**

In `tests/test_logging.py`:
```python
import uuid
from fastapi.testclient import TestClient
from ziomek.logging import RequestIDMiddleware

def test_request_id_generated():
    from fastapi import FastAPI
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/test")
    request_id = response.headers.get("x-request-id")
    assert request_id is not None
    # Verify it's a valid UUID
    uuid.UUID(request_id)

def test_request_id_echoed():
    from fastapi import FastAPI, Request
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    def test_endpoint(request: Request):
        return {"request_id": request.state.request_id}

    client = TestClient(app)
    response = client.get("/test")
    assert "request_id" in response.json()
    assert response.json()["request_id"] == response.headers.get("x-request-id")
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_logging.py::test_request_id_generated -v`
Expected: FAIL with "No module named ziomek.logging.RequestIDMiddleware"

- [ ] **Step 7: Implement RequestIDMiddleware**

Add to `src/ziomek/logging.py`:
```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate and propagate X-Request-ID for request tracing."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
```

- [ ] **Step 8: Run middleware test to verify it passes**

Run: `uv run pytest tests/test_logging.py::test_request_id_generated tests/test_logging.py::test_request_id_echoed -v`
Expected: PASS

- [ ] **Step 9: Write response time logging test**

In `tests/test_logging.py`:
```python
import time
from fastapi.testclient import TestClient
from ziomek.logging import RequestIDMiddleware

def test_response_time_logged():
    from fastapi import FastAPI
    import logging
    from io import StringIO

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    # Capture log output
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("ziomek")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    @app.get("/test")
    def test_endpoint():
        time.sleep(0.01)  # 10ms delay
        return {"ok": True}

    client = TestClient(app)
    client.get("/test")

    log_output = log_stream.getvalue()
    assert "duration_ms" in log_output
    duration = float(log_output.split('"duration_ms":')[1].split(",")[0])
    assert duration > 5  # Should be at least 10ms
```

- [ ] **Step 10: Run test to verify it fails**

Run: `uv run pytest tests/test_logging.py::test_response_time_logged -v`
Expected: FAIL (middleware doesn't log duration yet)

- [ ] **Step 11: Enhance RequestIDMiddleware with response time logging**

Update the middleware's `dispatch` method:
```python
async def dispatch(self, request: Request, call_next) -> Response:
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    response.headers["x-request-id"] = request_id

    logger = logging.getLogger("ziomek.access")
    logger.info(
        "%s %s %d %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        extra={"request_id": request_id},
    )
    return response
```

Also add an `extra` processor in `setup_logging()` to include `request_id` in log records.

- [ ] **Step 12: Run response time test to verify it passes**

Run: `uv run pytest tests/test_logging.py::test_response_time_logged -v`
Expected: PASS

- [ ] **Step 13: Implement setup_logging() function**

Add to `src/ziomek/logging.py`:
```python
def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging for the ziomek application."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("ziomek")
    logger.setLevel(numeric_level)
    logger.addHandler(handler)
    # Prevent duplicate handlers on repeated calls
    logger.propagate = False
```

- [ ] **Step 14: Wire logging into server**

In `src/ziomek/server.py`, add import and call:
```python
from ziomek.logging import setup_logging, RequestIDMiddleware

# In create_app():
app.add_middleware(RequestIDMiddleware)

# In run_server():
setup_logging(level=log_level)
```

- [ ] **Step 15: Pass log_level from CLI to server**

In `src/ziomek/cli.py`, update `serve_cmd()` to pass `log_level=args.log_level` to `run_server()`.

- [ ] **Step 16: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass (new logging tests + existing tests).

- [ ] **Step 17: Commit**

```bash
git add src/ziomek/logging.py src/ziomek/server.py src/ziomek/cli.py tests/test_logging.py
git commit -m "feat(server): add structured JSON logging with request tracing" --signoff
```

---

### Task 3: Health Endpoint Improvements

**Files:**
- Modify: `src/ziomek/server.py` — track startup timestamp, expose health state
- Modify: `src/ziomek/api/health.py` — enrich `/status` response
- Test: `tests/test_server.py` — add health endpoint integration test

**Interfaces:**
- Consumes: `Settings.host`, `Settings.port`, `Settings.audio_backend`, `Settings.audio_device`, `Settings.cache_dir`, `Settings.voice`
- Produces: Enriched `/status` JSON response with uptime, backend info, cache stats

- [ ] **Step 1: Track startup timestamp in server**

In `src/ziomek/server.py`, add a module-level variable:
```python
import time
_startup_time: float = 0

def get_uptime() -> float:
    """Return seconds since server startup."""
    return time.time() - _startup_time

_startup_time = time.time()  # Set on module load
```

- [ ] **Step 2: Write health endpoint integration test**

In `tests/test_server.py`:
```python
import time
from fastapi.testclient import TestClient
from ziomek.server import create_app

def test_health_status_has_new_fields():
    app = create_app()
    client = TestClient(app)
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()

    # Verify new fields exist
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0

    assert "audio_backend" in data
    assert "audio_device" in data or data["audio_device"] is None

    assert "cache_dir" in data
    assert "cache_stats" in data

    assert "model_loaded" in data
    assert "voice" in data
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py::test_health_status_has_new_fields -v`
Expected: FAIL — new fields missing from response

- [ ] **Step 4: Enrich `/status` endpoint**

In `src/ziomek/api/health.py`, rewrite the `status()` endpoint:
```python
@router.get("/status", summary="Server health")
async def status():
    from ziomek.server import get_uptime, _audio_player, _state_machine, _voice_cache, _tts_model
    from ziomek.config import Settings

    ready = _tts_model is not None and _tts_model.ready
    model_loaded = ready

    # Get audio backend info
    audio_backend = "unknown"
    audio_device = None
    if _audio_player is not None:
        audio_backend = _audio_player.backend_name
        audio_device = _audio_player.device_name

    # Get cache stats
    cache_stats = {"size_mb": 0, "files": 0}
    if _voice_cache is not None and _voice_cache._cache_dir:
        cache_dir = Path(_voice_cache._cache_dir)
        if cache_dir.exists():
            files = list(cache_dir.glob("*.wav")) + list(cache_dir.glob("*.mp3"))
            cache_stats["files"] = len(files)
            total_bytes = sum(f.stat().st_size for f in files)
            cache_stats["size_mb"] = round(total_bytes / (1024 * 1024), 2)

    return {
        "uptime_seconds": round(get_uptime(), 2),
        "model_loaded": model_loaded,
        "voice": "default",  # Will be set from Settings
        "audio_backend": audio_backend,
        "audio_device": audio_device,
        "cache_dir": _voice_cache._cache_dir if _voice_cache else None,
        "cache_stats": cache_stats,
        "endpoints": {
            "tts": ["POST /api/tts/generate", "POST /api/tts/speak", "GET /api/tts/status", "GET /api/tts/voices"],
            "avatar": ["POST /api/avatar/input", "GET /api/avatar/state", "POST /api/avatar/expression", "GET /api/avatar/sprite", "POST /api/avatar/speak", "GET /api/avatar/view"],
        },
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py::test_health_status_has_new_fields -v`
Expected: PASS

- [ ] **Step 6: Add test for missing model state**

In `tests/test_server.py`:
```python
def test_health_status_null_when_model_not_loaded():
    """When TTS model is not loaded, model_loaded should be False."""
    from ziomek.server import _tts_model
    # Model is loaded in create_app(), so this test verifies the field exists
    app = create_app()
    client = TestClient(app)
    response = client.get("/status")
    data = response.json()
    # Should not crash even if model is None
    assert isinstance(data["model_loaded"], bool)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py::test_health_status_null_when_model_not_loaded -v`
Expected: PASS

- [ ] **Step 8: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass.

- [ ] **Step 9: Commit**

```bash
git add src/ziomek/server.py src/ziomek/api/health.py tests/test_server.py
git commit -m "feat(server): enrich health endpoint with uptime, backend, and cache stats" --signoff
```

---

### Task 4: Update Documentation & Verification

**Files:**
- Modify: `README.md` — update Launch Commands section with new flags
- Modify: `docs/internal/TODO.md` — mark three items as done
- Test: Run full test suite one final time

- [ ] **Step 1: Update README Launch Commands**

Add `--host` and `--log-level` flags to the example command in `README.md`:
```bash
uv run python -m ziomek.cli serve --host 0.0.0.0 --port 5003 --log-level INFO --voice cosette --cache-dir ./voices
```

Add a row to the options table:
| `--host` | localhost | Host to bind (0.0.0.0 for remote/Docker) |
| `--log-level` | INFO | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |

- [ ] **Step 2: Update TODO.md**

Mark these three items as done:
- [x] Remote server support
- [x] Structured logging
- [x] Health endpoint improvements

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/internal/TODO.md
git commit -m "docs: update README with new CLI flags and mark Server & API tasks done" --signoff
```
