/**
 * Gamepad Avatar State Machine
 *
 * Drives avatar expressions based on gamepad input and VSCode state.
 * Uses expression preemption by intensity: higher-intensity expressions
 * always interrupt lower-intensity ones.
 */
import { Logger } from '../../logger.js';

const _logger = new Logger('debug');

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
  readonly message?: string;
  readonly messageExpiry?: number;
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
  private _currentExpressionType: 'idle' | 'button' | 'axis' | 'vscode' | 'external' | null = null;
  private _currentMessage: string | null = null;
  private _messageTimer: ReturnType<typeof setTimeout> | null = null;
  private _timedExpressionTimer: ReturnType<typeof setTimeout> | null = null;
  private _messageExpiryTimestamp: number = 0;

  update(input: GamepadAvatarInput): void {
    const pressedButtons: number[] = [];
    for (let i = 0; i < input.buttons.length; i++) {
      const pressed = input.buttons[i]?.pressed ?? false;
      if (pressed) pressedButtons.push(i);
      if (pressed && !this._prevButtons.has(i)) {
        _logger.debug('StateMachine', `Button press: btn[${i}], current=${this._current?.name ?? 'null'}, type=${this._currentExpressionType}`);
        this._prevButtons.add(i);
        this._tryStartButtonExpression(input, i);
        _logger.debug('StateMachine', `After button expr: _current=${this._current?.name ?? 'null'}`);
      }
      if (!pressed) {
        this._prevButtons.delete(i);
      }
    }
    if (pressedButtons.length > 0) {
      _logger.debug('StateMachine', `Pressed buttons: [${pressedButtons.join(', ')}]`);
    }
    this._updateLevelTriggers(input);
    if (!this._current) {
      _logger.debug('StateMachine', 'No current expression, starting idle');
      this._startExpression(this._findIdleExpression());
    }
    _logger.debug('StateMachine', `update() done: _current=${this._current?.name ?? 'null'}, type=${this._currentExpressionType}`);
  }

  tick(dtMs: number): ExpressionState {
    _logger.debug('StateMachine', `tick(dtMs=${dtMs}), _current=${this._current?.name ?? 'null'}, type=${this._currentExpressionType}`);
    if (!this._current) {
      _logger.debug('StateMachine', 'tick: no current, auto-starting idle');
      this._startExpression(this._findIdleExpression());
    }

    if (!this._current) {
      _logger.debug('StateMachine', 'tick: _current still null, returning static idle');
      // Check message expiry even when _current is null
      return {
        expressionName: 'idle',
        cycleIndex: 0,
        message: (this._messageExpiryTimestamp && Date.now() < this._messageExpiryTimestamp)
          ? (this._currentMessage ?? undefined)
          : undefined,
        messageExpiry: this._messageExpiryTimestamp || undefined,
      };
    }

    this._current.timer += dtMs;

    // Handle cycle advancement (finite cycle expressions)
    const frameDuration = this._current.cycleCount > 1
      ? this._current.def.durationMs / this._current.cycleCount
      : this._current.def.durationMs;

    while (this._current.timer >= frameDuration) {
      _logger.debug('StateMachine', `tick: frame complete for ${this._current.name}, frameDuration=${frameDuration}, cycleIndex=${this._current.cycleIndex}/${this._current.cycleCount}`);
      this._current.timer -= frameDuration;
      if (this._current.cycleCount > 1) {
        this._current.cycleIndex++;
        if (this._current.cycleIndex >= this._current.def.cycleCount) {
          // Cycle complete — transition
          const leftover = this._current.timer;
          _logger.debug('StateMachine', `tick: cycle complete for ${this._current.name}, type=${this._currentExpressionType}`);
          this._current = null;
          // Only level-triggered expressions keep their expression type
          if (this._currentExpressionType === 'button' || this._currentExpressionType === 'external') {
            this._currentExpressionType = null;
            _logger.debug('StateMachine', 'tick: cleared button type (edge-triggered)');
          }
          if (!this._currentExpressionType) {
            // Only idle can naturally transition to idle
            _logger.debug('StateMachine', 'tick: no type, transitioning to idle');
            this._startExpression(this._findIdleExpression());
            return this.tick(dtMs - leftover);
          }
          return this.tick(dtMs);
        }
      } else {
        // Single-cycle expression has ended
        const leftover = this._current.timer;
        _logger.debug('StateMachine', `tick: single-cycle expression ended for ${this._current.name}, type=${this._currentExpressionType}`);
        this._current = null;
        // Only level-triggered expressions keep their expression type
        if (this._currentExpressionType === 'button' || this._currentExpressionType === 'external') {
          this._currentExpressionType = null;
          _logger.debug('StateMachine', 'tick: cleared button type (edge-triggered)');
        }
        if (!this._currentExpressionType) {
          _logger.debug('StateMachine', 'tick: no type, transitioning to idle');
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
        _logger.debug('StateMachine', `tick: infinite expression ${this._current.name} no longer active`);
        this._current = null;
        this._currentExpressionType = null;
        return this.tick(dtMs);
      }
    }

    // Check message expiry
    const hasMessage = this._messageExpiryTimestamp && Date.now() < this._messageExpiryTimestamp;
    const message = hasMessage ? this._currentMessage : null;
    if (!hasMessage) {
      this._messageExpiryTimestamp = 0;
    }

    return {
      expressionName: this._current.name,
      cycleIndex: this._current.cycleIndex,
      message: message ?? undefined,
      messageExpiry: this._messageExpiryTimestamp || undefined,
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

    // Clear message-related state
    if (this._messageTimer) {
      clearTimeout(this._messageTimer);
      this._messageTimer = null;
    }
    if (this._timedExpressionTimer) {
      clearTimeout(this._timedExpressionTimer);
      this._timedExpressionTimer = null;
    }
    this._currentMessage = null;
    this._messageExpiryTimestamp = 0;
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

  /** Force-set the current expression (for external commands) */
  setExpression(expressionName: string, durationMs?: number): boolean {
    const expr = EXPRESSIONS.find(e => e.name === expressionName);
    if (!expr) {
      _logger.debug('StateMachine', `setExpression: expression '${expressionName}' not found`);
      return false;
    }
    this._startExpression(expr);
    this._currentExpressionType = 'external';

    // Clear any existing timed expression timer
    if (this._timedExpressionTimer) {
      clearTimeout(this._timedExpressionTimer);
      this._timedExpressionTimer = null;
    }

    // If duration provided, schedule auto-return to idle
    if (durationMs && durationMs > 0) {
      this._timedExpressionTimer = setTimeout(() => {
        this._currentExpressionType = null;
        this._timedExpressionTimer = null;
      }, durationMs);
    }

    _logger.debug('StateMachine', `setExpression: forced '${expressionName}'${durationMs ? ` (duration=${durationMs}ms)` : ''}`);
    return true;
  }

  /** Set an optional message to display with the current expression */
  setMessage(text?: string, durationMs: number = 10000): void {
    if (this._messageTimer) {
      clearTimeout(this._messageTimer);
      this._messageTimer = null;
    }
    if (text && text.trim()) {
      this._currentMessage = text.trim();
      if (durationMs > 0) {
        this._messageExpiryTimestamp = Date.now() + durationMs;
        this._messageTimer = setTimeout(() => {
          this._currentMessage = null;
          this._messageTimer = null;
          this._messageExpiryTimestamp = 0;
        }, durationMs);
      } else {
        this._messageExpiryTimestamp = 0;
      }
    } else {
      this._currentMessage = null;
      this._messageExpiryTimestamp = 0;
    }
    _logger.debug('StateMachine', `setMessage: ${this._currentMessage ?? 'cleared'} (expiry=${this._messageExpiryTimestamp || 'none'})`);
  }

  /** Get the current message */
  getMessage(): string | null {
    return this._currentMessage;
  }

  // ── Private helpers ──────────────────────────────────────────────────

  private _tryStartButtonExpression(input: GamepadAvatarInput, btnIndex: number): void {
    for (const expr of EXPRESSIONS) {
      for (const trigger of expr.triggers) {
        if (trigger.type === 'button' && trigger.condition(input)) {
          if (this._canStartExpression(expr)) {
            _logger.debug('StateMachine', `Button trigger matched: ${expr.name} (btn[${btnIndex}])`);
            this._startExpression(expr);
            this._currentExpressionType = 'button';
            _logger.debug('StateMachine', `Started expression: ${expr.name}`);
            return;
          } else {
            _logger.debug('StateMachine', `Button trigger rejected: ${expr.name} (intensity=${expr.intensity} vs current=${this._current?.def?.intensity ?? 'none'})`);
          }
        }
      }
    }
    _logger.debug('StateMachine', `No button expression matched for btn[${btnIndex}]`);
  }

  private _updateLevelTriggers(input: GamepadAvatarInput): void {
    const axisActive = Math.abs(input.axes[0]) > AXIS_THRESHOLD || Math.abs(input.axes[2]) > AXIS_THRESHOLD;

    _logger.debug('StateMachine', `_updateLevelTriggers: axisActive=${axisActive}, streaming=${input.streaming}, errorState=${input.errorState}`);

    if (axisActive !== this._prevAxisActive) {
      this._prevAxisActive = axisActive;
      if (axisActive) {
        if (this._tryStartExpressionByType('focused', input)) {
          this._currentExpressionType = 'axis';
          _logger.debug('StateMachine', 'Axis trigger: started focused');
        }
      } else if (this._currentExpressionType === 'axis') {
        _logger.debug('StateMachine', 'Axis trigger: cleared focused');
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
          _logger.debug('StateMachine', 'Streaming trigger: started thinking');
        }
      } else if (this._currentExpressionType === 'vscode' && this._current?.def.name === 'thinking') {
        _logger.debug('StateMachine', 'Streaming trigger: cleared thinking');
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
          _logger.debug('StateMachine', 'Error trigger: started dying');
        }
      } else if (this._currentExpressionType === 'vscode' && this._current?.def.name === 'dying') {
        _logger.debug('StateMachine', 'Error trigger: cleared dying');
        this._current = null;
        this._currentExpressionType = null;
      }
    }
  }

  private _tryStartExpressionByType(name: string, _input: GamepadAvatarInput): boolean {
    const expr = EXPRESSIONS.find(e => e.name === name);
    if (!expr) {
      _logger.debug('StateMachine', `_tryStartExpressionByType: expression '${name}' not found`);
      return false;
    }
    if (!this._canStartExpression(expr)) {
      _logger.debug('StateMachine', `_tryStartExpressionByType: rejected '${name}' - ${this._debugCanStartReason(expr)}`);
      return false;
    }
    _logger.debug('StateMachine', `_tryStartExpressionByType: starting '${name}'`);
    this._startExpression(expr);
    return true;
  }

  private _debugCanStartReason(expr: ExpressionDef): string {
    if (!this._current) return 'no current expression';
    if (expr.intensity > this._current.def.intensity) return `intensity ${expr.intensity} > ${this._current.def.intensity}`;
    const currentType = this._currentExpressionType;
    const newType = this._getTriggerType(expr);
    if (currentType === newType) return `same type (${currentType})`;
    return `intensity ${expr.intensity} <= ${this._current.def.intensity}`;
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

    const prevName = this._current?.name ?? 'null';
    this._current = {
      def,
      name,
      cycleIndex: 0,
      cycleCount: def.cycleCount,
      timer: 0,
    };
    _logger.debug('StateMachine', `_startExpression: ${prevName} → ${name} (intensity=${def.intensity}, duration=${def.durationMs})`);
  }
}
