# Ziomek Client: Standalone Avatar Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract ziomek into two processes — a standalone `ziomek-client` (gamepad + state machine + avatar rendering + HTTP relay) and the existing `ziomek server` (TTS + sprite data). The client serves a shared HTML renderer that works in both a local browser view and the VS Code extension webview.

**Architecture:** ziomek client runs on the user's machine, polls gamepad with pygame, runs the avatar state machine in Python, renders the avatar via a FastAPI web server (serving HTML/JS canvas renderer). Client auto-opens a local browser window. The VS Code extension connects to the client's WebSocket for optional avatar display in a VS Code panel. Extension removes all gamepad code.

**Tech Stack:** Python 3.10+, FastAPI, WebSocket, pygame (gamepad), HTML/JS Canvas, TypeScript, VS Code Extension API

**Spec:** [docs/superpowers/specs/2026-09-24-gamepad-to-ziomek-design.md](./2026-09-24-gamepad-to-ziomek-design.md)

## Global Constraints

- ziomek server port: 5003 (unchanged)
- ziomek client port: 5004 (new — FastAPI + WebSocket)
- WebSocket endpoint path: `/avatar`
- HTML renderer: `ziomek/client/renderer.html` — served by client at `/avatar-view` (extension fetches via HTTP at runtime)
- gamepad-node dependency removed from package.json
- Client startup: `ziomek-client` (no flags = browser view + WebSocket relay to extension; `--no-vscode` = browser view only; `--no-browser` = extension relay only)
- WebSocket relay: ON by default (both browser view and extension relay active simultaneously); `--no-vscode` disables extension relay, `--no-browser` disables local browser view
- WebSocket relay delay: 10ms (client side), state changes only pushed when expression or cycleIndex changes
- Extension WebSocket reconnect delay: 2 seconds (exponential backoff)
- Extension loads HTML via `fetch(clientUrl + '/avatar-view')` at activation (no npm dependency)
- TTS via HTTP POST (unchanged)
- Sprite sheet: client fetches from server → caches → serves to renderer

## Review Focus

| Risk | Test in task |
|------|-------------|
| pygame init fails when no gamepad connected → client crashes on startup | Task 2: test `GamepadManager.start()` with no gamepad, verify graceful init |
| HTML renderer breaks in VS Code webview (CSP, cross-origin issues) | Task 1: ensure renderer uses only inline CSS/JS, no external resources |
| WebSocket relay blocks FastAPI event loop | Task 2: verify gamepad poll thread doesn't block async event loop under load |
| Client HTML renderer differs from extension webview experience | Task 1: shared HTML file used by both, verify rendering logic |
| Extension still imports stale types after deletion | Task 5: verify `tsc` compiles, no orphan imports |
| Client HTTP server blocks TTS server on same machine | Task 2: client port 5004, server port 5003 — verify no port conflict |

---

### Task 1: Shared HTML Renderer (`ziomek/client/renderer.html`)

**Files:**
- Create: `ziomek/client/renderer.html`

**Interfaces:**
- Consumes: None (self-contained HTML/CSS/JS)
- Produces: Canvas-based avatar renderer that accepts `{expression, cycleIndex}` messages via postMessage
- Works in both a browser window and a VS Code webview

**Dependencies:** None (pure HTML/CSS/JS)

- [ ] **Step 1: Create renderer.html**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>ziomek Avatar</title>
  <style>
    body {
      margin: 0;
      padding: 0;
      background: #1a1a2e;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    canvas {
      image-rendering: pixelated;
      image-rendering: crisp-edges;
    }
    #container {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
    }
    #status {
      color: #666;
      font-size: 12px;
      font-family: monospace;
    }
  </style>
</head>
<body>
  <div id="container">
    <canvas id="avatar" width="100" height="100"></canvas>
    <div id="status">Loading...</div>
  </div>

  <script>
    const canvas = document.getElementById('avatar');
    const ctx = canvas.getContext('2d');
    const statusEl = document.getElementById('status');

    let spriteData = null;
    let spriteWidth = 0;
    let spriteHeight = 0;
    let frameWidth = 0;
    let frameHeight = 0;
    let rows = 1;

    // Current state
    let currentExpression = '';
    let currentCycleIndex = -1;
    let lastExpression = '';
    let lastCycleIndex = -1;

    // Animation
    let animationId = null;
    let lastTime = 0;
    let frameIndex = 0;

    /**
     * Parse sprite sheet and draw current frame.
     * spriteData is base64 PNG (data:image/png;base64,...)
     */
    function drawAvatar(spriteData, width, height, frameWidth, frameHeight, rows, expression, cycleIndex) {
      if (!spriteData) {
        statusEl.textContent = 'No sprite data';
        return;
      }

      statusEl.textContent = `${expression}/${cycleIndex}`;

      if (spriteWidth !== width || spriteHeight !== height) {
        // Load sprite
        const img = new Image();
        img.onload = function() {
          spriteWidth = img.width;
          spriteHeight = img.height;
          rows = Math.max(1, Math.round(img.height / img.width));
          frameWidth = Math.floor(img.width / 1);
          frameHeight = Math.floor(img.height / rows);
          canvas.width = frameWidth;
          canvas.height = frameHeight;
          // Start animation
          startAnimation();
        };
        img.src = spriteData;
      }
    }

    /** Animation loop */
    function startAnimation() {
      if (animationId) cancelAnimationFrame(animationId);
      lastTime = performance.now();
      frameIndex = 0;

      function animate(now) {
        const delta = now - lastTime;
        lastTime = now;

        // Only draw if state changed
        if (expression !== currentExpression || cycleIndex !== currentCycleIndex) {
          currentExpression = expression;
          currentCycleIndex = cycleIndex;
          drawCurrentFrame(expression, cycleIndex);
        }

        animationId = requestAnimationFrame(animate);
      }
      animate(performance.now());
    }

    function drawCurrentFrame(expression, cycleIndex) {
      if (!spriteData) return;

      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Calculate source rectangle
      const rowMap = {
        happy: 0, surprised: 1, curious: 2, looking: 2, thinking: 2,
        focused: 3, bored: 3, dying: 4, neutral: 1,
      };
      const row = rowMap[expression] ?? 1;

      ctx.drawImage(
        canvas.ownerDocument.getElementById('sprite-img') || (() => {
          // Create hidden image for sprite
          const img = new Image();
          img.id = 'sprite-img';
          img.style.display = 'none';
          img.src = spriteData;
          canvas.ownerDocument.body.appendChild(img);
          return img;
        })(),
        0, // source X
        row * frameHeight, // source Y (row * frameHeight)
        frameWidth, // source width
        frameHeight, // source height
        0, // dest X
        0, // dest Y
        canvas.width, // dest width
        canvas.height // dest height
      );
    }

    /** Load sprite from external source (e.g., FastAPI endpoint or VS Code API) */
    function loadSpriteFromUrl(url) {
      fetch(url)
        .then(res => res.json())
        .then(data => {
          spriteData = data.sprite_b64
            ? `data:image/png;base64,${data.sprite_b64}`
            : null;
          spriteWidth = data.width || 0;
          spriteHeight = data.height || 0;
          frameWidth = data.frameWidth || 0;
          frameHeight = data.frameHeight || 0;
          if (spriteData) {
            drawCurrentFrame(currentExpression, currentCycleIndex);
          }
        })
        .catch(err => {
          statusEl.textContent = 'Sprite load error: ' + err.message;
        });
    }

    /** Initialize — try to load sprite from window.spriteData or external URL */
    function init() {
      // Check for inline sprite data (VS Code webview mode)
      if (window.spriteData) {
        spriteData = window.spriteData;
        spriteWidth = window.spriteWidth;
        spriteHeight = window.spriteHeight;
        frameWidth = window.frameWidth;
        frameHeight = window.frameHeight;
        rows = Math.max(1, Math.round(spriteHeight / spriteWidth));
        canvas.width = frameWidth;
        canvas.height = frameHeight;
        startAnimation();
        statusEl.textContent = `Ready (${expression}/${cycleIndex})`;
      } else {
        // Try to load from remote (client mode)
        loadSpriteFromUrl('/api/avatar/sprite');
      }
    }

    // Listen for messages from parent (WebSocket relay or VS Code)
    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (msg && msg.type === 'update') {
        currentExpression = msg.expression;
        currentCycleIndex = msg.cycleIndex;
        drawCurrentFrame(msg.expression, msg.cycleIndex);
        statusEl.textContent = `${msg.expression}/${msg.cycleIndex}`;
      }
    });

    // Auto-initialize
    init();
  </script>
</body>
</html>
```

- [ ] **Step 2: Verify renderer works in browser**

Open `renderer.html` in a browser — should show "No sprite data" and "Ready" status. No JS errors in console.

- [ ] **Step 3: Commit**

```bash
cd ziomek
git add client/renderer.html
git commit -m "feat: add shared HTML avatar renderer (canvas-based, works in browser and webview)"
```

---

### Task 2: Ziomek Client — Gamepad Module

**Files:**
- Create: `ziomek/ziomek/client/gamepad.py`
- Create: `ziomek/tests/client/test_gamepad.py`

**Interfaces:**
- Consumes: `pygame` library
- Produces: `class GamepadManager` with methods `start() → None`, `poll() → GamepadState`, `stop() → None`
- `GamepadState`: dataclass with `buttons: list[float]`, `axes: list[float]`, `connected: bool`

**Dependencies:** None (pure Python)

- [ ] **Step 1: Define GamepadManager (pygame-based polling)**

```python
# ziomek/ziomek/client/gamepad.py
from __future__ import annotations
import threading
import time
from dataclasses import dataclass, field


@dataclass
class GamepadState:
    buttons: list[float] = field(default_factory=list)
    axes: list[float] = field(default_factory=list)
    connected: bool = False


class GamepadManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = GamepadState()
        self._initialized = False
        self._joystick = None

    def start(self) -> None:
        """Initialize pygame and discover gamepads."""
        import pygame
        pygame.joystick.init()
        count = pygame.joystick.get_count()
        if count > 0:
            self._joystick = pygame.joystick.Joystick(0)
            self._joystick.init()
            self._initialized = True
        # No gamepad connected — still considered "initialized"

    def poll(self) -> GamepadState:
        """Read current gamepad state. Thread-safe via lock."""
        if not self._initialized or self._joystick is None:
            return GamepadState()
        with self._lock:
            buttons = [self._joystick.get_button(i) for i in range(self._joystick.get_numbuttons())]
            axes = [self._joystick.get_axis(i) for i in range(self._joystick.get_numaxes())]
            self._state = GamepadState(
                buttons=buttons,
                axes=axes,
                connected=True,
            )
        return GamepadState(
            buttons=self._state.buttons,
            axes=self._state.axes,
            connected=self._state.connected,
        )

    def stop(self) -> None:
        """Cleanup pygame resources."""
        if self._joystick is not None:
            self._joystick.quit()
            self._joystick = None
        import pygame
        pygame.joystick.quit()
        self._initialized = False
```

- [ ] **Step 2: Write test**

```python
# ziomek/tests/client/test_gamepad.py
from ziomek.client.gamepad import GamepadManager, GamepadState


def test_gamepad_manager_initial_state():
    manager = GamepadManager()
    assert not manager._initialized
    state = manager.poll()
    assert state.buttons == []
    assert state.axes == []
    assert state.connected is False


def test_gamepad_manager_start_without_gamepad():
    """Should not raise when no gamepad is connected."""
    manager = GamepadManager()
    try:
        manager.start()
        manager.stop()
    except Exception:
        # pygame init may fail in headless; that's OK
        pass
```

- [ ] **Step 3: Run test to verify it fails (module not created)**

Run: `cd ziomek && python -m pytest tests/client/test_gamepad.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'ziomek.client.gamepad'"

- [ ] **Step 4: Implement GamepadManager and verify tests pass**

Implementation as shown in Step 1. Run: `cd ziomek && python -m pytest tests/client/test_gamepad.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ziomek
git add tests/client/test_gamepad.py ziomek/client/gamepad.py
git commit -m "feat: add gamepad polling module (GamepadManager with pygame)"
```

---

### Task 3: Ziomek Client — HTTP Server

**Files:**
- Create: `ziomek/ziomek/client/server.py`
- Create: `ziomek/tests/client/test_server.py`

**Interfaces:**
- Consumes: `GamepadManager` from Task 2, imports `AvatarStateMachine` from `ziomek.avatar.state_machine`
- Produces: FastAPI app with `/avatar-view` (serves renderer.html), `/avatar` (WebSocket relay), `/avatar/sprite` (sprite data from server)
- Client: `class ZiomekClientApp` with `start(port=5004) → None`, `stop() → None`

**Dependencies:** Task 2 (gamepad), existing state machine from ziomek.avatar

- [ ] **Step 1: Create HTTP server with FastAPI**

```python
# ziomek/ziomek/client/server.py
from __future__ import annotations
import os
import sys
import asyncio
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from ziomek.client.gamepad import GamepadManager, GamepadState
from ziomek.avatar.state_machine import AvatarStateMachine, AvatarInput, ExpressionState


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

        import uvicorn
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
                    if state.expressionName != self._last_expr or state.cycleIndex != self._last_cycle:
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
                return JSONResponse(status_code=503, content={"error": "Sprite not loaded"})
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

        return self._app

    def _start_gamepad_thread(self) -> None:
        self._gamepad_manager.start()

        def poll_loop():
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
            resp = httpx.get(f"{self._server_url}/api/avatar/sprite", timeout=5.0)
            data = resp.json()
            self._sprite_data = data.get("sprite_b64")
            self._sprite_width = data.get("width", 0)
            self._sprite_height = data.get("height", 0)
            self._frame_width = data.get("frameWidth", 0)
            self._frame_height = data.get("frameHeight", 0)
        except Exception:
            # Sprite fetch failed — renderer will show "No sprite data"
            pass

    def _open_local_browser(self) -> None:
        import webbrowser
        url = f"http://127.0.0.1:{self._port}/avatar-view"
        print(f"Opening avatar view in browser: {url}", file=sys.stderr)
        try:
            webbrowser.open(url)
        except Exception:
            pass  # Headless environments may fail

    def stop(self) -> None:
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self._gamepad_manager.stop()
```

- [ ] **Step 2: Write test (structure check)**

```python
# ziomek/tests/client/test_server.py
from ziomek.client.server import ZiomekClientApp


def test_client_app_has_required_methods():
    app = ZiomekClientApp()
    assert hasattr(app, 'start')
    assert hasattr(app, 'stop')
    assert hasattr(app, '_create_app')


def test_client_app_default_port():
    app = ZiomekClientApp()
    assert app._port == 5004
```

- [ ] **Step 3: Run test to verify it fails (module not created)**

Run: `cd ziomek && python -m pytest tests/client/test_server.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement and verify tests pass**

Implementation as shown in Step 1. Run: `cd ziomek && python -m pytest tests/client/test_server.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ziomek
git add tests/client/test_server.py ziomek/client/server.py
git commit -m "feat: add ziomek client HTTP server (FastAPI, gamepad relay, WebSocket, sprite fetch)"
```

---

### Task 4: Ziomek Client — CLI Launcher

**Files:**
- Create: `ziomek/ziomek/client/cli.py`
- Modify: `ziomek/pyproject.toml` (add client entry point)

**Interfaces:**
- Consumes: `ZiomekClientApp` from Task 3
- Produces: `ziomek-client` command-line tool with `--port`, `--no-vscode`, `--no-browser`, `--server-url` flags (default: both browser AND WebSocket relay enabled)

**Dependencies:** Task 3 (client server)

- [ ] **Step 1: Create CLI**

```python
# ziomek/ziomek/client/cli.py
from __future__ import annotations
import argparse
import sys

from ziomek.client.server import ZiomekClientApp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ziomek-client",
        description="ziomek client — gamepad polling + avatar display",
    )
    parser.add_argument("--port", type=int, default=5004, help="Client HTTP port (default: 5004)")
    parser.add_argument("--no-vscode", action="store_true", help="Disable WebSocket relay to VS Code (default: relay enabled)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open local browser")
    parser.add_argument(
        "--server-url",
        type=str,
        default="http://localhost:5003",
        help="ziomek server URL (default: http://localhost:5003)",
    )
    args = parser.parse_args()

    client = ZiomekClientApp(
        server_url=args.server_url,
        port=args.port,
        open_browser=not args.no_browser,
    )

    print(f"ziomek client starting on port {args.port}", file=sys.stderr)
    print(f"  Sprite server: {args.server_url}", file=sys.stderr)
    print(f"  Open browser: {not args.no_browser}", file=sys.stderr)
    print(f"  VS Code relay: {not args.no_vscode}", file=sys.stderr)
    print(file=sys.stderr)

    client.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update pyproject.toml**

```toml
# Add to existing [project.scripts] section:
[project.scripts]
ziomek = "ziomek.cli:main"
ziomek-client = "ziomek.client.cli:main"
```

- [ ] **Step 3: Install ziomek in dev mode and verify CLI**

Run: `pip install -e .`
Run: `ziomek-client --help`
Expected: Output showing available flags

- [ ] **Step 4: Commit**

```bash
cd ziomek
git add ziomek/client/cli.py ziomek/pyproject.toml
git commit -m "feat: add ziomek-client CLI with --port, --no-browser, --no-vscode, --server-url flags"
```

---

### Task 5: Extension Simplification

**Files:**
- Modify: `src/extension.ts` (remove gamepad code, add WebSocket relay to client)
- Modify: `src/humanize/avatar-panel.ts` (load shared HTML, connect to client WebSocket)
- Delete: `src/humanize/service.ts` (GamepadService)
- Delete: `src/humanize/events.ts` (GamepadEvent types)
- Modify: `package.json` (remove gamepad-node)

**Interfaces:**
- Consumes: WebSocket from client (`AvatarWebSocketClient`), fetches HTML at runtime from `http://localhost:5004/avatar-view` (HTTP GET)
- Produces: Simplified extension (~50 lines of gamepad code removed)
- Extension loads HTML via `fetch(clientUrl + '/avatar-view')` at activation time (no npm dependency, no file copying)

**Dependencies:** Task 2 (gamepad module), Task 3 (client server)

- [ ] **Step 1: Create websocket-client.ts in extension**

```typescript
// src/humanize/avatar/websocket-client.ts
import { Logger } from '../logger.js';

const _logger = new Logger('debug');

export interface AvatarStateUpdate {
  expression: string;
  cycleIndex: number;
}

export class AvatarWebSocketClient {
  private _ws: WebSocket | null = null;
  private _url: string;
  private _reconnectDelay = 2000;
  private _lastExpression = '';
  private _lastCycleIndex = -1;
  private _onStateChange?: (state: AvatarStateUpdate) => void;

  constructor(baseUrl: string) {
    this._url = baseUrl.replace('http://', 'ws://').replace('https://', 'wss://');
  }

  connect(): void {
    this._ws = new WebSocket(this._url);
    this._ws.onmessage = (event) => {
      const data = JSON.parse(event.data) as AvatarStateUpdate;
      if (data.expression !== this._lastExpression || data.cycleIndex !== this._lastCycleIndex) {
        this._lastExpression = data.expression;
        this._lastCycleIndex = data.cycleIndex;
        this._onStateChange?.(data);
      }
    };
    this._ws.onclose = () => {
      _logger.debug('AvatarWebSocket', 'WebSocket closed, reconnecting...');
      setTimeout(() => this.connect(), this._reconnectDelay);
    };
    this._ws.onerror = (err) => {
      _logger.error('AvatarWebSocket', 'WebSocket error:', err);
    };
  }

  disconnect(): void {
    if (this._ws) {
      this._ws.close();
      this._ws = null;
    }
  }

  onStateChange(cb: (state: AvatarStateUpdate) => void): void {
    this._onStateChange = cb;
  }
}
```

- [ ] **Step 2: Modify avatar-panel.ts**

```typescript
// Key changes to src/humanize/avatar-panel.ts:
import { join } from 'path';
import { readFileSync } from 'node:fs';
import { AvatarWebSocketClient } from './avatar/websocket-client.js';

export class GamepadAvatarPanel implements vscode.Disposable {
  // ... existing fields ...
  private _wsClient: AvatarWebSocketClient | null = null;

  constructor(
    private readonly _context: vscode.ExtensionContext,
    _skinRegistry: SkinRegistry,  // REMOVED — no longer needed locally
    // stateMachine REMOVED — state machine is now on ziomek client
    assetResolver?: AssetResolver,
  ) {
    // Load shared HTML renderer from ziomek client
    this._htmlTemplate = this._loadSharedHtml();
  }

  /** Load shared HTML renderer from ziomek client at runtime (HTTP GET /avatar-view) */
  private async _loadSharedHtml(): Promise<string> {
    try {
      const clientUrl = vscode.workspace.getConfiguration('ziomek').get('client.url', 'http://localhost:5004');
      const resp = await fetch(`${clientUrl}/avatar-view`);
      if (resp.ok) return await resp.text();
    } catch {
      // Client unavailable — generate minimal HTML
    }
    return '<html><body>Avatar view unavailable — start ziomek-client (ziomek-client --port 5004)</body></html>';
  }

  /** Connect to ziomek client WebSocket for avatar state updates */
  connectToClient(baseUrl: string): void {
    this._wsClient = new AvatarWebSocketClient(baseUrl);
    this._wsClient.onStateChange((state) => {
      if (!this._view) return;
      this._view.webview.postMessage({
        type: 'update',
        expression: state.expression,
        cycleIndex: state.cycleIndex,
      });
    });
    this._wsClient.connect();
  }

  dispose(): void {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
    if (this._wsClient) {
      this._wsClient.disconnect();
      this._wsClient = null;
    }
    this._view = undefined;
    while (this._disposables.length) {
      this._disposables.pop()?.dispose();
    }
  }
}
```

- [ ] **Step 3: Modify extension.ts**

```typescript
// Key changes:
import { GamepadAvatarPanel } from './humanize/avatar-panel.js';
import { Logger } from './logger.js';

let avatarPanel: GamepadAvatarPanel | null = null;
let logger: Logger | null = null;

export function activate(context: vscode.ExtensionContext) {
  logger = new Logger('debug');
  logger.info('extension', 'Activating Humanize AI extension');

  // ... existing Copilot Chat module registration ...

  // Avatar panel — load shared HTML renderer
  avatarPanel = new GamepadAvatarPanel(context, null);  // skinRegistry no longer needed

  // Connect to ziomek client (optional — user can disable with config)
  const config = vscode.workspace.getConfiguration('ziomek');
  const clientUrl = config.get('client.url', 'http://localhost:5004');
  avatarPanel.connectToClient(clientUrl);

  // Register view provider
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      GamepadAvatarPanel.viewType,
      avatarPanel,
    ),
  );
}
```

- [ ] **Step 4: Run compile to verify no TypeScript errors**

Run: `npm run compile`
Expected: PASS (no errors)

- [ ] **Step 5: Remove gamepad-node from package.json**

```json
{
  // Remove this dependency:
  "gamepad-node": "..."
}
```

- [ ] **Step 6: Delete service.ts and events.ts**

```bash
rm src/humanize/service.ts src/humanize/events.ts
```

- [ ] **Step 7: Run all tests**

Run: `npm test`
Expected: PASS (update any failing tests that reference deleted files)

- [ ] **Step 8: Commit**

```bash
git add src/extension.ts src/humanize/avatar-panel.ts src/humanize/avatar/websocket-client.ts package.json src/humanize/service.ts src/humanize/events.ts
git commit -m "refactor: remove gamepad code from extension, add WebSocket client to ziomek client, load shared HTML renderer"
```

---

### Task 6: Launcher Scripts & README

**Files:**
- Modify: `ziomek/run-ziomek.sh`
- Modify: `ziomek/run-ziomek.bat`
- Modify: `README.md`

**Interfaces:**
- Consumes: None
- Produces: Updated launcher scripts and README documenting both processes

**Dependencies:** All tasks

- [ ] **Step 1: Update README.md**

```markdown
## Installation

### Step 1: Install ziomek Server (TTS backend)

```bash
git clone <ziomek-repo-url>
cd ziomek
pip install -e .

# Start TTS server
ziomek serve --port 5003
```

### Step 2: Start ziomek Client (gamepad + avatar display)

```bash
# Start client (opens browser, relays to VS Code)
ziomek-client --port 5004 --server-url http://localhost:5003

# Options:
# --no-browser     : Disable local browser view
# --no-vscode      : Disable WebSocket relay to VS Code
# --server-url URL : Ziomek TTS server URL (default: http://localhost:5003)
#
# Default behavior: opens browser window AND relays to VS Code.
# --no-vscode: disable VS Code relay (keep browser only)
# --no-browser: disable browser (keep VS Code relay only)
```

### Step 3: Install VS Code Extension

```bash
cd <extension-root>
npm install
npm run compile
# Press F5 in VS Code
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `ziomek.client.url` | `http://localhost:5004` | URL of the ziomek client (gamepad relay) |
| `ziomek.tts.url` | `http://localhost:5003` | URL of the ziomek TTS server |
| `ziomek.enabled` | `true` | Enable gamepad input |
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with ziomek client installation instructions"
```

---

## Final Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     ziomek client (port 5004)                            │
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐          │
│  │ pygame       │───→│ State Machine│───→│ HTML/JS Renderer │          │
│  │ gamepad poll │    │ (Python)     │    │ (shared)           │          │
│  └──────────────┘    └──────────────┘    │  Browser/Canvas  │          │
│                                         └──────────────────┘          │
│  ┌────────────────────┐     ┌──────────────────┐                      │
│  │ FastAPI Web Server │───→ │ Local Browser     │                      │
│  │ :5004              │     │ (auto-opened)     │                      │
│  │                    │     └──────────────────┘                      │
│  │ /avatar-view       │                                                │
│  │ /avatar            │   ┌──────────────────┐                         │
│  │ /avatar/sprite     │   │ Extension Canvas  │                         │
│  │ /avatar/state      │   │ (optional relay)  │                         │
│  └────────────────────┘   └──────────────────┘                         │
└──────────────────────────────────────────────────────────────────────────┘
                                                                        │
                                                                        │ WebSocket relay (optional)
                                                                        ▼
┌─────────────────────────────┐     ┌──────────────────────────────────┐
│  VS Code Extension          │     │  ziomek server (port 5003)       │
│  • Canvas rendering         │     │  • TTS synthesis                 │
│  • Copilot Chat integration │     │  • Sprite data                   │
│  • Gamepad → client relay   │     │  • Audio playback                │
  • Fetches HTML from client   │                                    │
└─────────────────────────────┘     └──────────────────────────────────┘
```

## File Summary

| File | Action |
|------|--------|
| `ziomek/client/renderer.html` | Create — shared HTML avatar renderer |
| `ziomek/ziomek/client/gamepad.py` | Create — pygame gamepad polling |
| `ziomek/ziomek/client/server.py` | Create — FastAPI server with avatar relay |
| `ziomek/ziomek/client/cli.py` | Create — CLI launcher |
| `ziomek/tests/client/test_gamepad.py` | Create — gamepad tests |
| `ziomek/tests/client/test_server.py` | Create — server tests |
| `src/humanize/avatar/websocket-client.ts` | Create — extension WebSocket client |
| `src/humanize/avatar-panel.ts` | Modify — load shared HTML, connect to client |
| `src/extension.ts` | Modify — simplified, no gamepad code |
| `src/humanize/service.ts` | Delete |
| `src/humanize/events.ts` | Delete |
| `package.json` | Modify — remove gamepad-node |
| `README.md` | Modify — update docs |
| `ziomek/pyproject.toml` | Modify — add ziomek-client entry point |
