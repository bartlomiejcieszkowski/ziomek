"""ziomek MCP server - HTTP transport routes served by the streamable HTTP session manager."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp, StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import BaseRoute, Route

from ziomek import __version__

from .resources import RESOURCES, _on_list_resources, _on_read_resource
from .tools import TOOLS, _on_call_tool, _on_list_tools

logger = logging.getLogger(__name__)

MCP_PATH = "/mcp"
# Kept so clients that still use the two-endpoint SSE style keep working. The handler is
# path-agnostic, so these aliases reach the same session manager as the canonical path.
MCP_ALIAS_PATHS = ("/mcp/sse", "/mcp/message")

# Global server reference
_mcp_server: Server | None = None
_session_manager: StreamableHTTPSessionManager | None = None


def get_mcp_server() -> Server | None:
    """Get the MCP server instance (for testing)."""
    return _mcp_server


def get_session_manager() -> StreamableHTTPSessionManager | None:
    """Get the session manager built by the last server creation."""
    return _session_manager


def _build_session_manager(expose_full_config: bool = False) -> StreamableHTTPSessionManager:
    """Create the MCP server and the session manager that serves it."""
    global _mcp_server, _session_manager

    from ziomek.mcp import set_expose_full_config

    # Set the config exposure flag before creating the server
    set_expose_full_config(expose_full_config)

    _mcp_server = Server(
        name="ziomek",
        version=__version__,
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
        on_list_resources=_on_list_resources,
        on_read_resource=_on_read_resource,
    )

    _session_manager = StreamableHTTPSessionManager(app=_mcp_server)
    return _session_manager


def _mcp_routes(manager: StreamableHTTPSessionManager) -> list[BaseRoute]:
    """Routes for the JSON-RPC handler, the compatibility aliases, health and info page.

    The handler is wrapped in an ASGI callable: Starlette treats a bound method as a
    `func(request)` endpoint and would reject POST with 405.
    """
    handler = StreamableHTTPASGIApp(manager)
    routes: list[BaseRoute] = [Route(MCP_PATH, handler)]
    for alias in MCP_ALIAS_PATHS:
        routes.append(Route(alias, handler))
    routes.append(Route("/mcp/health", mcp_health, methods=["GET"]))
    routes.append(Route("/mcp/info", mcp_info_page, methods=["GET"]))
    return routes


def _run_session_manager(app: Any, manager: StreamableHTTPSessionManager) -> None:
    """Wrap the app lifespan so the session manager's task group is started."""
    inner = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app: Any) -> AsyncIterator[None]:
        async with inner(app):
            # handle_request raises "Task group is not initialized" unless run() is active.
            async with manager.run():
                yield

    app.router.lifespan_context = lifespan


def register_mcp_http_routes(app: Any, expose_full_config: bool = False) -> None:
    """Register MCP HTTP routes on a FastAPI app and run the session manager."""
    manager = _build_session_manager(expose_full_config)
    app.router.routes.extend(_mcp_routes(manager))
    _run_session_manager(app, manager)


def create_http_app(expose_full_config: bool = False) -> Any:
    """Create a standalone app with MCP HTTP routes."""
    manager = _build_session_manager(expose_full_config)
    app = Starlette(routes=_mcp_routes(manager))
    _run_session_manager(app, manager)
    return app


async def mcp_health(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(
        {
            "status": "ok",
            "transport": "http",
            "endpoints": {
                "mcp": MCP_PATH,
                "sse": MCP_ALIAS_PATHS[0],
                "message": MCP_ALIAS_PATHS[1],
            },
        }
    )


async def mcp_info_page(request: Request) -> HTMLResponse:
    """MCP server info page."""
    aliases = "".join(f"<li><a href='{alias}'>{alias}</a></li>" for alias in MCP_ALIAS_PATHS)
    return HTMLResponse(
        "<html><head><title>ziomek MCP</title></head>"
        "<body><h1>ziomek MCP Server</h1>"
        "<p>Transport: HTTP (streamable)</p>"
        f"<p>JSON-RPC endpoint: <a href='{MCP_PATH}'>{MCP_PATH}</a></p>"
        f"<ul><li><a href='/mcp/health'>Health</a></li>{aliases}</ul></body></html>",
    )


def start_mcp_http_server(host: str = "localhost", port: int = 5005) -> None:
    """Run the MCP server over HTTP transport.

    Uses uvicorn to serve the MCP HTTP routes.
    """
    import uvicorn

    app = create_http_app()
    logger.info(f"Starting ziomek MCP server (HTTP transport on {host}:{port})")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_mcp_http_server()
