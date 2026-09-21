/**
 * Gamepad Avatar State Machine
 *
 * Drives avatar expressions based on gamepad input and VSCode state.
 * Uses expression preemption by intensity: higher-intensity expressions
 * always interrupt lower-intensity ones.
 */

export interface GamepadAvatarInput {
  buttons: ReadonlyArray<{ pressed: boolean; value: number }>;
  axes: ReadonlyArray<number>;
  connected: boolean;
  streaming: boolean;
  chatFocused: boolean;
  errorState: boolean;
}

export interface ExpressionState {
  readonly expressionName: string;
  readonly cycleIndex: number;
}

export interface Skin {
  readonly id: string;
  readonly name: string;
  readonly spriteWidth: number;
  readonly spriteHeight: number;
  readonly frameWidth: number;
  readonly frameHeight: number;
  getFrameRow(expressionName: string, cycleIndex: number): number;
  getFrameCount(expressionName: string): number;
  getExpressionNames(): string[];
  getSpriteBuffer(): Buffer;
}

interface ExpressionDef {
  name: string;
  cycleCount: number;
  durationMs: number;
  intensity: number;
  triggers: Array<{
    type: 'button' | 'axis' | 'vscode' | 'idle';
    condition: (input: GamepadAvatarInput) => boolean;
  }>;
}

const EXPRESSIONS: ExpressionDef[] = [
  { name: 'idle', cycleCount: 60, durationMs: 999999999, intensity: 0, triggers: [{ type: 'idle', condition: () => true }] },
  { name: 'bored', cycleCount: 3, durationMs: 900, intensity: 0, triggers: [{ type: 'idle', condition: () => true }] },
  { name: 'happy', cycleCount: 1, durationMs: 500, intensity: 1, triggers: [{ type: 'button', condition: (inp) => inp.buttons[0]?.pressed === true }] },
  { name: 'surprised', cycleCount: 1, durationMs: 300, intensity: 2, triggers: [{ type: 'button', condition: (inp) => inp.buttons[1]?.pressed === true }] },
  { name: 'curious', cycleCount: 1, durationMs: 400, intensity: 1, triggers: [{ type: 'button', condition: (inp) => inp.buttons[2]?.pressed === true }] },
  { name: 'looking', cycleCount: 1, durationMs: 200, intensity: 1, triggers: [{ type: 'button', condition: (inp) => inp.buttons[12]?.pressed || inp.buttons[13]?.pressed || inp.buttons[14]?.pressed || inp.buttons[15]?.pressed }] },
  { name: 'focused', cycleCount: 1, durationMs: 999999999, intensity: 2, triggers: [{ type: 'axis', condition: (inp) => Math.abs(inp.axes[0]) > 0.3 || Math.abs(inp.axes[2]) > 0.3 }] },
  { name: 'thinking', cycleCount: 1, durationMs: 999999999, intensity: 1, triggers: [{ type: 'vscode', condition: (inp) => inp.streaming }] },
  { name: 'dying', cycleCount: 2, durationMs: 2000, intensity: 3, triggers: [{ type: 'vscode', condition: (inp) => inp.errorState }] },
];

const IDLE_SEQUENCE = ['bored', 'bored', 'bored', 'neutral', 'neutral', 'neutral'];
const AXIS_THRESHOLD = 0.3;

interface CurrentState {
  def: ExpressionDef;
  name: string;
  cycleIndex: number;
  timer: number;
  cycleCount: number;
}

export class AvatarStateMachine {
  private _current: CurrentState | null = null;
  private _idleIndex = 0;
  private _prevButtons = new Set<number>();
  private _prevAxisActive = false;
  private _prevStreaming = false;
  private _prevErrorState = false;
  private _currentExpressionType: 'idle' | 'button' | 'axis' | 'vscode' | null = null;

  update(input: GamepadAvatarInput): void {
    for (let i = 0; i < input.buttons.length; i++) {
      const pressed = input.buttons[i]?.pressed ?? false;
      if (pressed && !this._prevButtons.has(i)) {
        this._prevButtons.add(i);
        this._tryStartButtonExpression(input, i);
      }
      if (!pressed) {
        this._prevButtons.delete(i);
      }
    }
    this._updateLevelTriggers(input);
    if (!this._current) {
      this._startExpression(this._findIdleExpression());
    }
  }

  tick(dtMs: number): ExpressionState {
    if (!this._current) {
      return { expressionName: 'idle', cycleIndex: 0 };
    }

    this._current.timer += dtMs;

    // Handle cycle advancement (finite cycle expressions)
    const frameDuration = this._current.cycleCount > 1
      ? this._current.def.durationMs / this._current.cycleCount
      : this._current.def.durationMs;

    while (this._current.timer >= frameDuration) {
      this._current.timer -= frameDuration;
      if (this._current.cycleCount > 1) {
        this._current.cycleIndex++;
        if (this._current.cycleIndex >= this._current.def.cycleCount) {
          // Cycle complete — transition
          const leftover = this._current.timer;
          this._current = null;
          // Only level-triggered expressions keep their expression type
          if (this._currentExpressionType === 'button') {
            this._currentExpressionType = null;
          }
          if (!this._currentExpressionType) {
            // Only idle can naturally transition to idle
            this._startExpression(this._findIdleExpression());
            return this.tick(dtMs - leftover);
          }
          return this.tick(dtMs);
        }
      } else {
        // Single-cycle expression has ended
        const leftover = this._current.timer;
        this._current = null;
        // Only level-triggered expressions keep their expression type
        if (this._currentExpressionType === 'button') {
          this._currentExpressionType = null;
        }
        if (!this._currentExpressionType) {
          this._startExpression(this._findIdleExpression());
          return this.tick(dtMs - leftover);
        }
        return this.tick(dtMs);
      }
    }

    // Handle infinite duration (level-triggered expressions)
    if (this._current.def.durationMs >= 999999999) {
      // Infinite — check if trigger is still active
      if (!this._isTriggerActive(this._current.def)) {
        this._current = null;
        this._currentExpressionType = null;
        return this.tick(dtMs);
      }
    }

    return {
      expressionName: this._current.name,
      cycleIndex: this._current.cycleIndex,
    };
  }

  reset(): void {
    this._current = null;
    this._idleIndex = 0;
    this._prevButtons.clear();
    this._prevAxisActive = false;
    this._prevStreaming = false;
    this._prevErrorState = false;
    this._currentExpressionType = null;
  }

  getCurrentState(): ExpressionState {
    return {
      expressionName: this._current?.name ?? 'idle',
      cycleIndex: this._current?.cycleIndex ?? 0,
    };
  }

  getExpressionNames(): string[] {
    return EXPRESSIONS.map(e => e.name);
  }

  getDefaultExpression(): string {
    return 'idle';
  }

  // ── Private helpers ──────────────────────────────────────────────────

  private _tryStartButtonExpression(input: GamepadAvatarInput, _btnIndex: number): void {
    for (const expr of EXPRESSIONS) {
      for (const trigger of expr.triggers) {
        if (trigger.type === 'button' && trigger.condition(input)) {
          if (this._canStartExpression(expr)) {
            this._startExpression(expr);
            this._currentExpressionType = 'button';
            return;
          }
        }
      }
    }
  }

  private _updateLevelTriggers(input: GamepadAvatarInput): void {
    const axisActive = Math.abs(input.axes[0]) > AXIS_THRESHOLD || Math.abs(input.axes[2]) > AXIS_THRESHOLD;

    if (axisActive !== this._prevAxisActive) {
      this._prevAxisActive = axisActive;
      if (axisActive) {
        if (this._tryStartExpressionByType('focused', input)) {
          this._currentExpressionType = 'axis';
        }
      } else if (this._currentExpressionType === 'axis') {
        this._current = null;
        this._currentExpressionType = null;
      }
    }

    // Streaming trigger
    if (input.streaming !== this._prevStreaming) {
      this._prevStreaming = input.streaming;
      if (input.streaming) {
        if (this._tryStartExpressionByType('thinking', input)) {
          this._currentExpressionType = 'vscode';
        }
      } else if (this._currentExpressionType === 'vscode' && this._current?.def.name === 'thinking') {
        this._current = null;
        this._currentExpressionType = null;
      }
    }

    // Error state trigger
    if (input.errorState !== this._prevErrorState) {
      this._prevErrorState = input.errorState;
      if (input.errorState) {
        if (this._tryStartExpressionByType('dying', input)) {
          this._currentExpressionType = 'vscode';
        }
      } else if (this._currentExpressionType === 'vscode' && this._current?.def.name === 'dying') {
        this._current = null;
        this._currentExpressionType = null;
      }
    }
  }

  private _tryStartExpressionByType(name: string, _input: GamepadAvatarInput): boolean {
    const expr = EXPRESSIONS.find(e => e.name === name);
    if (!expr) return false;
    if (this._canStartExpression(expr)) {
      this._startExpression(expr);
      return true;
    }
    return false;
  }

  private _findIdleExpression(): string {
    return IDLE_SEQUENCE[this._idleIndex % IDLE_SEQUENCE.length];
  }

  private _canStartExpression(expr: ExpressionDef): boolean {
    if (!this._current) return true;
    if (expr.intensity > this._current.def.intensity) return true;
    const currentType = this._currentExpressionType;
    const newType = this._getTriggerType(expr);
    if (currentType === newType) return false;
    if (currentType === 'idle' && (newType === 'button' || newType === 'axis' || newType === 'vscode')) return true;
    return false;
  }

  private _getTriggerType(expr: ExpressionDef): string {
    for (const t of expr.triggers) {
      if (t.type !== 'idle') return t.type;
    }
    return 'idle';
  }

  private _isTriggerActive(_def: ExpressionDef): boolean {
    // Level-triggered expressions stay active until the trigger changes.
    // Lifecycle is handled by _updateLevelTriggers, so return true here
    // to prevent unnecessary transitions during tick().
    return true;
  }

  private _startExpression(nameOrDef: string | ExpressionDef): void {
    let def: ExpressionDef;
    let name: string;

    if (typeof nameOrDef === 'string') {
      def = EXPRESSIONS.find(e => e.name === nameOrDef) ?? EXPRESSIONS[0];
      name = nameOrDef;
    } else {
      def = nameOrDef;
      name = nameOrDef.name;
    }

    // For cycle expressions (bored → neutral), advance the idle index
    if (name === 'bored' || name === 'neutral') {
      this._idleIndex++;
      const sequence = IDLE_SEQUENCE;
      name = sequence[this._idleIndex % sequence.length];
      def = EXPRESSIONS.find(e => e.name === name) ?? EXPRESSIONS[0];
    }

    this._current = {
      def,
      name,
      cycleIndex: 0,
      cycleCount: def.cycleCount,
      timer: 0,
    };
  }
}
