"""ziomek MCP server — HTTP transport using streamable_http_app."""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import Server

from .resources import RESOURCES, _on_list_resources, _on_read_resource
from .tools import TOOLS, _on_call_tool, _on_list_tools

logger = logging.getLogger(__name__)

# Global server reference
_mcp_server: Server | None = None


def get_mcp_server() -> Server | None:
    """Get the MCP server instance (for testing)."""
    return _mcp_server


def create_http_app() -> Any:
    """Create a FastAPI/Starlette app with MCP HTTP routes.

    Uses MCP SDK's built-in streamable_http_app() for SSE + JSON-RPC transport.
    Mounts at /mcp path.
    """
    global _mcp_server

    _mcp_server = Server(
        name="ziomek",
        version="0.2.0",
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
        on_list_resources=_on_list_resources,
        on_read_resource=_on_read_resource,
    )

    # Get the built-in HTTP app from MCP SDK
    http_app = _mcp_server.streamable_http_app("/mcp")

    return http_app


async def start_mcp_http_server(host: str = "localhost", port: int = 5005) -> None:
    """Run the MCP server over HTTP transport.

    Uses uvicorn to serve the streamable_http_app.
    """
    import uvicorn

    app = create_http_app()
    logger.info(f"Starting ziomek MCP server (HTTP transport on {host}:{port})")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import asyncio

    asyncio.run(start_mcp_http_server())
