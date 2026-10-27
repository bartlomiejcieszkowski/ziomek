"""Tests for ziomek structured logging."""

import json
import logging
import time
import uuid
from io import StringIO

from fastapi.testclient import TestClient


def test_json_formatter_output():
    """JSON formatter should produce parseable JSON with required fields."""
    from ziomek.logging import JSONFormatter

    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["message"] == "hello world"
    assert parsed["level"] == "INFO"
    assert "timestamp" in parsed


def test_json_formatter_with_exception():
    """JSON formatter should include exception info when present."""
    from ziomek.logging import JSONFormatter

    formatter = JSONFormatter()
    import sys

    try:
        raise ValueError("test error")
    except ValueError:
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="exception occurred",
            args=(),
            exc_info=sys.exc_info(),
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "test error" in parsed["exception"]


def test_request_id_generated():
    """Middleware should generate X-Request-ID when absent."""
    from fastapi import FastAPI

    from ziomek.logging import RequestIDMiddleware

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
    """Middleware should echo X-Request-ID in response headers."""
    from fastapi import FastAPI, Request

    from ziomek.logging import RequestIDMiddleware

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    def test_endpoint(request: Request):
        return {"request_id": request.state.request_id}

    client = TestClient(app)
    response = client.get("/test")
    assert "request_id" in response.json()
    assert response.json()["request_id"] == response.headers.get("x-request-id")


def test_response_time_logged():
    """Middleware should log response time in milliseconds."""
    from fastapi import FastAPI

    from ziomek.logging import JSONFormatter, RequestIDMiddleware

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    # Capture log output
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("ziomek.access")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    @app.get("/test")
    def test_endpoint():
        time.sleep(0.01)  # 10ms delay
        return {"ok": True}

    client = TestClient(app)
    client.get("/test")

    log_output = log_stream.getvalue()
    # Log format: "GET /test 200 17.88ms"
    assert "ms" in log_output


def test_setup_logging_configures_handler():
    """setup_logging should configure the root logger."""
    # Reset any existing handlers
    import logging

    from ziomek.logging import setup_logging

    root_logger = logging.getLogger("ziomek")
    root_logger.handlers.clear()

    setup_logging(level="DEBUG")
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) > 0
