import type { MappingConfig } from './config.js';
import { Logger } from '../logger.js';

export type ActionCallback = (action: string) => void;

export class MappingResolver {
  private _config: MappingConfig;
  private _callback: ActionCallback | null = null;
  private _logger: Logger | null = null;
  private _pressedButtons = new Set<number>();
  private _debounceMs = 80;
  private _lastActionTime = 0;
  private _axisThreshold = 0.5;
  private _axisDeadZone = 0.3;
  private _lastAxisValues: Map<number, number> = new Map();

  constructor(
    config: MappingConfig,
    options: {
      debounceMs?: number;
      axisThreshold?: number;
      axisDeadZone?: number;
      logger?: Logger;
    } = {},
  ) {
    this._config = config;
    this._logger = options.logger || null;
    this._debounceMs = options.debounceMs ?? 80;
    this._axisThreshold = options.axisThreshold ?? 0.5;
    this._axisDeadZone = options.axisDeadZone ?? 0.3;
  }

  onAction(callback: ActionCallback): void {
    this._callback = callback;
  }

  setConfig(config: MappingConfig): void {
    this._config = config;
  }

  handleButton(buttonIndex: number, pressed: boolean, _value: number): void {
    if (!this._callback) return;

    if (pressed) {
      // Debounce check
      const now = Date.now();
      if (now - this._lastActionTime < this._debounceMs) {
        return;
      }

      // Edge detection: only fire on new press
      if (this._pressedButtons.has(buttonIndex)) {
        return;
      }

      this._pressedButtons.add(buttonIndex);
      this._lastActionTime = now;

      const action = this._resolveActionForButton(buttonIndex);
      if (action) {
        this._callback(action);
      }
    } else {
      this._pressedButtons.delete(buttonIndex);
    }
  }

  handleAxis(axisIndex: number, value: number): void {
    if (!this._callback) return;

    // Apply dead zone
    const absValue = Math.abs(value);
    if (absValue < this._axisDeadZone) {
      this._lastAxisValues.delete(axisIndex);
      return;
    }

    // Check if crossed threshold
    const previousValue = this._lastAxisValues.get(axisIndex);
    if (previousValue !== undefined) {
      const previousSigned = Math.sign(previousValue);
      const currentSigned = Math.sign(value);

      // Only fire if the value is past threshold and direction hasn't changed
      if (absValue >= this._axisThreshold && previousSigned === currentSigned) {
        const action = this._resolveActionForAxis(axisIndex, currentSigned);
        if (action) {
          this._callback(action);
          // Don't update lastAxisValues to keep firing while stick is held
        }
      }
    }

    this._lastAxisValues.set(axisIndex, value);
  }

  clear(): void {
    this._pressedButtons.clear();
    this._lastAxisValues.clear();
  }

  private _resolveActionForButton(buttonIndex: number): string | null {
    // Check buttons map
    if (this._config.buttons[buttonIndex]) {
      return this._config.buttons[buttonIndex];
    }

    // Check D-pad (buttons 4=up, 5=right, 6=down, 7=left in standard mapping)
    const dpadMap: Record<number, 0 | 1 | 2 | 3> = {
      4: 0, // up
      5: 1, // right
      6: 2, // down
      7: 3, // left
    };

    if (dpadMap[buttonIndex] !== undefined) {
      return this._config.dpad[dpadMap[buttonIndex]];
    }

    return null;
  }

  private _resolveActionForAxis(
    axisIndex: number,
    direction: number,
  ): string | null {
    // Try config first
    const axisKey =
      axisIndex === 0
        ? 'yAxis'
        : axisIndex === 1
        ? 'xAxis'
        : axisIndex === 2
        ? 'yAxis'
        : 'xAxis';
    const configEntry = this._config.axes[axisKey];

    if (configEntry) {
      return configEntry[1];
    }

    // Default axis behavior when not configured
    if (axisIndex === 0 || axisIndex === 2) {
      // Y axis: negative = up, positive = down
      return direction < 0 ? 'scroll-up' : 'scroll-down';
    }
    // X axis: negative = left, positive = right
    return direction < 0 ? 'scroll-left' : 'scroll-right';
  }
}
