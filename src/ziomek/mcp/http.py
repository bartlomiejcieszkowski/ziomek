"""ziomek MCP server — HTTP transport (SSE + JSON-RPC).

Provides MCP JSON-RPC over HTTP POST with SSE for server→client streaming.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse


def _create_mcp_server(expose_full_config: bool = False):
    """Create an MCP server instance with tools and resources registered."""
    from mcp.server.lowlevel import Server

    from .resources import register_resources
    from .tools import register_tools

    mcp_server = Server("ziomek-mcp")
    register_tools(mcp_server)
    register_resources(mcp_server, expose_full_config)
    return mcp_server


def _sse_event(event: str, data: str, event_id: str | None = None) -> str:
    """Format an SSE event."""
    lines: list[str] = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {data}")
    lines.append("\n\n")
    return "".join(lines)


async def _mcp_sse_generator(client_id: str, initialized: bool):
    """SSE generator for MCP server→client messages."""
    # Store client state
    if not hasattr(_mcp_sse_clients, "__getitem__"):
        # Initialize storage
        pass
    # Get or create client queue
    if not hasattr(_mcp_sse_clients, "get"):
        _mcp_sse_clients.clear()
    if client_id not in _mcp_sse_clients:
        _mcp_sse_clients[client_id] = []

    # Send initial event
    yield _sse_event("connected", json.dumps({"client_id": client_id}))

    # Stream messages
    while client_id in _mcp_sse_clients and _mcp_sse_clients[client_id] is not None:
        messages = _mcp_sse_clients.pop(client_id, [])
        for msg in messages:
            yield _sse_event("message", json.dumps(msg))
        await asyncio.sleep(0.1)

    # Client disconnected
    if client_id in _mcp_sse_clients:
        del _mcp_sse_clients[client_id]


# Global SSE client storage
_mcp_sse_clients: dict[str, list[dict[str, Any]] | None] = {}
_mcp_initialized: dict[str, bool] = {}


def _send_to_client(client_id: str, message: dict[str, Any]) -> None:
    """Send a message to an SSE client."""
    if client_id in _mcp_sse_clients and _mcp_sse_clients[client_id] is not None:
        _mcp_sse_clients[client_id].append(message)


def register_mcp_http_routes(app: FastAPI, expose_full_config: bool = False) -> None:
    """Register MCP HTTP routes on the FastAPI app."""
    import asyncio

    mcp_server = _create_mcp_server(expose_full_config)

    # ── SSE endpoint for server→client streaming ──
    @app.get("/mcp/sse")
    async def mcp_sse() -> StreamingResponse:
        client_id = str(uuid.uuid4())
        _mcp_sse_clients[client_id] = []
        _mcp_initialized[client_id] = False

        async def stream():
            try:
                async for event in mcp_server.create_sse_message(
                    client_id,
                    mcp_server.create_initialization_options(),
                ):
                    yield _sse_event("message", json.dumps(event), str(uuid.uuid4()))
            except asyncio.CancelledError:
                pass
            finally:
                if client_id in _mcp_sse_clients:
                    _mcp_sse_clients[client_id] = None
                if client_id in _mcp_initialized:
                    del _mcp_initialized[client_id]

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ── JSON-RPC POST endpoint ──
    @app.post("/mcp/message")
    async def mcp_message(request: Request) -> Response:
        body = await request.json()
        client_id = request.headers.get("x-mcp-client-id", "default")

        # Initialize client
        if body.get("method") == "initialize":
            _mcp_initialized[client_id] = True
            result = await mcp_server.handle_initialize(body)
            return Response(content=json.dumps(result), media_type="application/json")

        if not _mcp_initialized.get(client_id, False):
            return Response(
                content=json.dumps({"jsonrpc": "2.0", "error": {"code": -32000, "message": "Not initialized"}, "id": None}),
                status_code=400,
                media_type="application/json",
            )

        # Handle other requests
        result = await mcp_server.handle_message(body, client_id)
        if result:
            if isinstance(result, dict):
                return Response(content=json.dumps(result), media_type="application/json")
            elif isinstance(result, list):
                return Response(content=json.dumps(result), media_type="application/json")
        return Response(status_code=204)

    # ── Health check ──
    @app.get("/mcp/health")
    async def mcp_health() -> dict[str, Any]:
        return {
            "status": "ok",
            "transport": "http",
            "endpoints": {
                "sse": "/mcp/sse",
                "message": "/mcp/message",
            },
        }

    # ── MCP client HTML page ──
    @app.get("/mcp")
    async def mcp_page() -> HTMLResponse:
        return HTMLResponse(
            content="""<!DOCTYPE html>
<html>
<head><title>ziomek MCP</title></head>
<body>
<h1>ziomek MCP Server</h1>
<p>Transport: HTTP (SSE + JSON-RPC)</p>
<ul>
    <li>SSE: <code>/mcp/sse</code></li>
    <li>Message: <code>POST /mcp/message</code></li>
    <li>Health: <code>GET /mcp/health</code></li>
</ul>
<script>
const ws = new EventSource('/mcp/sse');
ws.onmessage = (event) => {
    console.log('MCP:', event.data);
    document.body.innerHTML += '<pre>' + event.data + '</pre>';
};
ws.onerror = () => console.error('MCP SSE error');
</script>
</body>
</html>""",
            media_type="text/html",
        )
