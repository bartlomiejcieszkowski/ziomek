import type { GamepadEvent, GamepadEventListener } from './events.js';

export class GamepadService {
  private readonly _listeners = new Set<GamepadEventListener>();
  private _pollingInterval: number | null = null;
  private readonly _pollingIntervalMs: number;
  private readonly _previousStates = new Map<number, ReadonlyArray<{ pressed: boolean; value: number }>>();

  constructor(pollingIntervalMs: number = 16) {
    this._pollingIntervalMs = pollingIntervalMs;
  }

  start(): void {
    // Stub - will use gamepad-node in Task 2
  }

  stop(): void {
    if (this._pollingInterval !== null) {
      clearInterval(this._pollingInterval);
      this._pollingInterval = null;
    }
  }

  on(_event: 'button' | 'axis' | 'connect' | 'disconnect' | 'all', _listener: GamepadEventListener): () => void {
    this._listeners.add(_listener);
    return () => {
      this._listeners.delete(_listener);
    };
  }

  private _emit_(_event: GamepadEvent): void {
    // Stub - will emit events in Task 2
  }
}
