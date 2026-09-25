"""ziomek client — FastAPI server for avatar display and WebSocket relay.

Serves the HTML avatar renderer, relays gamepad state to extension via
WebSocket, and proxies sprite data from the TTS server.
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from ziomek.avatar.state_machine import AvatarStateMachine, AvatarInput, ExpressionState
from ziomek.client.gamepad import GamepadManager, GamepadState


class ZiomekClientApp:
    """ziomek client — gamepad polling + state machine + HTTP server."""

    def __init__(
        self,
        server_url: str = "http://localhost:5003",
        port: int = 5004,
        open_browser: bool = True,
    ) -> None:
        self._server_url = server_url
        self._port = port
        self._open_browser = open_browser
        self._gamepad_manager = GamepadManager()
        self._state_machine = AvatarStateMachine()
        self._last_expr = ""
        self._last_cycle = -1
        self._sprite_data: Optional[str] = None
        self._sprite_width = 0
        self._sprite_height = 0
        self._frame_width = 0
        self._frame_height = 0
        self._app: Optional[FastAPI] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._create_app()
        self._start_gamepad_thread()
        self._fetch_sprite()

        if self._open_browser:
            self._open_local_browser()

        uvicorn.run(self._app, host="127.0.0.1", port=self._port)

    def _create_app(self) -> None:
        self._app = FastAPI(title="ziomek client")
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @self._app.get("/avatar-view")
        async def avatar_view() -> HTMLResponse:
            html_path = Path(__file__).parent / "renderer.html"
            return HTMLResponse(content=html_path.read_text())

        @self._app.websocket("/avatar")
        async def avatar_ws(websocket: WebSocket) -> None:
            await websocket.accept()
            try:
                while True:
                    state = self._state_machine.tick(16)
                    if (
                        state.expressionName != self._last_expr
                        or state.cycleIndex != self._last_cycle
                    ):
                        msg = {
                            "expression": state.expressionName,
                            "cycleIndex": state.cycleIndex,
                        }
                        await websocket.send_json(msg)
                        self._last_expr = state.expressionName
                        self._last_cycle = state.cycleIndex
                    await asyncio.sleep(0.01)
            except Exception:
                pass

        @self._app.get("/avatar/sprite")
        async def avatar_sprite() -> dict:
            if self._sprite_data is None:
                return JSONResponse(
                    status_code=503, content={"error": "Sprite not loaded"}
                )
            return {
                "sprite_b64": self._sprite_data,
                "width": self._sprite_width,
                "height": self._sprite_height,
                "frameWidth": self._frame_width,
                "frameHeight": self._frame_height,
            }

        @self._app.get("/avatar/state")
        async def avatar_state() -> dict:
            state = self._state_machine.tick(16)
            return {
                "expression": state.expressionName,
                "cycleIndex": state.cycleIndex,
            }

        @self._app.post("/avatar/input")
        async def avatar_input(request: Request) -> dict:
            body = await request.json()
            inp = AvatarInput(
                buttons=body.get("buttons", []),
                axes=body.get("axes", [0.0] * 4),
                connected=body.get("connected", False),
                streaming=body.get("streaming", False),
                chatFocused=body.get("chatFocused", False),
                errorState=body.get("errorState", False),
            )
            self._state_machine.update(inp)
            state = self._state_machine.tick(16)
            return {"expression": state.expressionName, "cycleIndex": state.cycleIndex}

    def _start_gamepad_thread(self) -> None:
        self._gamepad_manager.start()

        def poll_loop() -> None:
            while True:
                try:
                    state = self._gamepad_manager.poll()
                    if state.connected:
                        buttons = [
                            {"pressed": bool(b), "value": 0.0}
                            for b in state.buttons
                        ]
                        inp = AvatarInput(
                            buttons=buttons,
                            axes=state.axes,
                            connected=state.connected,
                            streaming=False,
                            chatFocused=False,
                            errorState=False,
                        )
                        self._state_machine.update(inp)
                except Exception:
                    pass
                time.sleep(0.01)  # 100Hz

        self._thread = threading.Thread(target=poll_loop, daemon=True)
        self._thread.start()

    def _fetch_sprite(self) -> None:
        import httpx

        try:
            resp = httpx.get(
                f"{self._server_url}/api/avatar/sprite", timeout=5.0
            )
            data = resp.json()
            self._sprite_data = data.get("sprite_b64")
            self._sprite_width = data.get("width", 0)
            self._sprite_height = data.get("height", 0)
            self._frame_width = data.get("frameWidth", 0)
            self._frame_height = data.get("frameHeight", 0)
        except Exception:
            # Sprite fetch failed — renderer will show "No sprite data"
            print(
                f"[ziomek client] Warning: could not fetch sprite from {self._server_url}/api/avatar/sprite",
                file=sys.stderr,
            )

    def _open_local_browser(self) -> None:
        import webbrowser

        url = f"http://127.0.0.1:{self._port}/avatar-view"
        print(f"[ziomek client] Opening avatar view in browser: {url}", file=sys.stderr)
        try:
            webbrowser.open(url)
        except Exception:
            pass  # Headless environments may fail

    def stop(self) -> None:
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self._gamepad_manager.stop()
