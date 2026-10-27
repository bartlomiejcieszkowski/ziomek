"""Probe: does the MCP HTTP endpoint work when its session manager lifespan runs?

Tests mount layout + alias rewriting, since the current code fails both
(path conflict at /mcp, and 'Task group is not initialized').
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server import Server

from ziomek.mcp.resources import _on_list_resources, _on_read_resource
from ziomek.mcp.tools import _on_call_tool, _on_list_tools

BODY = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
HEADERS = {"Accept": "application/json, text/event-stream"}
ALIASES = ("/mcp/sse", "/mcp/message")


def build_app(mount_prefix: str, internal_path: str, rewrite_aliases: bool):
    srv = Server(
        name="ziomek",
        version="0.3.0",
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
        on_list_resources=_on_list_resources,
        on_read_resource=_on_read_resource,
    )
    inner = srv.streamable_http_app(streamable_http_path=internal_path)

    def wrapped(scope, receive, send):
        if scope["type"] == "http" and rewrite_aliases:
            path = scope.get("path_info") or scope.get("path") or ""
            if path in ALIASES:
                scope = {**scope, "path": internal_path, "path_info": internal_path}
        return inner(scope, receive, send)

    app = FastAPI()
    inner_lifespan = inner.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        async with inner_lifespan(inner):
            yield

    app.router.lifespan_context = lifespan
    app.mount(mount_prefix, wrapped)
    return app


def main():
    for mount_prefix, internal_path in (("/mcp", "/"), ("/", "/mcp")):
        print(f"--- mount={mount_prefix} internal={internal_path}")
        for rewrite in (False, True):
            app = build_app(mount_prefix, internal_path, rewrite)
            with TestClient(app) as c:
                for path in (mount_prefix, mount_prefix + "/", "/mcp/sse", "/mcp/message"):
                    r = c.post(path, json=BODY, headers=HEADERS)
                    print(f"  rewrite={rewrite} POST {path} -> {r.status_code} {r.text[:120]}")


if __name__ == "__main__":
    main()
