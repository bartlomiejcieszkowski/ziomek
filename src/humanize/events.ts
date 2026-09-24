export interface GamepadState {
  readonly id: string;
  readonly index: number;
  readonly connected: boolean;
  readonly buttons: ReadonlyArray<GamepadButton>;
  readonly axes: ReadonlyArray<number>;
  readonly mapping: string;
}

export interface GamepadButton {
  readonly pressed: boolean;
  readonly value: number;
}

export interface GamepadConnectedEvent {
  readonly type: 'gamepadconnected';
  readonly gamepad: GamepadState;
}

export interface GamepadDisconnectedEvent {
  readonly type: 'gamepaddisconnected';
  readonly gamepad: GamepadState;
}

export interface GamepadButtonEvent {
  readonly type: 'gamepadbutton';
  readonly index: number;
  readonly buttonIndex: number;
  readonly pressed: boolean;
  readonly value: number;
}

export interface GamepadAxisEvent {
  readonly type: 'gamepadaxis';
  readonly index: number;
  readonly axisIndex: number;
  readonly value: number;
}

export type GamepadEvent =
  | GamepadConnectedEvent
  | GamepadDisconnectedEvent
  | GamepadButtonEvent
  | GamepadAxisEvent;

export type GamepadEventListener = (event: GamepadEvent) => void;
