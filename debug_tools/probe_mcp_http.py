from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server import Server

from ziomek.mcp.resources import _on_list_resources, _on_read_resource
from ziomek.mcp.tools import _on_call_tool, _on_list_tools

BODY = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
HEADERS = {"Accept": "application/json, text/event-stream"}


def probe(mount_prefix: str, internal_path: str) -> None:
    app = FastAPI()
    srv = Server(
        name="ziomek",
        version="0.3.0",
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
        on_list_resources=_on_list_resources,
        on_read_resource=_on_read_resource,
    )
    app.mount(mount_prefix, srv.streamable_http_app(streamable_http_path=internal_path))
    with TestClient(app) as c:
        for path in (mount_prefix, mount_prefix + "/"):
            r = c.post(path, json=BODY, headers=HEADERS)
            print(f"mount={mount_prefix} internal={internal_path} POST {path} -> {r.status_code} {r.text[:200]}")


if __name__ == "__main__":
    probe("/mcp", "/")
    probe("/mcp", "/mcp")
    probe("/", "/mcp")
