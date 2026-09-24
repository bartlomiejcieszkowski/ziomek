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
  static readonly viewType = 'humanizeAI.avatar';
  private readonly _stateMachine: StateMachineProvider;
  private readonly _assetResolver: AssetResolver;

  private _view?: vscode.WebviewView;
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
  private readonly _htmlTemplate: string;

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

    // Load HTML template and sprite sheet once at construction time
    this._htmlTemplate = this._loadHtmlTemplate();
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

  /** Create or reveal the view */
  show(): void {
    if (this._view) {
      this._view.show?.(true);
      // Start polling if already visible (view already created)
      if (this._view.visible && !this._pollTimer) {
        this._startPolling();
      }
      return;
    }
  }

  /** Provide the webview view (called automatically by VS Code) */
  resolveWebviewView(view: vscode.WebviewView, _context: vscode.WebviewViewResolveContext<unknown>, _token: vscode.CancellationToken): void {
    
    view.webview.options = { 
      enableScripts: true,
      localResourceRoots: [
        this._context.extensionUri
      ]
    };
    
    // Listen for messages from the webview (two-way communication)
    view.webview.onDidReceiveMessage((message) => {
      switch (message.type) {
        case 'log':
          _logger.debug('AvatarWebview', message.text || '');
          break;
        default:
          break;
      }
    });

    // Listen for visibility changes
    view.onDidChangeVisibility(() => {
      if (this._view?.visible && !this._pollTimer) {
        this._startPolling();
      } else if (!this._view?.visible) {
        this._stopPolling();
      }
    });

    this._view = view;
    this._view.webview.html = this._htmlTemplate;
  }

  /** Stop polling loop */
  private _stopPolling(): void {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  }

  /** Dispose panel and associated resources */
  dispose(): void {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
    this._view = undefined;
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
    _logger.debug('AvatarPanel', '_startPolling: view exists =', Boolean(this._view));
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
    if (!this._view) return;

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
    if (!this._view) return;

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

    this._view.webview.postMessage({
      type: 'update',
      expression: state.expressionName,
      cycleIndex: state.cycleIndex,
      spriteWidth: this._spriteWidth,
      spriteHeight: this._spriteHeight,
      frameWidth: this._frameWidth,
      frameHeight: this._frameHeight,
      row,
      spriteData,
    });
  }

  /** Load HTML template from disk */
  private _loadHtmlTemplate(): string {
    try {
      const htmlPath = this._assetResolver('src/gamepad/avatar-panel.html');
      return readFileSync(htmlPath, 'utf-8');
    } catch {
      return '';
    }
  }
}
