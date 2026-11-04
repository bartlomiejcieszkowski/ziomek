"""ziomek MCP server - stdio transport."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server

from .resources import RESOURCES, _on_list_resources, _on_read_resource
from .tools import TOOLS, _on_call_tool, _on_list_tools

logger = logging.getLogger(__name__)

# Global server reference
_mcp_server: Server | None = None

# Config exposure flag (set by server.py before calling start_mcp_server)
_expose_full_config: bool = False

# Dev mode is one flag, read by the paths that answer only in it: the debug paths and the page that
# states values. A page that posts values is served only where something can read them back.
from ziomek.dev_mode import get_dev_mode, set_dev_mode


def set_expose_full_config(expose: bool) -> None:
    """Set whether full config should be exposed in resources."""
    global _expose_full_config
    _expose_full_config = expose


def get_expose_full_config() -> bool:
    """Get the current config exposure setting."""
    return _expose_full_config


async def start_mcp_server(expose_full_config: bool = False, dev_mode: bool = False) -> None:
    """Run the MCP server over stdio transport.

    This is the main entry point for MCP clients connecting via stdio.
    The server runs until interrupted (Ctrl+C or SIGTERM).
    """
    global _mcp_server

    # Set the flags before creating the server
    set_expose_full_config(expose_full_config)
    set_dev_mode(dev_mode)

    _mcp_server = Server(
        name="ziomek",
        version="0.2.0",
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
        on_list_resources=_on_list_resources,
        on_read_resource=_on_read_resource,
    )

    logger.info("Starting ziomek MCP server (stdio transport)")

    async with stdio_server() as (read_stream, write_stream):
        await _mcp_server.run(
            read_stream,
            write_stream,
            _mcp_server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(start_mcp_server())
