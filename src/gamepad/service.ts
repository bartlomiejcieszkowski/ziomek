import type { GamepadEvent, GamepadEventListener, GamepadState } from './events.js';

// Type definition for gamepad-node (no @types package available)
type Manager = {
  on(event: string, listener: (data: any) => void): void;
  poll(): void;
  getGamepads(): GamepadState[];
  _destroyed?: boolean;
};

type GamepadModule = {
  GamepadManager: { new (): Manager };
  installNavigatorShim?: (options?: any) => Manager;
};

let cachedModule: GamepadModule | null = null;

async function getGamepadModule(): Promise<GamepadModule> {
  if (!cachedModule) {
    try {
      // SAFETY: gamepad-node has no TypeScript types; dynamic import returns
      // { GamepadManager, installNavigatorShim, ... } as named exports
      // We cast via unknown to avoid type mismatch between module structure
      const mod = await import('gamepad-node');
      // SAFETY: gamepad-node exports GamepadManager as a named export
      // The module structure has GamepadManager directly on the import object
      const gm = (mod as unknown as { GamepadManager?: { new (): Manager } }).GamepadManager;
      if (!gm) {
        // Try default export as fallback
        // SAFETY: gamepad-node may export via default in some bundlers
        const def = (mod as unknown as { default?: { GamepadManager?: { new (): Manager } } }).default;
        if (!def || !def.GamepadManager) {
          throw new Error('GamepadManager not found in gamepad-node module');
        }
        cachedModule = { GamepadManager: def.GamepadManager } as GamepadModule;
      } else {
        cachedModule = { GamepadManager: gm } as GamepadModule;
      }
    } catch {
      throw new Error('Failed to load gamepad-node module');
    }
  }
  return cachedModule;
}

export class GamepadService {
  private readonly _listeners = new Set<GamepadEventListener>();
  private _pollingInterval: ReturnType<typeof setInterval> | null = null;
  private readonly _pollingIntervalMs: number;
  private readonly _previousStates = new Map<number, ReadonlyArray<{ pressed: boolean; value: number }>>();
  private _manager: Manager | null = null;
  private _module: GamepadModule | null = null;

  constructor(pollingIntervalMs: number = 16) {
    this._pollingIntervalMs = pollingIntervalMs;
  }

  async start(): Promise<void> {
    try {
      this._module = await getGamepadModule();

      // Create GamepadManager directly (bypass installNavigatorShim which tries
      // to patch navigator.getGamepads — navigator doesn't exist in VS Code's
      // extension host environment)
      this._manager = new this._module!.GamepadManager();
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
      // Start polling loop — we call manager methods directly instead of
      // relying on navigator.getGamepads() which doesn't exist in VS Code
      this._previousStates.clear();
      this._pollingInterval = globalThis.setInterval(() => this._poll(), this._pollingIntervalMs);
    } catch (error) {
      console.error('GamepadService: failed to initialize gamepad-node:', error);
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
    if (!this._manager) return;
    try {
      // Call GamepadManager's methods directly instead of navigator.getGamepads()
      const gamepads = this._manager.getGamepads();

      for (const gamepad of gamepads) {
        if (!gamepad) continue;

        const previousButtons = this._previousStates.get(gamepad.index);
        const currentButtons = gamepad.buttons.map((b: any) => ({ pressed: b.pressed, value: b.value }));

        // Detect button transitions
        gamepad.buttons.forEach((btn: any, i: number) => {
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
        gamepad.axes.forEach((axis: number, i: number) => {
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
    if (!this._manager) return 0;
    try {
      const gamepads = this._manager.getGamepads();
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
    if (!this._manager) return undefined;
    try {
      const gamepad = this._manager.getGamepads()[index];
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
    if (!this._manager) return undefined;
    try {
      const gamepad = this._manager.getGamepads()[index];
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

  /** Get raw gamepad states from the manager for external consumers (avatar panel). */
  getGamepads(): GamepadState[] {
    if (!this._manager) return [];
    try {
      return this._manager.getGamepads();
    } catch {
      return [];
    }
  }
}
