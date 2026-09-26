declare module 'gamepad-node' {
  export interface GamepadManager extends NodeJS.EventEmitter {
    startPolling(fps: number): void;
    poll(): void;
    getGamepads(): Array<{
      index: number;
      id: string;
      connected: boolean;
      buttons: Array<{ pressed: boolean; value: number }>;
      axes: number[];
      mapping: string;
      vibrationActuator?: any;
    }>;
    _destroyed?: boolean;
  }

  export interface InstallOptions {
    sdl?: any;
  }

  export function installNavigatorShim(options?: InstallOptions): GamepadManager;
}
