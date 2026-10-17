/**
 * Avatar WebSocket Client
 *
 * Connects to the ziomek server via WebSocket for avatar state updates.
 * Reconnects automatically with exponential backoff on connection loss.
 */

import { Logger } from '../../logger.js';

const _logger = new Logger('debug');

export interface AvatarStateUpdate {
  expression: string;
  cycleIndex: number;
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export class AvatarWebSocketClient {
  private _ws: WebSocket | null = null;
  private _url: string;
  private _reconnectDelay = 2000;
  private _maxReconnectDelay = 30000;
  private _reconnectAttempts = 0;
  private _maxReconnectAttempts = 10;
  private _lastExpression = '';
  private _lastCycleIndex = -1;
  private _onStateChange?: (state: AvatarStateUpdate) => void;
  private _onStatusChange?: (status: ConnectionStatus) => void;
  private _status: ConnectionStatus = 'disconnected';

  constructor(baseUrl: string) {
    this._url = baseUrl
      .replace('http://', 'ws://')
      .replace('https://', 'wss://');
  }

  get status(): ConnectionStatus {
    return this._status;
  }

  private setStatus(status: ConnectionStatus): void {
    this._status = status;
    this._onStatusChange?.(status);
  }

  connect(): void {
    this.setStatus('connecting');
    _logger.debug('AvatarWebSocket', `Connecting to ${this._url} (attempt ${this._reconnectAttempts + 1})`);

    try {
      this._ws = new WebSocket(this._url);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      _logger.error('AvatarWebSocket', `Failed to create WebSocket: ${msg}`);
      this.setStatus('error');
      this._scheduleReconnect();
      return;
    }

    this._ws.onopen = () => {
      _logger.info('AvatarWebSocket', 'Connected successfully');
      this._reconnectAttempts = 0;
      this._reconnectDelay = 2000;
      this.setStatus('connected');
    };

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

    this._ws.onclose = (event) => {
      _logger.debug('AvatarWebSocket', `WebSocket closed (code: ${event.code}, reason: ${event.reason || 'no reason'})`);
      this.setStatus('disconnected');
      this._scheduleReconnect();
    };

    this._ws.onerror = () => {
      _logger.error('AvatarWebSocket', 'WebSocket error occurred');
      this.setStatus('error');
    };
  }

  private _scheduleReconnect(): void {
    if (this._reconnectAttempts >= this._maxReconnectAttempts) {
      _logger.warn('AvatarWebSocket', `Max reconnect attempts (${this._maxReconnectAttempts}) reached. Giving up.`);
      this.setStatus('error');
      return;
    }

    this._reconnectAttempts++;
    const delay = Math.min(this._reconnectDelay * Math.pow(2, this._reconnectAttempts - 1), this._maxReconnectDelay);
    _logger.debug('AvatarWebSocket', `Reconnecting in ${delay}ms (attempt ${this._reconnectAttempts}/${this._maxReconnectAttempts})`);
    setTimeout(() => this.connect(), delay);
  }

  disconnect(): void {
    this._reconnectAttempts = this._maxReconnectAttempts; // Stop auto-reconnect
    if (this._ws) {
      this._ws.close();
      this._ws = null;
    }
    this.setStatus('disconnected');
  }

  onStateChange(cb: (state: AvatarStateUpdate) => void): void {
    this._onStateChange = cb;
  }

  onStatusChange(cb: (status: ConnectionStatus) => void): void {
    this._onStatusChange = cb;
  }
}
