/**
 * Gamepad polling module — monitors connected gamepads and detects button presses.
 *
 * Runs in the browser (Pi extension context). Polls `navigator.getGamepads()`
 * at a configurable interval, tracks button state, and fires callbacks on
 * press/release events with debouncing.
 */

// ── Types ────────────────────────────────────────────────────────────────────

export interface GamepadButtonState {
  pressed: boolean;
  value: number;
}

export interface GamepadState {
  index: number;
  id: string;
  connected: boolean;
  buttons: GamepadButtonState[];
  axes: readonly number[];
}

export type GamepadButtonAction =
  | "listen_short"
  | "listen_long"
  | "cycle_responses"
  | "speak_last"
  | "next_response"
  | "prev_response"
  | "scroll_up"
  | "scroll_down"
  | "toggle_dashboard"
  | "show_status"
  | string;

export interface ButtonMap {
  [buttonName: string]: GamepadButtonAction;
}

export interface GamepadConfig {
  pollIntervalMs: number;
  debounceMs: number;
  buttonMap: ButtonMap;
}

export type GamepadButtonCallback = (
  buttonName: string,
  action: GamepadButtonAction,
  pressed: boolean,
) => void;

// ── Constants ────────────────────────────────────────────────────────────────

const DEFAULT_BUTTON_MAP: ButtonMap = {
  A: "listen_short",
  B: "cycle_responses",
  X: "listen_long",
  Y: "speak_last",
  LB: "next_response",
  RB: "prev_response",
  DPAD_UP: "scroll_up",
  DPAD_DOWN: "scroll_down",
  START: "toggle_dashboard",
  SELECT: "show_status",
};

const DEFAULT_CONFIG: GamepadConfig = {
  pollIntervalMs: 2000,
  debounceMs: 1000,
  buttonMap: DEFAULT_BUTTON_MAP,
};

// ── Button name mapping ──────────────────────────────────────────────────────

const BUTTON_INDEX_TO_NAME: Map<number, string> = new Map([
  [0, "A"],
  [1, "B"],
  [2, "X"],
  [3, "Y"],
  [4, "LB"],
  [5, "RB"],
  [6, "DPAD_UP"],
  [7, "DPAD_DOWN"],
  [8, "DPAD_LEFT"],
  [9, "DPAD_RIGHT"],
  [10, "START"],
  [11, "SELECT"],
]);

function indexToButtonName(index: number): string {
  return BUTTON_INDEX_TO_NAME.get(index) ?? `button_${index}`;
}

// ── Manager ──────────────────────────────────────────────────────────────────

export class GamepadManager {
  private config: GamepadConfig;
  private previousState: Map<number, boolean> = new Map();
  private lastPressTime: Map<number, number> = new Map();
  private intervalId: ReturnType<typeof setInterval> | null = null;
  private callbacks: GamepadButtonCallback[] = [];
  private currentGamepad: GamepadState | null = null;

  constructor(config: Partial<GamepadConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    if (config.buttonMap) {
      this.config.buttonMap = { ...DEFAULT_BUTTON_MAP, ...config.buttonMap };
    }
  }

  /**
   * Start polling the gamepad.
   */
  start(): void {
    if (this.intervalId) return;
    this.intervalId = setInterval(() => this.poll(), this.config.pollIntervalMs);
  }

  /**
   * Stop polling.
   */
  stop(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  /**
   * Check if polling is active.
   */
  isRunning(): boolean {
    return this.intervalId !== null;
  }

  /**
   * Register a button press/release callback.
   */
  onButton(callback: GamepadButtonCallback): void {
    this.callbacks.push(callback);
  }

  /**
   * Remove a button callback.
   */
  offButton(callback: GamepadButtonCallback): void {
    this.callbacks = this.callbacks.filter((cb) => cb !== callback);
  }

  /**
   * Get the current gamepad state.
   */
  getState(): GamepadState | null {
    return this.currentGamepad;
  }

  /**
   * Manually poll (useful for testing).
   */
  poll(): GamepadState | null {
    const gamepads = navigator.getGamepads();
    let gamepad: Gamepad | null = null;

    // Find the first connected gamepad
    for (let i = 0; i < gamepads.length; i++) {
      if (gamepads[i]?.connected) {
        gamepad = gamepads[i];
        break;
      }
    }

    if (!gamepad) {
      this.currentGamepad = null;
      return null;
    }

    const buttons: GamepadButtonState[] = gamepad.buttons.map((b) => ({
      pressed: b.pressed,
      value: b.value,
    }));

    const state: GamepadState = {
      index: gamepad.index,
      id: gamepad.id,
      connected: gamepad.connected,
      buttons,
      axes: gamepad.axes,
    };

    // Detect button presses
    for (let i = 0; i < buttons.length; i++) {
      const wasPressed = this.previousState.get(i) ?? false;
      const isPressed = buttons[i].pressed;

      if (isPressed && !wasPressed) {
        // Button pressed
        const now = Date.now();
        const lastPress = this.lastPressTime.get(i) ?? 0;
        const cooldown = now - lastPress;

        if (cooldown >= this.config.debounceMs) {
          this.lastPressTime.set(i, now);
          const buttonName = indexToButtonName(i);
          const action = this.config.buttonMap[buttonName] ?? buttonName;
          this.fireCallback(buttonName, action, true);
        }
      } else if (!isPressed && wasPressed) {
        // Button released
        this.fireCallback(
          indexToButtonName(i),
          this.config.buttonMap[indexToButtonName(i)] ?? indexToButtonName(i),
          false,
        );
      }

      this.previousState.set(i, isPressed);
    }

    this.currentGamepad = state;
    return state;
  }

  /**
   * Fire button callbacks.
   */
  private fireCallback(
    buttonName: string,
    action: GamepadButtonAction,
    pressed: boolean,
  ): void {
    for (const cb of this.callbacks) {
      try {
        cb(buttonName, action, pressed);
      } catch (error) {
        console.error(`[GamepadManager] callback error:`, error);
      }
    }
  }
}
