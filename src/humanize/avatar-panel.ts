/**
 * GamepadAvatarPanel — VS Code panel for displaying the animated avatar.
 *
 * Manages a VS Code webview panel with canvas-based avatar rendering.
 * Receives avatar state updates from the ziomek client via WebSocket.
 */

import * as vscode from 'vscode';
import { Logger } from '../logger.js';
import { AvatarWebSocketClient, AvatarStateUpdate } from './avatar/websocket-client.js';

const _logger = new Logger('debug');

/**
 * GamepadAvatarPanel manages a VS Code webview panel displaying
 * an animated avatar. State is received from the ziomek client
 * via WebSocket relay.
 */
export class GamepadAvatarPanel implements vscode.Disposable {
  static readonly viewType = 'humanizeAI.avatar';
  private _view?: vscode.WebviewView;
  private _htmlTemplate = '<html><body>Avatar view unavailable — start ziomek-client</body></html>';
  private _wsClient: AvatarWebSocketClient | null = null;
  private _disposables: vscode.Disposable[] = [];
  private _spriteWidth = 0;
  private _spriteHeight = 0;
  private _frameWidth = 0;
  private _frameHeight = 0;
  private _lastExpression = '';
  private _lastCycleIndex = -1;
  private _spriteDataUrl: string | null = null;

  constructor(
    private readonly _context: vscode.ExtensionContext,
  ) {
    // HTML template will be loaded from ziomek client at runtime
  }

  /** Load HTML template from ziomek client at runtime (HTTP GET /avatar-view) */
  async _loadSharedHtml(clientUrl: string): Promise<void> {
    try {
      const resp = await fetch(`${clientUrl}/avatar-view`);
      if (resp.ok) {
        this._htmlTemplate = await resp.text();
      }
    } catch {
      _logger.debug('AvatarPanel', 'Failed to load HTML from ziomek client, using fallback');
    }
  }

  /** Connect to ziomek client WebSocket for avatar state updates */
  connectToClient(clientUrl: string): void {
    this._wsClient = new AvatarWebSocketClient(clientUrl);
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

  /** Create or reveal the view */
  show(): void {
    if (this._view) {
      this._view.show?.(true);
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
      // No polling needed — state comes via WebSocket
    });

    this._view = view;
    this._view.webview.html = this._htmlTemplate;
  }

  /** Dispose panel and associated resources */
  dispose(): void {
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
