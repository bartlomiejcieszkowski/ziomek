"""ziomek structured logging — JSON formatter, request tracing, response times."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured log collectors."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, object] = {
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


class _LogRingBuffer(logging.Handler):
    """A logging handler that keeps the last N log entries in memory."""

    def __init__(self, maxlen: int = 200) -> None:
        super().__init__()
        self._buffer: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._formatter = logging.Formatter()

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self._formatter.formatException(record.exc_info)
        self._buffer.append(entry)

    def get_entries(self) -> list[dict[str, Any]]:
        return list(self._buffer)

    def clear(self) -> None:
        self._buffer.clear()


# Global log buffer singleton
_log_buffer: _LogRingBuffer | None = None


def get_log_buffer() -> _LogRingBuffer:
    """Return the global log ring buffer, creating it if needed."""
    global _log_buffer
    if _log_buffer is None:
        _log_buffer = _LogRingBuffer()
    return _log_buffer


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate and propagate X-Request-ID for request tracing."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
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


def setup_logging(level: str = "INFO", enable_buffer: bool = False, log_file: str | None = None) -> None:
    """Configure structured logging for the ziomek application.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        enable_buffer: If True, attach a ring buffer handler for debug endpoints.
        log_file: Optional file path for JSON log output. Stdout uses colored text.
    """
    from uvicorn.logging import ColourizedFormatter
    
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Stdout: colored format (like uvicorn)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(ColourizedFormatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger = logging.getLogger("ziomek")
    logger.setLevel(numeric_level)
    logger.addHandler(stdout_handler)
    logger.propagate = False
    
    # Log file: JSON format (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)
    
    # Configure uvicorn to use colored format on stdout too
    for uvicorn_logger in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        uv_logger = logging.getLogger(uvicorn_logger)
        uv_logger.handlers.clear()
        uv_handler = logging.StreamHandler(sys.stdout)
        uv_handler.setFormatter(ColourizedFormatter(
            "%(message)s",
        ))
        uv_logger.addHandler(uv_handler)
        uv_logger.propagate = False
    
    if enable_buffer:
        buf = _LogRingBuffer()
        buf.setLevel(logging.DEBUG)
        buf.setFormatter(JSONFormatter())
        logger.addHandler(buf)
