/**
 * GamepadAvatarPanel — VS Code panel for displaying the animated avatar.
 *
 * Manages a VS Code webview panel with canvas-based avatar rendering.
 * The avatar reacts to gamepad input via the state machine.
 */

import * as vscode from 'vscode';
import { join } from 'path';
import { readFileSync } from 'node:fs';
import { Logger } from '../logger.js';
import { SkinRegistry } from './avatar/skin-registry.js';
import { GamepadAvatarInput, ExpressionState } from './avatar/state-machine.js';

const _logger = new Logger('debug');

/** State sent from extension to panel */
interface UpdateMessage {
  type: 'update';
  expression: string;
  cycleIndex: number;
  spriteWidth: number;
  spriteHeight: number;
  frameWidth: number;
  frameHeight: number;
  row: number;
  spriteData?: string;
}

/** State machine instance used for expression updates */
interface StateMachineProvider {
  update(input: GamepadAvatarInput): void;
  tick(dtMs: number): ExpressionState;
}

/** Asset resolver function — resolves relative paths relative to extension root */
export type AssetResolver = (relativePath: string) => string;

/**
 * GamepadAvatarPanel manages a VS Code webview panel displaying
 * an animated avatar that reacts to gamepad input.
 */
export class GamepadAvatarPanel implements vscode.Disposable {
  static readonly viewType = 'gamifyAI.avatar';
  private readonly _stateMachine: StateMachineProvider;
  private readonly _assetResolver: AssetResolver;

  private _panel?: vscode.WebviewPanel;
  private _pollTimer: ReturnType<typeof setInterval> | null = null;
  private _lastPollTime = 0;
  private _lastExpression = '';
  private _lastCycleIndex = -1;
  private _disposables: vscode.Disposable[] = [];
  private _spriteBuffer: Buffer | null = null;
  private _spriteWidth = 0;
  private _spriteHeight = 0;
  private _frameWidth = 0;
  private _frameHeight = 0;
  private _rows = 0;

  // VS Code state
  private _streaming = false;
  private _chatFocused = false;
  private _errorState = false;

  // Gamepad state
  private _gamepadButtons: Array<{ pressed: boolean; value: number }> = [];
  private _gamepadAxes: number[] = [];
  private _gamepadConnected = false;

  constructor(
    private readonly _context: vscode.ExtensionContext,
    _skinRegistry: SkinRegistry,
    stateMachine: StateMachineProvider,
    assetResolver?: AssetResolver,
  ) {
    this._stateMachine = stateMachine;
    this._assetResolver = assetResolver ?? ((rel: string) => join(this._context.extensionUri.fsPath, rel));

    // Load sprite sheet once at construction time
    this._loadSprite();
  }

  /** Load sprite sheet at startup */
  private _loadSprite(): void {
    try {
      const spritePath = this._assetResolver('3rd_party/single_frame_sprite_sheet.png');
      console.log(`[Avatar] Loading sprite sheet: ${spritePath}`);
      const spriteBuffer = readFileSync(spritePath);
      console.log(`[Avatar] Sprite sheet loaded: ${spriteBuffer.length} bytes`);
      // Parse PNG header for dimensions
      if (spriteBuffer[0] === 0x89 && spriteBuffer[1] === 0x50) {
        this._spriteBuffer = spriteBuffer;
        this._spriteWidth = (spriteBuffer[16] << 24) | (spriteBuffer[17] << 16) | (spriteBuffer[18] << 8) | spriteBuffer[19];
        this._spriteHeight = (spriteBuffer[20] << 24) | (spriteBuffer[21] << 16) | (spriteBuffer[22] << 8) | spriteBuffer[23];
        // Auto-detect rows from dimensions
        this._rows = Math.max(1, Math.round(this._spriteHeight / this._spriteWidth));
        this._frameWidth = Math.floor(this._spriteWidth / 1);
        this._frameHeight = Math.floor(this._spriteHeight / this._rows);
        console.log(`[Avatar] Sprite dimensions: ${this._spriteWidth}x${this._spriteHeight}, ${this._rows} frames (${this._frameWidth}x${this._frameHeight}px)`);
      } else {
        console.error('[Avatar] Not a valid PNG file');
        this._spriteBuffer = null;
      }
    } catch (err) {
      // Sprite loading failed — will use placeholder rendering
      console.error('[Avatar] Failed to load sprite sheet:', err);
      this._spriteBuffer = null;
    }
  }

  /** Show or reveal the panel */
  show(): void {
    if (this._panel) {
      this._panel.reveal();
      // Start polling if already visible (panel already created)
      if (this._panel.visible && !this._pollTimer) {
        this._startPolling();
      }
      return;
    }

    this._panel = vscode.window.createWebviewPanel(
      GamepadAvatarPanel.viewType,
      'Gamify AI — Avatar',
      vscode.ViewColumn.Two,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
      },
    );

    this._panel.webview.html = this._getHtml();

    this._panel.onDidDispose(() => {
      this.dispose();
    }, null, this._disposables);

    this._panel.onDidChangeViewState((event) => {
      if (event.webviewPanel.visible && !this._pollTimer) {
        this._startPolling();
      }
    });
  }

  /** Hide the panel */
  hide(): void {
    if (this._panel) {
      this._panel.dispose();
      this._panel = undefined;
    }
  }

  /** Dispose panel and associated resources */
  dispose(): void {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
    this._panel?.dispose();
    this._panel = undefined;
    while (this._disposables.length) {
      this._disposables.pop()?.dispose();
    }
  }

  /** Update gamepad state from gamepad-node */
  updateFromGamepad(gamepads: Array<{ buttons: ReadonlyArray<{ pressed: boolean; value: number }>; axes: ReadonlyArray<number> }>): void {
    if (gamepads.length > 0) {
      const gp = gamepads[0];
      this._gamepadConnected = true;
      this._gamepadButtons = gp.buttons.map(b => ({ pressed: b.pressed, value: b.value }));
      this._gamepadAxes = [...gp.axes];
    } else {
      this._gamepadConnected = false;
    }
  }

  /** Set VS Code chat streaming state */
  setStreaming(streaming: boolean): void {
    this._streaming = streaming;
  }

  /** Set VS Code error state */
  setErrorState(errorState: boolean): void {
    this._errorState = errorState;
  }

  /** Set VS Code chat focused state */
  setChatFocused(chatFocused: boolean): void {
    this._chatFocused = chatFocused;
  }

  /** Directly update panel state (for testing) */
  updateState(state: ExpressionState): void {
    this._sendToPanel(state);
  }

  /** Get the current state machine expression */
  getCurrentState(): ExpressionState {
    const input = this._getInput();
    this._stateMachine.update(input);
    return this._stateMachine.tick(16);
  }

  /** Start polling loop */
  private _startPolling(): void {
    this._lastPollTime = Date.now();
    this._pollTimer = setInterval(() => {
      this._updatePanel();
    }, 100); // 10 FPS
  }

  /** Build gamepad input from current state */
  private _getInput(): GamepadAvatarInput {
    return {
      buttons: this._gamepadButtons,
      axes: this._gamepadAxes,
      connected: this._gamepadConnected,
      streaming: this._streaming,
      chatFocused: this._chatFocused,
      errorState: this._errorState,
    };
  }

  /** Update panel with current state */
  private _updatePanel(): void {
    if (!this._panel) return;

    const now = Date.now();
    const delta = this._lastPollTime > 0 ? now - this._lastPollTime : 100;
    this._lastPollTime = now;

    const input = this._getInput();
    this._stateMachine.update(input);
    const state = this._stateMachine.tick(delta);

    _logger.debug('AvatarPanel', `_updatePanel: delta=${delta}ms, spriteBuffer=${Boolean(this._spriteBuffer)}, state=${state.expressionName}/${state.cycleIndex}`);
    this._sendToPanel(state);
  }

  /** Send state to panel via postMessage */
  private _sendToPanel(state: ExpressionState): void {
    if (!this._panel) return;

    // Skip if expression hasn't changed
    if (state.expressionName === this._lastExpression && state.cycleIndex === this._lastCycleIndex) {
      return;
    }

    this._lastExpression = state.expressionName;
    this._lastCycleIndex = state.cycleIndex;

    // Get expression row from state machine (uses the ROW_MAP)
    const rowMap: Record<string, number> = {
      happy: 0, surprised: 1, curious: 2, looking: 2, thinking: 2,
      focused: 3, bored: 3, dying: 4, neutral: 1,
    };
    const row = rowMap[state.expressionName] ?? 1;

    _logger.debug('AvatarPanel', `_sendToPanel: expression=${state.expressionName}, row=${row}, spriteBuffer=${Boolean(this._spriteBuffer)}`);

    // Build sprite base64 from cached buffer
    const spriteData = this._spriteBuffer
      ? `data:image/png;base64,${this._spriteBuffer.toString('base64')}`
      : undefined;

    this._panel.webview.postMessage({
      type: 'update',
      expression: state.expressionName,
      cycleIndex: state.cycleIndex,
      spriteWidth: this._spriteWidth,
      spriteHeight: this._spriteHeight,
      frameWidth: this._frameWidth,
      frameHeight: this._frameHeight,
      row,
      spriteData,
    } as UpdateMessage);
  }

  /** Get HTML content for the webview */
  private _getHtml(): string {
    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      margin: 0;
      padding: 8px;
      background: #0a0a0a;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      overflow: hidden;
      font-family: 'Courier New', monospace;
    }
    #hud {
      position: relative;
      border: 3px solid #3a3a3a;
      box-shadow: 0 0 15px rgba(255, 0, 0, 0.2), inset 0 0 20px rgba(0, 0, 0, 0.8);
      border-radius: 4px;
    }
    #hud canvas {
      display: block;
      image-rendering: pixelated;
      image-rendering: crisp-edges;
    }
    #label {
      color: #ff4444;
      font-size: 10px;
      font-weight: bold;
      letter-spacing: 3px;
      text-align: center;
      margin-top: 8px;
      text-transform: uppercase;
      opacity: 0.9;
    }
  </style>
</head>
<body>
  <div id="hud">
    <canvas id="avatar" width="128" height="128"></canvas>
  </div>
  <div id="label">IDLE</div>
  <script>
    (function() {
      const canvas = document.getElementById('avatar');
      const ctx = canvas.getContext('2d')!;
      const label = document.getElementById('label');
      let spriteImage = null;
      let spriteSrc = null;
      let frameData = null;
      let tick = 0;

      function render() {
        tick++;

        if (!frameData) {
          ctx.fillStyle = '#1a1a1a';
          ctx.fillRect(0, 0, 128, 128);
          ctx.fillStyle = '#ff4444';
          ctx.font = '12px monospace';
          ctx.textAlign = 'center';
          ctx.fillText('...', 64, 64);
          return;
        }

        const { expression, row, spriteWidth, spriteHeight, frameWidth, frameHeight } = frameData;

        if (spriteImage) {
          ctx.imageSmoothingEnabled = false;
          const sy = row * frameHeight;
          ctx.drawImage(
            spriteImage,
            0, sy, frameWidth, frameHeight,
            0, 0, 128, 128
          );
        } else {
          // Draw placeholder avatar with basic shapes
          drawPlaceholder(ctx, expression, tick);
        }

        // Update label
        label.textContent = expression.toUpperCase();
        if (expression === 'dying') {
          label.style.color = '#ff0000';
        } else if (expression === 'happy') {
          label.style.color = '#44ff44';
        } else if (expression === 'surprised') {
          label.style.color = '#ffff44';
        } else {
          label.style.color = '#ff4444';
        }
      }

      function drawPlaceholder(ctx, expression, tick) {
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, 128, 128);

        const cx = 64, cy = 56;

        // Face outline
        ctx.fillStyle = '#d4a574';
        ctx.fillRect(cx - 26, cy - 26, 52, 52);

        // Hair
        ctx.fillStyle = '#4a3728';
        ctx.fillRect(cx - 28, cy - 28, 56, 12);

        // Eyes
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(cx - 14, cy - 8, 10, 10);
        ctx.fillRect(cx + 4, cy - 8, 10, 10);

        // Pupils
        ctx.fillStyle = '#000000';
        let pupilX = 0, pupilY = 0;
        if (expression === 'surprised' || expression === 'focused') {
          pupilX = -2; pupilY = 2; // Small pupils
        } else if (expression === 'thinking') {
          pupilY = -3; // Looking up
        } else if (expression === 'happy') {
          // Squinty eyes
          ctx.fillStyle = '#000000';
          ctx.fillRect(cx - 12, cy - 2, 6, 3);
          ctx.fillRect(cx + 6, cy - 2, 6, 3);
          ctx.fillStyle = '#1a1a1a';
          ctx.fillRect(0, 0, 128, 128);
          ctx.fillStyle = '#d4a574';
          ctx.fillRect(cx - 26, cy - 26, 52, 52);
          ctx.fillStyle = '#4a3728';
          ctx.fillRect(cx - 28, cy - 28, 56, 12);
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(cx - 14, cy - 8, 10, 10);
          ctx.fillRect(cx + 4, cy - 8, 10, 10);
          // Smile
          ctx.fillStyle = '#000000';
          ctx.fillRect(cx - 10, cy + 10, 20, 3);
          return;
        }

        ctx.fillRect(cx - 12 + pupilX, cy - 6 + pupilY, 4, 4);
        ctx.fillRect(cx + 6 + pupilX, cy - 6 + pupilY, 4, 4);

        // Brow
        ctx.fillStyle = '#4a3728';
        if (expression === 'surprised' || expression === 'focused') {
          ctx.fillRect(cx - 16, cy - 12, 14, 3);
          ctx.fillRect(cx + 2, cy - 12, 14, 3);
        } else if (expression === 'dying') {
          // Closed eyes
          ctx.fillStyle = '#000000';
          ctx.fillRect(cx - 14, cy - 2, 10, 3);
          ctx.fillRect(cx + 4, cy - 2, 10, 3);
        } else if (expression === 'happy') {
          // Relaxed brow
          ctx.fillRect(cx - 16, cy - 2, 14, 2);
          ctx.fillRect(cx + 2, cy - 2, 14, 2);
        }

        // Mouth
        ctx.fillStyle = '#000000';
        if (expression === 'dying') {
          // Grimace
          ctx.fillRect(cx - 8, cy + 12, 16, 8);
        } else if (expression === 'surprised') {
          // O mouth
          ctx.beginPath();
          ctx.arc(cx, cy + 14, 6, 0, Math.PI * 2);
          ctx.fill();
        } else if (expression === 'happy' || expression === 'thinking') {
          // Smile
          ctx.fillRect(cx - 10, cy + 12, 20, 3);
        } else {
          // Neutral line
          ctx.fillRect(cx - 6, cy + 10, 12, 2);
        }
      }

      // Receive messages from extension
      window.addEventListener('message', function(event) {
        const message = event.data;
        if (message.type === 'update') {
          console.log('[Webview] Received update:', message.expression, '/', message.cycleIndex);
          frameData = message;

          if (message.spriteData && message.spriteData !== spriteSrc) {
            spriteImage = new Image();
            spriteSrc = message.spriteData;
            spriteImage.onload = function() { render(); };
            spriteImage.src = message.spriteData;
          } else {
            render();
          }
        }
      });

      // Initial render
      render();
    })();
  </script>
</body>
</html>`;
  }
}
