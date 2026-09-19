import { installNavigatorShim as _installNavigatorShim } from 'gamepad-node';

// Type declaration for gamepad-node (no @types package available)
declare function installNavigatorShim(options?: {
  sdl?: any;
}): {
  on(event: string, listener: (...args: any[]) => void): void;
  startPolling(fps: number): void;
  poll(): void;
  getGamepads(): Array<any>;
  _destroyed?: boolean;
};

import type { GamepadEvent, GamepadEventListener, GamepadState } from './events.js';

export class GamepadService {
  private readonly _listeners = new Set<GamepadEventListener>();
  private _pollingInterval: ReturnType<typeof setInterval> | null = null;
  private readonly _pollingIntervalMs: number;
  private readonly _previousStates = new Map<number, ReadonlyArray<{ pressed: boolean; value: number }>>();
  private _manager: ReturnType<typeof installNavigatorShim> | null = null;

  constructor(pollingIntervalMs: number = 16) {
    this._pollingIntervalMs = pollingIntervalMs;
  }

  start(): void {
    try {
      this._manager = _installNavigatorShim() as ReturnType<typeof installNavigatorShim>;

      // Forward connect/disconnect events from gamepad-node
      this._manager.on('gamepadconnected', (event: { gamepad: any }) => {
        this._emit({
          type: 'gamepadconnected',
          gamepad: this._toEventState(event.gamepad),
        } as GamepadEvent);
      });

      this._manager.on('gamepaddisconnected', (event: { gamepad: any }) => {
        this._emit({
          type: 'gamepaddisconnected',
          gamepad: this._toEventState(event.gamepad),
        } as GamepadEvent);
      });

      // Start polling loop
      this._previousStates.clear();
      this._pollingInterval = globalThis.setInterval(() => this._poll(), this._pollingIntervalMs);
    } catch (error) {
      console.error('GamepadService: failed to initialize gamepad-node:', error);
      // Graceful degradation - service can still be stopped without crashing
    }
  }

  stop(): void {
    if (this._pollingInterval !== null) {
      clearInterval(this._pollingInterval);
      this._pollingInterval = null;
    }
    this._manager = null;
  }

  on(_event: 'button' | 'axis' | 'connect' | 'disconnect' | 'all', listener: GamepadEventListener): () => void {
    this._listeners.add(listener);
    return () => {
      this._listeners.delete(listener);
    };
  }

  private _poll(): void {
    try {
      const gamepads = navigator.getGamepads();

      for (const gamepad of gamepads) {
        if (!gamepad) continue;

        const previousButtons = this._previousStates.get(gamepad.index);
        const currentButtons = gamepad.buttons.map(b => ({ pressed: b.pressed, value: b.value }));

        // Detect button transitions
        gamepad.buttons.forEach((btn, i) => {
          if (previousButtons && previousButtons[i]) {
            if (btn.pressed !== previousButtons[i].pressed) {
              this._emit({
                type: 'gamepadbutton',
                index: gamepad.index,
                buttonIndex: i,
                pressed: btn.pressed,
                value: btn.value,
              } as GamepadEvent);
            }
          }
        });

        // Detect axis changes
        gamepad.axes.forEach((axis, i) => {
          this._emit({
            type: 'gamepadaxis',
            index: gamepad.index,
            axisIndex: i,
            value: axis,
          } as GamepadEvent);
        });

        this._previousStates.set(gamepad.index, currentButtons);
      }
    } catch {
      // Ignore polling errors (e.g., gamepad disconnected mid-poll)
    }
  }

  private _toEventState(gamepad: GamepadState): GamepadState {
    return {
      id: gamepad.id,
      index: gamepad.index,
      connected: gamepad.connected,
      buttons: gamepad.buttons.map(b => ({ pressed: b.pressed, value: b.value })),
      axes: [...gamepad.axes],
      mapping: gamepad.mapping,
    };
  }

  private _emit(event: GamepadEvent): void {
    for (const listener of this._listeners) {
      try {
        listener(event);
      } catch (error) {
        console.error('Gamepad event listener error:', error);
      }
    }
  }

  isStarted(): boolean {
    return this._pollingInterval !== null;
  }

  isManagerReady(): boolean {
    return this._manager !== null;
  }

  getGamepadCount(): number {
    try {
      const gamepads = navigator.getGamepads();
      let count = 0;
      for (const gp of gamepads) {
        if (gp) count++;
      }
      return count;
    } catch {
      return 0;
    }
  }

  getGamepadIndex(index: number): GamepadState | undefined {
    try {
      const gamepad = navigator.getGamepads()[index];
      if (!gamepad) return undefined;
      return this._toEventState(gamepad);
    } catch {
      return undefined;
    }
  }

  getGamepadDetail(index: number): {
    connected: boolean;
    id: string;
    mapping: string;
    buttons: number;
    axes: number;
  } | undefined {
    try {
      const gamepad = navigator.getGamepads()[index];
      if (!gamepad) return undefined;
      return {
        connected: gamepad.connected,
        id: gamepad.id,
        mapping: gamepad.mapping,
        buttons: gamepad.buttons.length,
        axes: gamepad.axes.length,
      };
    } catch {
      return undefined;
    }
  }
}
