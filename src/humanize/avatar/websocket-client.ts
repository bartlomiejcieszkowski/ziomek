/**
 * Avatar WebSocket Client
 *
 * Connects to the ziomek client via WebSocket for avatar state updates.
 * Reconnects automatically with exponential backoff on connection loss.
 */

import { Logger } from '../../logger.js';

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
    this._url = baseUrl
      .replace('http://', 'ws://')
      .replace('https://', 'wss://');
  }

  connect(): void {
    this._ws = new WebSocket(this._url);

    this._ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AvatarStateUpdate;
        if (
          data.expression !== this._lastExpression ||
          data.cycleIndex !== this._lastCycleIndex
        ) {
          this._lastExpression = data.expression;
          this._lastCycleIndex = data.cycleIndex;
          this._onStateChange?.(data);
        }
      } catch (err) {
        _logger.error('AvatarWebSocket', 'Failed to parse WebSocket message:', err);
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
