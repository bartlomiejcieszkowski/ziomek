"""Probe: full MCP handshake through /mcp and the legacy aliases.

Session manager must be run by the parent app's lifespan; alias rewriting has to
match the *full* request path, because Mount strips the /mcp prefix before the
inner app sees it (path_info becomes '/sse', not '/mcp/sse').
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server import Server

from ziomek.mcp.resources import _on_list_resources, _on_read_resource
from ziomek.mcp.tools import _on_call_tool, _on_list_tools

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}},
}
LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
HEADERS = {"Accept": "application/json, text/event-stream"}
ALIASES = ("/mcp/sse", "/mcp/message")
CANONICAL = "/"


def build_app():
    srv = Server(
        name="ziomek",
        version="0.3.0",
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
        on_list_resources=_on_list_resources,
        on_read_resource=_on_read_resource,
    )
    inner = srv.streamable_http_app(streamable_http_path=CANONICAL)

    def wrapped(scope, receive, send):
        if scope["type"] == "http" and scope.get("path") in ALIASES:
            scope = {**scope, "path_info": CANONICAL}
        return inner(scope, receive, send)

    app = FastAPI()

    @asynccontextmanager
    async def lifespan(app):
        async with srv.session_manager.run():
            yield

    app.router.lifespan_context = lifespan
    app.mount("/mcp", wrapped)
    return app


def probe_path(client, path):
    r = client.post(path, json=INIT, headers=HEADERS)
    print(f"POST {path} initialize -> {r.status_code} {r.text[:160]}")
    session = r.headers.get("mcp-session-id")
    if not session:
        return
    r = client.post(path, json=LIST, headers={**HEADERS, "Mcp-Session-Id": session})
    text = r.text[:160]
    print(f"POST {path} tools/list -> {r.status_code} {text}")


def main():
    app = build_app()
    with TestClient(app, base_url="http://localhost:5004") as c:
        for path in ("/mcp", "/mcp/sse", "/mcp/message"):
            probe_path(c, path)


if __name__ == "__main__":
    main()
