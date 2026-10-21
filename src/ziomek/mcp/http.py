"""ziomek MCP server - HTTP transport using streamable_http_app."""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import Server
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route

from .resources import RESOURCES, _on_list_resources, _on_read_resource
from .tools import TOOLS, _on_call_tool, _on_list_tools

logger = logging.getLogger(__name__)

# Global server reference
_mcp_server: Server | None = None
_mcp_http_app: Any = None


def get_mcp_server() -> Server | None:
    """Get the MCP server instance (for testing)."""
    return _mcp_server


def _get_mcp_http_app() -> Any:
    """Get the MCP HTTP app (for SSE passthrough)."""
    return _mcp_http_app


def register_mcp_http_routes(app: Any, expose_full_config: bool = False) -> None:
    """Register MCP HTTP routes on a FastAPI app.

    Uses MCP SDK's built-in streamable_http_app() for SSE + JSON-RPC transport.
    Adds custom health/info endpoints at /mcp path.
    """
    global _mcp_server

    from ziomek.mcp import set_expose_full_config

    # Set the config exposure flag before creating the server
    set_expose_full_config(expose_full_config)

    _mcp_server = Server(
        name="ziomek",
        version="0.2.0",
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
        on_list_resources=_on_list_resources,
        on_read_resource=_on_read_resource,
    )

    # Get the built-in HTTP app from MCP SDK
    mcp_http_app = _mcp_server.streamable_http_app(streamable_http_path="/mcp")

    # Store globally for SSE passthrough
    global _mcp_http_app
    _mcp_http_app = mcp_http_app

    # Health endpoint (GET only)
    app.add_route("/mcp/health", mcp_health, methods=["GET"])

    # Info page (GET only)
    app.add_route("/mcp", mcp_page, methods=["GET"])

    # SSE passthrough (GET with Accept: text/event-stream)
    app.add_route("/mcp/sse", mcp_sse, methods=["GET"])

    # Mount the MCP HTTP app as catch-all for /mcp/* and POST /mcp
    app.mount("/mcp", mcp_http_app)


async def mcp_health(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({
        "status": "ok",
        "transport": "http",
        "endpoints": {
            "sse": "/mcp/sse",
            "message": "/mcp/message",
        },
    })


async def mcp_page(request: Request) -> HTMLResponse:
    """MCP server info page."""
    return HTMLResponse(
        "<html><head><title>ziomek MCP</title></head>"
        "<body><h1>ziomek MCP Server</h1>"
        "<p>Transport: HTTP (streamable)</p>"
        "<ul>"
        "<li><a href='/mcp/health'>Health</a></li>"
        "<li><a href='/mcp/sse'>SSE</a></li>"
        "</ul></body></html>",
    )


async def mcp_sse(request: Request) -> Any:
    """SSE stream passthrough to MCP SDK."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/mcp",
        "path_info": "/mcp",
        "query_string": request.url.query.encode(),
        "headers": [(k.lower(), v if isinstance(v, bytes) else v.encode()) for k, v in request.headers.raw],
    }

    async def receive():
        return {"type": "http.request", "body": b""}

    body_chunks: list[bytes] = []

    async def send(message):
        if message["type"] == "http.response.body":
            body_chunks.append(message.get("body", b""))

    app = _get_mcp_http_app()
    if app:
        await app(scope, receive, send)

    from starlette.responses import StreamingResponse

    async def stream():
        for chunk in body_chunks:
            yield chunk

    return StreamingResponse(stream(), media_type="text/event-stream")


def start_mcp_http_server(host: str = "localhost", port: int = 5005) -> None:
    """Run the MCP server over HTTP transport.

    Uses uvicorn to serve the streamable_http_app.
    """
    import uvicorn

    app = create_http_app()
    logger.info(f"Starting ziomek MCP server (HTTP transport on {host}:{port})")
    uvicorn.run(app, host=host, port=port)


def create_http_app() -> Any:
    """Create a standalone FastAPI/Starlette app with MCP HTTP routes."""
    global _mcp_server

    from ziomek.mcp import set_expose_full_config

    set_expose_full_config(False)

    _mcp_server = Server(
        name="ziomek",
        version="0.2.0",
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
        on_list_resources=_on_list_resources,
        on_read_resource=_on_read_resource,
    )

    # Get the built-in HTTP app from MCP SDK
    http_app = _mcp_server.streamable_http_app(streamable_http_path="/mcp")

    return http_app


if __name__ == "__main__":
    start_mcp_http_server()
