"""ziomek MCP server — embedded alongside FastAPI HTTP server."""

from __future__ import annotations


def start_mcp_server(expose_full_config: bool = False) -> None:
    """Start the MCP server (runs in a separate thread)."""
    import asyncio

    from mcp.server.lowlevel import Server

    from .resources import register_resources
    from .tools import register_tools

    mcp_server = Server("ziomek-mcp")
    register_tools(mcp_server)
    register_resources(mcp_server, expose_full_config)

    async def _run():
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    asyncio.run(_run())


def get_mcp_server(expose_full_config: bool = False):
    """Get the MCP server instance (for testing)."""
    from mcp.server.lowlevel import Server

    from .resources import register_resources
    from .tools import register_tools

    mcp_server = Server("ziomek-mcp")
    register_tools(mcp_server)
    register_resources(mcp_server, expose_full_config)
    return mcp_server
