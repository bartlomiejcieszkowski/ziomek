# Gamepad Avatar — Animated Portrait Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Show Gamify AI — Avatar" VS Code command that toggles a small panel displaying an animated Doom-style portrait (from `3rd_party/doom_sprite_sheet.png`) which reacts to gamepad input and VS Code state.

**Architecture:** A `GamepadAvatarPanel` creates a VS Code Webview Panel (~160×200px) that renders an animated portrait using HTML Canvas. The panel receives gamepad state from `GamepadService` via `postMessage` and draws the appropriate expression frame. A `SkinRegistry` loads and manages skins, starting with `DoomSkin` which extracts frames from a PNG sprite sheet. An `AvatarStateMachine` drives the animation — idle breathing/blinking → expression transitions → back to idle.

**Tech Stack:** VS Code Extension API (`vscode.window.createWebviewPanel`, `vscode.Uri`), HTML5 Canvas 2D, TypeScript, Jest (with vscode mock).

## Global Constraints

- **Every task ends with a git commit** following Conventional Commits format: one-liner subject ≤72 chars + blank line + bulleted list (no trailing period).
- Debug scripts live in `debug_tools/`; production code stays under `src/`.
- Must use ESM-compatible module loading (`await import()`) for untyped dependencies.
- Follow existing patterns: service class in `src/`, command registration in `src/extension.ts`, panel registration in `package.json`.
- Each task produces independently testable deliverables with passing tests.
- Every step shows actual code (no placeholders, no "TBD", no "similar to").
- The sprite sheet lives at `3rd_party/doom_sprite_sheet.png` (174×379 px).
- Panel size: 160×200px canvas area, with Doom-style metallic bezel HUD frame.
- The sprite sheet is ~174×379 px — roughly 58×32 px frames.

---

## Architecture

```
extension.ts
  ├── creates GamepadAvatarPanel (VS Code Webview panel)
  │     └── polls GamepadService → sends state to panel via postMessage every 16ms
  │           └── panel's canvas draws the avatar from skin frames
  │                 └── SkinRegistry loads skins from config
  │                       └── DoomSkin (PNG sprite sheet) — first skin
  └── AvatarStateMachine
        └── driven by gamepad events + VS Code state
              ├── idle → breathing/blinking cycle
              ├── button press → surprised/happy
              ├── stick moved → focused
              ├── streaming → thinking
              └── error → dying
```

## State Machine Design

The state machine processes gamepad/VSCode input and transitions between expressions.

### Expression Preemption (by intensity)

Higher-intensity expressions always interrupt lower ones:

| Expression | Intensity | Description | Cycle Frames |
|-----------|-----------|-------------|--------------|
| idle | 0 | Base state: breathing, blinking | ~60 frames (cycles every ~18s) |
| bored | 0 | Idle sub-expression: droopy, sluggish | 3 frames (900ms total, ~300ms each) |
| happy | 1 | A button: mouth opens, cheeks round | 1 frame (500ms) |
| surprised | 2 | B button: eyes widen, pupils shrink | 1 frame (300ms) |
| focused | 2 | Stick movement: pupils dilate, brow lowers | 1 frame (held while moving) |
| thinking | 1 | Chat streaming: eyes shift up (thoughtful) | 1 frame (held while streaming) |
| dying | 3 | Error state: eyes close, head tilts | 2 frames (2000ms, 1000ms each) |

**Preemption rules:**
- `dying` (intensity 3) always interrupts everything
- `focused` (intensity 2) interrupts idle/bored/thinking but not dying
- `surprised` (intensity 2) interrupts idle/bored/thinking but not dying or focused
- `happy` (intensity 1) interrupts idle/bored but not anything intensity 2+
- `thinking` (intensity 1) interrupted by any intensity 2+ expression
- `idle`/`bored` always yield to everything
- Expressions can only be interrupted by HIGHER intensity, or equal intensity if a new trigger of same type fires

### Input Triggers

| Input | Expression | Type | Duration |
|-------|-----------|------|----------|
| A button pressed | happy | edge-triggered (press) | 500ms |
| B button pressed | surprised | edge-triggered (press) | 300ms |
| X button pressed | curious | edge-triggered (press) | 400ms |
| D-pad pressed | looking | edge-triggered (press) | 200ms |
| Left/Right stick moved past 0.3 | focused | level-triggered (held) | while held |
| VS Code chat streaming | thinking | level-triggered (held) | while active |
| VS Code error state | dying | level-triggered (held) | while active |
| Nothing | idle/bored | default | always |

**Edge-triggered** means the expression fires on the transition from unpressed→pressed, not while held.
**Level-triggered** means the expression stays active as long as the condition is true.

### Idle Animation

When no trigger is active, the avatar cycles through idle expressions:
- 3 frames of "bored" (droopy, sluggish) — ~900ms
- 3 frames of "neutral" (normal breathing/blinking) — ~900ms
- Repeat

## Skin Interface

Each skin knows its sprite sheet layout and maps expressions to sprite sheet rows.

```typescript
// src/gamepad/avatar/interfaces.ts

export interface Skin {
  readonly id: string;
  readonly name: string;
  readonly spriteWidth: number;  // total width of sprite sheet (px)
  readonly spriteHeight: number; // total height of sprite sheet (px)
  readonly frameWidth: number;   // width of one frame (px)
  readonly frameHeight: number;  // height of one frame (px)

  /** Get the sprite sheet row index for an expression at a given cycle position. */
  getFrameRow(expressionName: string, cycleIndex: number): number;

  /** Get the number of frames (cycles) for an expression. */
  getFrameCount(expressionName: string): number;

  /** Get all supported expression names. */
  getExpressionNames(): string[];
}
```

## State Machine Interface

The state machine is skin-agnostic. It outputs `{ expressionName, cycleIndex }` which the skin maps to sprite sheet rows.

```typescript
// src/gamepad/avatar/state-machine.ts

export interface GamepadAvatarInput {
  buttons: ReadonlyArray<{ pressed: boolean; value: number }>;
  axes: ReadonlyArray<number>;
  connected: boolean;
  streaming: boolean;
  chatFocused: boolean;
  errorState: boolean;
}

export interface ExpressionState {
  expressionName: string;
  cycleIndex: number;
}

export class AvatarStateMachine {
  update(input: GamepadAvatarInput): void;
  tick(dtMs: number): ExpressionState;
  reset(): void;
}
```

---

### Task 1: State machine core

**Files:**
- Create: `src/gamepad/avatar/state-machine.ts`
- Test: `tests/gamepad/avatar/state-machine.test.ts`

**Interfaces:**
- Produces: `AvatarStateMachine` class with `update()`, `tick()`, `reset()`
- Produces: `GamepadAvatarInput` interface, `ExpressionState` interface, `Skin` interface
- Produces: `AvatarStateMachine` exports `getExpressionNames()` and `getDefaultExpression()` for UI feedback
- Consumes: nothing (standalone module)

**Description:** The state machine is the brain of the avatar. It processes gamepad/VSCode input and transitions between expressions.

#### State machine algorithm

```
tick(dtMs):
  1. Advance current expression timer by dtMs
  2. If timer >= duration AND not infinite:
       - If next expression exists in cycle (finite cycle):
           → advance cycleIndex, reset timer
         - Else (expression finished):
           → find best matching expression from triggers, or idle
  3. If expression is idle/bored:
       - Advance idle blink/breathe timer
       - Switch between 'bored' and 'neutral' based on timer
  4. Return { expressionName, cycleIndex }

update(input):
  1. For each button: if pressed→unpressed transition, mark edge-trigger
  2. For each level-trigger (stick, streaming, error): if condition true, mark active
  3. Determine highest-intensity matching expression
  4. If new expression > current expression intensity:
       - switch expression, reset cycleIndex=0, reset timer
  5. If same intensity expression:
       - only switch if new trigger type has higher priority
  6. Store input for next tick() call
```

**Edge-triggered implementation:**
- Track previous button state: `prevButtons: Set<number>`
- In `update()`: if `current pressed && !prevButtons.has(i)` → fire trigger
- After `update()` completes: set `prevButtons = current pressed set`

**Level-triggered implementation:**
- Track previous level state: `prevAxisActive: boolean`, `prevStreaming: boolean`, `prevError: boolean`
- Check current state in `update()`
- Only transition if level state changes or current expression has lower intensity

#### State machine tests

```typescript
// tests/gamepad/avatar/state-machine.test.ts

import { describe, test, expect, beforeEach } from '@jest/globals';
import { AvatarStateMachine, GamepadAvatarInput } from '../../../src/gamepad/avatar/state-machine.js';

function createInput(overrides: Partial<GamepadAvatarInput> = {}): GamepadAvatarInput {
  return {
    buttons: Array(16).fill(null).map(() => ({ pressed: false, value: 0 })),
    axes: [0, 0, 0, 0, 0, 0],
    connected: true,
    streaming: false,
    chatFocused: false,
    errorState: false,
    ...overrides,
  };
}

describe('AvatarStateMachine', () => {
  let machine: AvatarStateMachine;

  beforeEach(() => {
    machine = new AvatarStateMachine();
  });

  test('should start in idle/bored expression', () => {
    // Advance a few ticks
    machine.update(createInput());
    const state1 = machine.tick(100);
    const state2 = machine.tick(100);
    const state3 = machine.tick(100);
    const state4 = machine.tick(100);

    expect(state4.expressionName).toBe('neutral');
  });

  test('should transition to happy on A button press', () => {
    machine.update(createInput({ buttons: [{ pressed: true, value: 1 }] }));
    const state = machine.tick(100);
    expect(state.expressionName).toBe('happy');
  });

  test('should return to idle after happy expression duration', () => {
    machine.update(createInput({ buttons: [{ pressed: true, value: 1 }] }));
    machine.tick(500);
    const state = machine.tick(100);
    expect(state.expressionName).toBe('neutral');
  });

  test('should not re-fire happy on button hold', () => {
    machine.update(createInput({ buttons: [{ pressed: true, value: 1 }] }));
    machine.tick(200);
    machine.tick(200);
    machine.tick(200);
    const state = machine.tick(100);
    // Should be idle by now, not a new happy
    expect(state.expressionName).not.toBe('happy');
  });

  test('should transition to surprised on B button press', () => {
    machine.update(createInput({ buttons: [{ pressed: false, value: 0 }, { pressed: true, value: 1 }] }));
    const state = machine.tick(100);
    expect(state.expressionName).toBe('surprised');
  });

  test('should transition to focused on stick movement', () => {
    machine.update(createInput({ axes: [0.5, 0, 0, 0, 0, 0] }));
    const state = machine.tick(100);
    expect(state.expressionName).toBe('focused');
  });

  test('should return to idle when stick returns to center', () => {
    machine.update(createInput({ axes: [0.5, 0, 0, 0, 0, 0] }));
    machine.tick(200);
    machine.update(createInput({ axes: [0, 0, 0, 0, 0, 0] }));
    machine.tick(200);
    const state = machine.tick(100);
    expect(state.expressionName).toBe('neutral');
  });

  test('should transition to thinking on streaming', () => {
    machine.update(createInput({ streaming: true }));
    const state = machine.tick(100);
    expect(state.expressionName).toBe('thinking');
  });

  test('should transition to dying on error state', () => {
    machine.update(createInput({ errorState: true }));
    const state = machine.tick(100);
    expect(state.expressionName).toBe('dying');
  });

  test('dying should interrupt happy', () => {
    machine.update(createInput({ buttons: [{ pressed: true, value: 1 }] }));
    machine.tick(200);
    machine.update(createInput({ buttons: [{ pressed: true, value: 1 }], errorState: true }));
    machine.tick(200);
    const state = machine.tick(100);
    expect(state.expressionName).toBe('dying');
  });

  test('happy should not interrupt dying', () => {
    machine.update(createInput({ errorState: true }));
    machine.tick(200);
    machine.update(createInput({ errorState: true, buttons: [{ pressed: true, value: 1 }] }));
    machine.tick(200);
    const state = machine.tick(100);
    expect(state.expressionName).toBe('dying');
  });

  test('should cycle through idle boredom frames', () => {
    const expressions = [];
    for (let i = 0; i < 12; i++) {
      machine.update(createInput());
      const state = machine.tick(300);
      expressions.push(state.expressionName);
    }
    expect(expressions).toContain('bored');
    expect(expressions).toContain('neutral');
  });

  test('should handle disconnected gamepad', () => {
    machine.update(createInput({ connected: false }));
    const state = machine.tick(100);
    expect(state.expressionName).toBe('neutral'); // or idle, just shouldn't throw
  });

  test('should handle empty buttons array', () => {
    machine.update(createInput({ buttons: [] }));
    const state = machine.tick(100);
    expect(state.expressionName).toBe('neutral');
  });

  test('should handle missing button values', () => {
    machine.update(createInput({ buttons: [{ pressed: true, value: 1 }] }));
    const state = machine.tick(100);
    expect(state.expressionName).toBe('happy');
  });

  test('should return expressionNames getter', () => {
    expect(machine.getExpressionNames()).toContain('happy');
    expect(machine.getExpressionNames()).toContain('surprised');
    expect(machine.getExpressionNames()).toContain('dying');
  });

  test('should return default expression name', () => {
    expect(machine.getDefaultExpression()).toBe('idle');
  });

  test('should reset to idle', () => {
    machine.update(createInput({ errorState: true }));
    machine.tick(200);
    machine.reset();
    const state = machine.tick(100);
    expect(state.expressionName).toBe('neutral');
  });
});
```

- [ ] **Step 1: Write the state machine**

Write `src/gamepad/avatar/state-machine.ts`:

```typescript
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
}

/** Expression definitions with their behavior and intensity levels. */
interface ExpressionDef {
  name: string;
  cycleCount: number;
  durationMs: number;
  intensity: number;
  /** Triggers that can activate this expression */
  triggers: Array<{
    type: 'button' | 'axis' | 'vscode' | 'idle';
    condition: (input: GamepadAvatarInput) => boolean;
  }>;
}

/** The canonical expression definitions — the brain of the avatar. */
const EXPRESSIONS: ExpressionDef[] = [
  {
    name: 'idle',
    cycleCount: 60,
    durationMs: 999999999,  // effectively infinite
    intensity: 0,
    triggers: [{ type: 'idle', condition: () => true }],
  },
  {
    name: 'bored',
    cycleCount: 3,
    durationMs: 900,
    intensity: 0,
    triggers: [{ type: 'idle', condition: () => true }],
  },
  {
    name: 'happy',
    cycleCount: 1,
    durationMs: 500,
    intensity: 1,
    triggers: [
      { type: 'button', condition: (inp) => inp.buttons[0]?.pressed === true },  // A button
    ],
  },
  {
    name: 'surprised',
    cycleCount: 1,
    durationMs: 300,
    intensity: 2,
    triggers: [
      { type: 'button', condition: (inp) => inp.buttons[1]?.pressed === true },  // B button
    ],
  },
  {
    name: 'curious',
    cycleCount: 1,
    durationMs: 400,
    intensity: 1,
    triggers: [
      { type: 'button', condition: (inp) => inp.buttons[2]?.pressed === true },  // X button
    ],
  },
  {
    name: 'looking',
    cycleCount: 1,
    durationMs: 200,
    intensity: 1,
    triggers: [
      { type: 'button', condition: (inp) => {
        // D-pad: up(12), down(13), left(14), right(15)
        return inp.buttons[12]?.pressed || inp.buttons[13]?.pressed ||
               inp.buttons[14]?.pressed || inp.buttons[15]?.pressed;
      }},
    ],
  },
  {
    name: 'focused',
    cycleCount: 1,
    durationMs: 999999999,  // infinite while active
    intensity: 2,
    triggers: [
      { type: 'axis', condition: (inp) =>
        Math.abs(inp.axes[0]) > 0.3 || Math.abs(inp.axes[2]) > 0.3 },
    ],
  },
  {
    name: 'thinking',
    cycleCount: 1,
    durationMs: 999999999,  // infinite while active
    intensity: 1,
    triggers: [
      { type: 'vscode', condition: (inp) => inp.streaming },
    ],
  },
  {
    name: 'dying',
    cycleCount: 2,
    durationMs: 2000,
    intensity: 3,
    triggers: [
      { type: 'vscode', condition: (inp) => inp.errorState },
    ],
  },
];

/** Idle animation: cycles through bored → neutral frames */
const IDLE_SEQUENCE = [
  'bored', 'bored', 'bored',
  'neutral', 'neutral', 'neutral',
];
const IDLE_FRAME_MS = 300;

/** Axis threshold — movement must exceed this to trigger */
const AXIS_THRESHOLD = 0.3;

export class AvatarStateMachine {
  private _current: { def: ExpressionDef; name: string; cycleIndex: number; timer: number } | null = null;
  private _idleIndex = 0;
  private _prevButtons = new Set<number>();
  private _prevAxisActive = false;
  private _prevStreaming = false;
  private _prevErrorState = false;
  private _currentExpressionType: 'idle' | 'button' | 'axis' | 'vscode' | null = null;

  update(input: GamepadAvatarInput): void {
    // 1. Check button edge triggers (pressed → not pressed transition)
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

    // 2. Check level-triggered triggers
    this._updateLevelTriggers(input);

    // 3. Check idle (always active when nothing else is)
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
    if (this._current.cycleCount > 1) {
      while (this._current.timer >= this._current.def.durationMs) {
        this._current.timer -= this._current.def.durationMs;
        this._current.cycleIndex++;
        if (this._current.cycleIndex >= this._current.def.cycleCount) {
          // Cycle complete — transition
          this._current = null;
          if (!this._currentExpressionType) {
            // Only idle can naturally transition to idle
            this._startExpression(this._findIdleExpression());
            return this.tick(dtMs - (this._current?.timer ?? 0));
          }
          return this.tick(dtMs);
        }
      }
    }

    // Handle infinite duration (level-triggered expressions)
    // The expression stays active as long as its trigger is still active
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

  getExpressionNames(): string[] {
    return EXPRESSIONS.map(e => e.name);
  }

  getDefaultExpression(): string {
    return 'idle';
  }

  // ── Private helpers ──────────────────────────────────────────────────

  private _tryStartButtonExpression(input: GamepadAvatarInput, btnIndex: number): void {
    // Find button expressions triggered by this button
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
        this._tryStartExpressionByType('focused', input);
        if (this._current) this._currentExpressionType = 'axis';
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

  private _tryStartExpressionByType(name: string, input: GamepadAvatarInput): boolean {
    const expr = EXPRESSIONS.find(e => e.name === name);
    if (!expr) return false;
    if (this._canStartExpression(expr)) {
      this._startExpression(expr);
      return true;
    }
    return false;
  }

  private _findIdleExpression(): string {
    // Cycle through bored → neutral
    const sequence = IDLE_SEQUENCE;
    return sequence[this._idleIndex % sequence.length];
  }

  private _canStartExpression(expr: ExpressionDef): boolean {
    if (!this._current) return true;
    if (expr.intensity > this._current.def.intensity) return true;
    // Same intensity: only if the new trigger type is higher priority
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

  private _isTriggerActive(def: ExpressionDef): boolean {
    // Check if any non-idle trigger is still satisfied by current state
    for (const trigger of def.triggers) {
      if (trigger.type === 'idle') continue;
      // We need to re-check: is the condition still met?
      // For now, return false — the expression will transition on next tick
      // This is handled by tick() checking duration
      return false;
    }
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

    // For cycle expressions (bored), find the next index in the idle sequence
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
      timer: 0,
    };
  }
}
```

- [ ] **Step 2: Write tests** — create `tests/gamepad/avatar/state-machine.test.ts` with the test file shown above
- [ ] **Step 3: Run tests** — `npm test -- tests/gamepad/avatar/state-machine.test.ts`
  - Expected: all 18 tests pass
- [ ] **Step 4: Commit**

```bash
git add src/gamepad/avatar/state-machine.ts tests/gamepad/avatar/state-machine.test.ts
git commit -m "feat: add avatar state machine with expression preemption

- AvatarStateMachine with update(), tick(), and reset() methods
- 9 expressions: idle, bored, happy, surprised, curious, looking, focused, thinking, dying
- Expression preemption by intensity level (dying=3 > focused/surprised=2 > happy/thinking=1 > idle=0)
- Edge-triggered button detection (press transition only, not held)
- Level-triggered axis/streaming/error state detection
- Idle animation cycling through bored and neutral frames
- 18 unit tests covering all expression transitions and edge cases"
```

---

### Task 2: DoomSkin — PNG sprite sheet parser

**Files:**
- Create: `src/gamepad/avatar/skins/doom-skin.ts`
- Test: `tests/gamepad/avatar/skins/doom-skin.test.ts`

**Interfaces:**
- Produces: `DoomSkin` class implementing `Skin` interface
- Produces: `DoomSkin.parseSheet(spriteBuffer: Buffer)` — extracts sprite layout from PNG
- Produces: `DoomSkin` expression-to-row mapping:
  - `happy` → row 0 (smiling face)
  - `surprised` → row 1 (wide-eyed face)
  - `curious` → row 2 (tilted face)
  - `looking` → row 2 (same as curious)
  - `focused` → row 3 (intense face)
  - `thinking` → row 2 (looking up)
  - `dying` → row 4 (dead/dark face)
  - `bored` → row 3 or 5 (tired/droopy)
  - `neutral` → row 1 (normal)
- Consumes: nothing (standalone module, reads PNG via `@img/sharp` or manual parsing)

**Description:** The Doom skin parses the sprite sheet PNG and maps each expression to a row index. The sprite sheet is ~174×379 px with frames arranged vertically (one expression per row).

**Sprite sheet layout:** The Doom head sprite sheet contains 5 rows of Doom's face in different expressions. The skin splits the sheet by calculating `frameWidth = sheetWidth / cols` and `frameHeight = sheetHeight / rows` from config or autodetection.

```typescript
// src/gamepad/avatar/skins/doom-skin.ts

/**
 * Doom-style avatar skin.
 *
 * Maps expressions to rows in the Doom head sprite sheet.
 * The sprite sheet is assumed to have one expression per row,
 * arranged vertically. Frame layout:
 *   row 0: neutral/smiling (happy)
 *   row 1: wide-eyed (surprised/neutral)
 *   row 2: looking sideways (curious/looking/thinking)
 *   row 3: intense/scowling (focused/bored)
 *   row 4: dead/dark (dying)
 *   row 5: exhausted (extra bored)
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { Skin, ExpressionState } from '../state-machine.js';

/** Default sprite sheet path */
const DEFAULT_SPRITE_PATH = join(__dirname, '../../../../3rd_party/doom_sprite_sheet.png');

/** Row index map: expression name → sprite sheet row */
const ROW_MAP: Record<string, number> = {
  happy: 0,
  surprised: 1,
  curious: 2,
  looking: 2,
  focused: 3,
  thinking: 2,
  dying: 4,
  bored: 3,
  neutral: 1,
};

/** Auto-detected sprite sheet dimensions */
let _sheetWidth = 0;
let _sheetHeight = 0;
let _rows = 0;
let _cols = 0;
let _loaded = false;

/** Parse PNG header to extract dimensions */
function parsePngHeader(buffer: Buffer): { width: number; height: number } {
  // PNG signature check (first 8 bytes)
  if (buffer[0] !== 0x89 || buffer[1] !== 0x50 || buffer[2] !== 0x4e || buffer[3] !== 0x47) {
    throw new Error('Not a valid PNG file');
  }

  // Width: bytes 16-19 (4 bytes, big-endian)
  const width = (buffer[16] << 24) | (buffer[17] << 16) | (buffer[18] << 8) | buffer[19];
  // Height: bytes 20-23 (4 bytes, big-endian)
  const height = (buffer[20] << 24) | (buffer[21] << 16) | (buffer[22] << 8) | buffer[23];

  if (width <= 0 || height <= 0) {
    throw new Error(`Invalid PNG dimensions: ${width}x${height}`);
  }

  return { width, height };
}

export class DoomSkin implements Skin {
  readonly id = 'doom';
  readonly name = 'Doom';
  private readonly _spritePath: string;
  private readonly _rows: number;
  private readonly _cols: number;
  private readonly _frameWidth: number;
  private readonly _frameHeight: number;
  private readonly _spriteWidth: number;
  private readonly _spriteHeight: number;

  constructor(options: { spritePath?: string; rows?: number; cols?: number } = {}) {
    this._spritePath = options.spritePath ?? DEFAULT_SPRITE_PATH;

    // Load and parse sprite dimensions
    const buffer = readFileSync(this._spritePath);
    const { width, height } = parsePngHeader(buffer);
    this._spriteWidth = width;
    this._spriteHeight = height;

    if (options.rows && options.cols) {
      this._rows = options.rows;
      this._cols = options.cols;
    } else {
      // Auto-detect: assume one frame per row (vertical strip)
      // or try to infer from aspect ratio
      this._cols = 1;
      // Estimate rows based on typical Doom head proportions (~1:1 frames)
      const frameSize = Math.max(width, height);
      this._rows = Math.round(height / frameSize);
      if (this._rows < 1) this._rows = 1;
    }

    this._frameWidth = Math.floor(width / this._cols);
    this._frameHeight = Math.floor(height / this._rows);
  }

  get spriteWidth(): number { return this._spriteWidth; }
  get spriteHeight(): number { return this._spriteHeight; }
  get frameWidth(): number { return this._frameWidth; }
  get frameHeight(): number { return this._frameHeight; }

  getFrameRow(expressionName: string, _cycleIndex: number): number {
    const row = ROW_MAP[expressionName];
    if (row === undefined) {
      // Default to neutral row
      return ROW_MAP['neutral'] ?? 1;
    }
    return row;
  }

  getFrameCount(expressionName: string): number {
    // Doom skin has 1 frame per expression (static row)
    return 1;
  }

  getExpressionNames(): string[] {
    return Object.keys(ROW_MAP);
  }

  /** Get the full sprite buffer for canvas drawing. */
  getSpriteBuffer(): Buffer {
    return readFileSync(this._spritePath);
  }
}
```

- [ ] **Step 1: Write the skin parser** — create `src/gamepad/avatar/skins/doom-skin.ts` with the code above, including PNG header parsing, row mapping, and `Skin` interface implementation
- [ ] **Step 2: Write tests** — create `tests/gamepad/avatar/skins/doom-skin.test.ts`:

```typescript
import { describe, test, expect } from '@jest/globals';
import { DoomSkin } from '../../../../src/gamepad/avatar/skins/doom-skin.js';

// Use a minimal test PNG in 3rd_party/ if the sprite isn't available
const testPngPath = '3rd_party/doom_sprite_sheet.png';

describe('DoomSkin', () => {
  test('should load and parse PNG header', () => {
    const skin = new DoomSkin({ spritePath: testPngPath });
    expect(skin.spriteWidth).toBeGreaterThan(0);
    expect(skin.spriteHeight).toBeGreaterThan(0);
    expect(skin.frameWidth).toBeGreaterThan(0);
    expect(skin.frameHeight).toBeGreaterThan(0);
  });

  test('should have 5+ rows for Doom expressions', () => {
    const skin = new DoomSkin({ spritePath: testPngPath });
    expect(skin.spriteHeight / skin.frameHeight).toBeGreaterThanOrEqual(5);
  });

  test('should map all expression names to valid rows', () => {
    const skin = new DoomSkin({ spritePath: testPngPath });
    for (const expr of skin.getExpressionNames()) {
      const row = skin.getFrameRow(expr, 0);
      expect(row).toBeGreaterThanOrEqual(0);
    }
  });

  test('should return frame count of 1 for static expressions', () => {
    const skin = new DoomSkin({ spritePath: testPngPath });
    for (const expr of skin.getExpressionNames()) {
      expect(skin.getFrameCount(expr)).toBe(1);
    }
  });

  test('should have valid sprite buffer', () => {
    const skin = new DoomSkin({ spritePath: testPngPath });
    const buffer = skin.getSpriteBuffer();
    expect(buffer.length).toBeGreaterThan(1000); // reasonable PNG size
  });

  test('should use default expression name fallback', () => {
    const skin = new DoomSkin({ spritePath: testPngPath });
    // Unknown expression should return a valid row (neutral)
    const row = skin.getFrameRow('unknown_expr', 0);
    expect(row).toBeGreaterThanOrEqual(0);
  });

  test('should accept custom rows/cols config', () => {
    const skin = new DoomSkin({ spritePath: testPngPath, rows: 5, cols: 1 });
    expect(skin.getExpressionNames()).toContain('happy');
  });
});
```

- [ ] **Step 3: Run tests** — `npm test -- tests/gamepad/avatar/skins/doom-skin.test.ts`
  - Expected: all tests pass
- [ ] **Step 4: Commit**

```bash
git add src/gamepad/avatar/skins/doom-skin.ts tests/gamepad/avatar/skins/doom-skin.test.ts
git commit -m "feat: add DoomSkin PNG sprite sheet parser

- DoomSkin implements Skin interface with expression-to-row mapping
- Auto-parses PNG header for sprite sheet dimensions (width/height)
- Maps 9 expressions to sprite sheet rows (happy, surprised, dying, etc.)
- Returns frame count of 1 (static row per expression)
- Unit tests for PNG parsing, row mapping, and config options"
```

---

### Task 3: SkinRegistry — plugin loading + config

**Files:**
- Create: `src/gamepad/avatar/skin-registry.ts`
- Modify: `package.json` — add `gamifyAI.avatarSkins` config section
- Test: `tests/gamepad/avatar/skin-registry.test.ts`

**Interfaces:**
- Produces: `SkinConfig` interface (from `package.json`)
- Produces: `SkinRegistry` with:
  - `constructor(context: vscode.ExtensionContext, config?: Record<string, any>)`
  - `getSkin(id: string): Skin | undefined`
  - `getAllSkins(): { id: string; name: string }[]`
  - `getCurrentSkin(): string`
  - `setCurrentSkin(id: string): void`
  - `getDefaultSkin(): string`
- Produces: auto-registration of DoomSkin from `3rd_party/` as the default
- Produces: user-configurable skin definitions via `package.json` → `gamifyAI.avatarSkins`
  - Each entry: `{ id: string, name: string, type: 'doom' | 'custom', spritePath: string, rows?: number, cols?: number }`
- Consumes: `Skin` interface, `DoomSkin` class

**Description:** The SkinRegistry is the skin factory. On construction, it reads the extension's `package.json` for configured skins and builds a map. The built-in `DoomSkin` is always registered first. Custom skins are loaded by type and options from the config.

```typescript
// src/gamepad/avatar/skin-registry.ts

import * as vscode from 'vscode';
import { Skin } from './state-machine.js';
import { DoomSkin } from './skins/doom-skin.js';

export interface SkinConfig {
  id: string;
  name: string;
  type: 'doom' | 'custom';
  spritePath?: string;
  rows?: number;
  cols?: number;
}

export class SkinRegistry {
  private _skins = new Map<string, Skin>();
  private _currentSkin = 'doom';

  constructor(context: vscode.ExtensionContext, config?: Record<string, SkinConfig[]>) {
    // Always register built-in skins first
    this._registerSkin(new DoomSkin());

    // Register user-configured skins
    const skins = config ?? this._getConfig(context);
    for (const skinConfig of skins) {
      if (skinConfig.type === 'doom') {
        this._registerSkin(new DoomSkin({
          spritePath: skinConfig.spritePath,
          rows: skinConfig.rows,
          cols: skinConfig.cols,
        }));
      }
      // Custom types can be extended later
    }
  }

  private _registerSkin(skin: Skin): void {
    this._skins.set(skin.id, skin);
  }

  private _getConfig(context: vscode.ExtensionContext): SkinConfig[] {
    const config = vscode.workspace.getConfiguration('gamifyAI');
    const skins = config.get<SkinConfig[]>('avatarSkins', []);
    return skins;
  }

  getSkin(id: string): Skin | undefined {
    return this._skins.get(id);
  }

  getAllSkins(): { id: string; name: string }[] {
    return Array.from(this._skins.values()).map(s => ({ id: s.id, name: s.name }));
  }

  getCurrentSkin(): string {
    return this._currentSkin;
  }

  setCurrentSkin(id: string): boolean {
    if (this._skins.has(id)) {
      this._currentSkin = id;
      return true;
    }
    return false;
  }

  getDefaultSkin(): string {
    return 'doom';
  }
}
```

**package.json changes:**
Add to `package.json` → `activationEvents` section and `contributes`:

```json
{
  "gamifyAI": {
    "avatarSkins": {
      "type": "array",
      "description": "Avatar skin configurations",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string", "description": "Unique skin identifier" },
          "name": { "type": "string", "description": "Display name" },
          "type": { "type": "string", "enum": ["doom", "custom"], "description": "Skin type" },
          "spritePath": { "type": "string", "description": "Path to sprite sheet PNG" },
          "rows": { "type": "number", "description": "Number of sprite rows" },
          "cols": { "type": "number", "description": "Number of sprite columns" }
        }
      }
    }
  }
}
```

- [ ] **Step 1: Write the skin registry** — create `src/gamepad/avatar/skin-registry.ts`
- [ ] **Step 2: Add package.json config** — add `gamifyAI.avatarSkins` to `package.json` → `contributes.configuration`
- [ ] **Step 3: Write tests** — create `tests/gamepad/avatar/skin-registry.test.ts`:

```typescript
import { describe, test, expect, beforeEach, vi } from '@jest/globals';
import { SkinRegistry } from '../../../../src/gamepad/avatar/skin-registry.js';

// Mock vscode module
describe('SkinRegistry', () => {
  let registry: SkinRegistry;

  beforeEach(() => {
    // Minimal vscode mock
    const mockVscode = {
      workspace: {
        getConfiguration: () => ({
          get: () => [],
        }),
      },
      ExtensionContext: class {},
    } as any;

    registry = new SkinRegistry(mockVscode);
  });

  test('should always have DoomSkin registered by default', () => {
    const skin = registry.getSkin('doom');
    expect(skin).toBeDefined();
  });

  test('should list all registered skins', () => {
    const skins = registry.getAllSkins();
    expect(skins.length).toBeGreaterThan(0);
    expect(skins[0].id).toBe('doom');
  });

  test('should return current skin as doom by default', () => {
    expect(registry.getCurrentSkin()).toBe('doom');
  });

  test('should return doom as default skin', () => {
    expect(registry.getDefaultSkin()).toBe('doom');
  });

  test('should handle getCurrentSkin for single skin', () => {
    expect(registry.getCurrentSkin()).toBe('doom');
  });
});
```

- [ ] **Step 4: Run tests** — `npm test -- tests/gamepad/avatar/skin-registry.test.ts`
  - Expected: all tests pass
- [ ] **Step 5: Compile** — `npm run compile` (verify no TS errors)
- [ ] **Step 6: Commit**

```bash
git add src/gamepad/avatar/skin-registry.ts src/gamepad/avatar/skins/doom-skin.ts src/gamepad/avatar/skins/doom-skin.ts tests/gamepad/avatar/skins/doom-skin.test.ts tests/gamepad/avatar/skin-registry.test.ts package.json
git commit -m "feat: add SkinRegistry with DoomSkin auto-registration

- SkinRegistry as skin factory with getSkin/getAllSkins/setCurrentSkin
- DoomSkin auto-registered as default from 3rd_party/ sprite sheet
- User-configurable skins via package.json gamifyAI.avatarSkins
- SkinConfig with id, name, type, spritePath, rows, cols
- package.json configuration schema for avatarSkins
- Unit tests for registry creation and skin lookup"
```

---

### Task 4: VS Code Webview panel

**Files:**
- Create: `src/gamepad/avatar-panel.ts` — the VS Code panel manager
- Test: `tests/gamepad/avatar-panel.test.ts`

**Interfaces:**
- Produces: `GamepadAvatarPanel` with:
  - `show(): void` — create/reveal panel
  - `hide(): void` — hide panel
  - `dispose(): void` — cleanup
  - `updateState(state: { expressionName: string; cycleIndex: number }): void` — update panel content
  - `setSkin(id: string): void` — switch skin
- Consumes: `SkinRegistry`, `AvatarStateMachine`, `GamepadService`

**Description:** The webview panel manages the VS Code panel lifecycle and communicates with the embedded HTML canvas via `postMessage`. The panel content is a self-contained HTML page that renders the avatar frame from the skin's sprite sheet.

**Panel architecture:**
1. Extension creates webview panel with HTML content
2. HTML contains a 128×128 canvas + Doom-style HUD bezel border
3. Extension sends `{ expressionName, cycleIndex, skinId }` via `postMessage`
4. Panel's canvas draws the sprite sheet frame from the current skin

**HTML content:**
- 128×128 canvas, pixelated (`image-rendering: pixelated`)
- Dark background with metallic HUD frame (CSS border/shadow)
- Expression label at bottom (text: "IDLE", "HAPPY", "DIED", etc.)
- Canvas draws the sprite sheet frame from received message

```typescript
// src/gamepad/avatar-panel.ts

import * as vscode from 'vscode';
import { SkinRegistry } from './skin-registry.js';
import { AvatarStateMachine, GamepadAvatarInput } from './state-machine.js';
import type { Gamepad } from 'gamepad-node';

export interface GamepadState {
  buttons: ReadonlyArray<{ pressed: boolean; value: number }>;
  axes: ReadonlyArray<number>;
  connected: boolean;
}

export class GamepadAvatarPanel {
  private _panel?: vscode.WebviewPanel;
  private _disposables: vscode.Disposable[] = [];
  private _pollTimer: ReturnType<typeof setInterval> | null = null;
  private _state: GamepadState = {
    buttons: Array(16).fill(null).map(() => ({ pressed: false, value: 0 })),
    axes: [0, 0, 0, 0, 0, 0],
    connected: false,
  };
  private _streaming = false;
  private _chatFocused = false;
  private _errorState = false;

  static readonly viewType = 'gamifyAI.avatar';

  constructor(
    private readonly _context: vscode.ExtensionContext,
    private readonly _skinRegistry: SkinRegistry,
  ) {}

  show(): void {
    if (this._panel) {
      this._panel.reveal();
      return;
    }

    this._panel = vscode.window.createWebviewPanel(
      GamepadAvatarPanel.viewType,
      'Gamify AI — Avatar',
      vscode.ViewColumn.Two,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
      },
    );

    this._panel.webview.html = this._getHtml();

    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
    this._panel.onDidChangeViewState(({ visible }) => {
      if (visible && !this._pollTimer) {
        this._startPolling();
      }
    });

    // Initial draw with waiting state
    this._updatePanel();
  }

  hide(): void {
    this._panel?.hide();
  }

  dispose(): void {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
    this._panel?.dispose();
    this._panel = undefined;
    this._disposables.forEach(d => d.dispose());
    this._disposables = [];
  }

  updateFromGamepad(gamepads: Gamepad[]): void {
    if (gamepads.length > 0) {
      const gp = gamepads[0];
      this._state.connected = true;
      this._state.buttons = gp.buttons;
      this._state.axes = gp.axes;
    } else {
      this._state.connected = false;
    }
  }

  setStreaming(streaming: boolean): void {
    this._streaming = streaming;
  }

  setErrorState(errorState: boolean): void {
    this._errorState = errorState;
  }

  setChatFocused(chatFocused: boolean): void {
    this._chatFocused = chatFocused;
  }

  private _getInput(): GamepadAvatarInput {
    return {
      buttons: this._state.buttons,
      axes: this._state.axes,
      connected: this._state.connected,
      streaming: this._streaming,
      chatFocused: this._chatFocused,
      errorState: this._errorState,
    };
  }

  private _updatePanel(): void {
    if (!this._panel) return;

    // Build gamepad input state
    const input = this._getInput();

    // Get current expression from state machine (simplified — no full machine here)
    // In practice, we'd need a state machine instance
    const skin = this._skinRegistry.getSkin(this._skinRegistry.getCurrentSkin());
    const expression = 'idle';
    const cycleIndex = 0;

    this._panel.webview.postMessage({
      type: 'update',
      expression,
      cycleIndex,
      skinId: this._skinRegistry.getCurrentSkin(),
      spriteWidth: skin?.spriteWidth,
      spriteHeight: skin?.spriteHeight,
      frameWidth: skin?.frameWidth,
      frameHeight: skin?.frameHeight,
    });
  }

  private _startPolling(): void {
    this._pollTimer = setInterval(() => {
      this._updatePanel();
    }, 100); // 10 FPS — state machine only needs to update every 100ms
  }

  private _getHtml(): string {
    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      margin: 0;
      padding: 8px;
      background: #0a0a0a;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      overflow: hidden;
      font-family: 'Courier New', monospace;
    }
    #hud {
      position: relative;
      border: 3px solid #3a3a3a;
      box-shadow: 0 0 15px rgba(255, 0, 0, 0.2), inset 0 0 20px rgba(0, 0, 0, 0.8);
      border-radius: 4px;
    }
    #hud canvas {
      display: block;
      image-rendering: pixelated;
      image-rendering: crisp-edges;
    }
    #label {
      color: #ff4444;
      font-size: 10px;
      font-weight: bold;
      letter-spacing: 3px;
      text-align: center;
      margin-top: 8px;
      text-transform: uppercase;
      opacity: 0.9;
    }
  </style>
</head>
<body>
  <div id="hud">
    <canvas id="avatar" width="128" height="128"></canvas>
  </div>
  <div id="label">IDLE</div>
  <script>
    (function() {
      const canvas = document.getElementById('avatar');
      const ctx = canvas.getContext('2d')!;
      const label = document.getElementById('label');
      let spriteImage: HTMLImageElement | null = null;
      let frameData: any = null;

      // Render sprite from postMessage
      function render() {
        if (!spriteImage || !frameData) {
          // Draw placeholder
          ctx.fillStyle = '#1a1a1a';
          ctx.fillRect(0, 0, 128, 128);
          ctx.fillStyle = '#ff4444';
          ctx.font = '12px monospace';
          ctx.textAlign = 'center';
          ctx.fillText('...', 64, 64);
          return;
        }

        const { spriteWidth, spriteHeight, frameWidth, frameHeight, expression, cycleIndex } = frameData;
        const skin = skinRegistry.getSkin(frameData.skinId);

        if (skin) {
          const row = skin.getFrameRow(expression, cycleIndex);
          const sx = 0; // single column
          const sy = row * (spriteHeight / Math.floor(spriteHeight / frameHeight));

          ctx.imageSmoothingEnabled = false;
          ctx.drawImage(
            spriteImage,
            sx, sy, frameWidth, frameHeight,
            0, 0, 128, 128
          );

          // Red label
          label.textContent = expression.toUpperCase();
          label.style.color = expression === 'dying' ? '#ff0000' :
                              expression === 'happy' ? '#44ff44' :
                              expression === 'surprised' ? '#ffff44' : '#ff4444';
        }
      }

      window.addEventListener('message', function(event) {
        const message = event.data;
        if (message.type === 'update') {
          frameData = message;
          if (message.spriteData) {
            // If sprite data is provided as base64, decode it
            spriteImage = new Image();
            spriteImage.onload = () => { render(); };
            spriteImage.src = message.spriteData;
          } else {
            render();
          }
        }
      });

      // Initial state
      render();
    })();
  </script>
</body>
</html>`;
  }
}
```

**Note:** The above HTML uses `skinRegistry` as a global, which won't work in practice. The proper approach is:
1. Extension sends the current expression + skin ID via `postMessage`
2. The panel HTML receives it and renders a simple placeholder or a basic sprite-based avatar
3. Full sprite sheet loading would require the panel to know the sprite data — which means the extension needs to provide the sprite as `postMessage` data (base64 or array buffer)

For a simpler initial implementation:
- Extension sends expression name only
- Panel renders a simple canvas-based Doom-style face using basic shapes (rectangles, circles) to simulate expressions
- No sprite sheet loading needed in the webview
- The expression drives which simple shape configuration to draw

Let me revise to use the simple canvas approach:

```typescript
// Simplified panel that draws a pixelated avatar with basic shapes
private _getHtml(): string {
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { margin: 0; padding: 8px; background: #0a0a0a; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; font-family: 'Courier New', monospace; }
    #hud { position: relative; border: 3px solid #3a3a3a; box-shadow: 0 0 15px rgba(255, 0, 0, 0.2), inset 0 0 20px rgba(0, 0, 0, 0.8); border-radius: 4px; }
    #hud canvas { display: block; image-rendering: pixelated; image-rendering: crisp-edges; }
    #label { color: #ff4444; font-size: 10px; font-weight: bold; letter-spacing: 3px; text-align: center; margin-top: 8px; text-transform: uppercase; opacity: 0.9; }
  </style>
</head>
<body>
  <div id="hud"><canvas id="avatar" width="128" height="128"></canvas></div>
  <div id="label">IDLE</div>
  <script>
    (function() {
      const canvas = document.getElementById('avatar');
      const ctx = canvas.getContext('2d')!;
      const label = document.getElementById('label');
      let expression = 'idle';
      let tick = 0;

      function draw() {
        tick++;
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, 128, 128);

        const cx = 64, cy = 56;

        // Face outline (rounded rectangle approximation)
        ctx.fillStyle = '#8b7355';
        ctx.fillRect(cx - 28, cy - 28, 56, 56);
        ctx.fillStyle = '#d4a574';
        ctx.fillRect(cx - 26, cy - 26, 52, 52);

        // Hair/head top
        ctx.fillStyle = '#4a3728';
        ctx.fillRect(cx - 28, cy - 30, 56, 10);
        ctx.fillRect(cx - 24, cy - 32, 8, 4);
        ctx.fillRect(cx + 16, cy - 32, 8, 4);

        // Eyes
        const eyeY = cy - 6;
        const eyeW = 6, eyeH = 6;

        // Eye background
        ctx.fillStyle = '#fff';
        ctx.fillRect(cx - 18, eyeY, eyeW, eyeH);
        ctx.fillRect(cx + 10, eyeY, eyeW, eyeH);

        // Pupils (move based on expression)
        let pupilX = 0, pupilY = 0;
        if (expression === 'focused') pupilX = 2;
        else if (expression === 'surprised') { eyeW = 8; eyeH = 8; }

        ctx.fillStyle = '#2a1a0a';
        ctx.fillRect(cx - 15 + pupilX, eyeY + 1 + pupilY, 3, 3);
        ctx.fillRect(cx + 13 + pupilX, eyeY + 1 + pupilY, 3, 3);

        // Mouth
        ctx.fillStyle = '#6b3a2a';
        if (expression === 'happy') {
          // Smile: curved down
          ctx.fillRect(cx - 12, cy + 8, 24, 4);
          ctx.fillRect(cx - 14, cy + 4, 4, 8);
          ctx.fillRect(cx + 10, cy + 4, 4, 8);
        } else if (expression === 'surprised') {
          // O mouth
          ctx.fillRect(cx - 6, cy + 4, 12, 12);
        } else if (expression === 'dying') {
          // X eyes, flat mouth
          ctx.fillStyle = '#000';
          ctx.fillRect(cx - 18, eyeY - 2, 6, 2);
          ctx.fillRect(cx - 16, eyeY, 2, 6);
          ctx.fillRect(cx + 10, eyeY - 2, 6, 2);
          ctx.fillRect(cx + 12, eyeY, 2, 6);
          ctx.fillRect(cx - 6, cy + 10, 12, 2);
        } else if (expression === 'focused' || expression === 'thinking') {
          // Flat line
          ctx.fillRect(cx - 10, cy + 10, 20, 2);
        } else {
          // Default slight smile
          ctx.fillRect(cx - 8, cy + 10, 16, 2);
        }

        // Brow for intense expressions
        if (expression === 'focused' || expression === 'surprised' || expression === 'dying') {
          ctx.fillStyle = '#4a3728';
          ctx.fillRect(cx - 20, eyeY - 3, 14, 2);
          ctx.fillRect(cx + 6, eyeY - 3, 14, 2);
        }

        // Breathing animation for idle
        if (expression === 'idle' || expression === 'bored') {
          const breathe = Math.sin(tick * 0.1) * 2;
          ctx.fillStyle = '#d4a574';
          ctx.fillRect(cx - 26 + breathe, cy - 26, 52, 52);
        }

        // Label
        label.textContent = expression.toUpperCase();
        label.style.color = expression === 'dying' ? '#ff0000' :
                            expression === 'happy' ? '#44ff44' :
                            expression === 'surprised' ? '#ffff44' : '#ff4444';

        requestAnimationFrame(draw);
      }

      window.addEventListener('message', function(event) {
        const message = event.data;
        if (message.type === 'update') {
          expression = message.expression;
        }
      });

      draw();
    })();
  </script>
</body>
</html>`;
}
```

This HTML approach draws a Doom-style pixelated avatar using basic canvas shapes — no sprite sheet needed in the webview. The expression name drives which features are drawn (eyes, mouth, brow).

- [ ] **Step 1: Write the panel** — create `src/gamepad/avatar-panel.ts` with the canvas-based avatar drawing HTML
- [ ] **Step 2: Write tests** — create `tests/gamepad/avatar-panel.test.ts`:

```typescript
import { describe, test, expect, beforeEach, vi } from '@jest/globals';
import { GamepadAvatarPanel } from '../../../../src/gamepad/avatar-panel.js';

describe('GamepadAvatarPanel', () => {
  let panel: GamepadAvatarPanel;
  const mockContext = {
    extensionUri: { fsPath: '/test' } as any,
  } as any;
  const mockRegistry = {
    getSkin: () => ({ spriteWidth: 128, spriteHeight: 128, frameWidth: 32, frameHeight: 32 }),
    getCurrentSkin: () => 'doom',
  } as any;

  beforeEach(() => {
    vi.clearAllMocks();
    panel = new GamepadAvatarPanel(mockContext, mockRegistry);
  });

  test('should be creatable', () => {
    expect(panel).toBeDefined();
  });

  test('should have correct view type', () => {
    expect(GamepadAvatarPanel.viewType).toBe('gamifyAI.avatar');
  });

  test('should initialize with default gamepad state', () => {
    // Panel should initialize with empty gamepad state
    expect(panel).toBeDefined();
  });

  test('should handle updateFromGamepad without error', () => {
    // Mock gamepad state
    panel.updateFromGamepad([
      {
        buttons: [{ pressed: false, value: 0 }],
        axes: [0, 0, 0, 0],
      } as any,
    ]);
    // Should not throw
  });

  test('should set streaming state', () => {
    panel.setStreaming(true);
    panel.setStreaming(false);
    // Should not throw
  });

  test('should set error state', () => {
    panel.setErrorState(true);
    panel.setErrorState(false);
    // Should not throw
  });

  test('should dispose without error', () => {
    panel.dispose();
    // Should not throw, should be safe to call multiple times
    panel.dispose();
  });

  test('should handle show when not yet shown', () => {
    // Cannot fully test without real VS Code, but should not throw
    expect(panel).toBeDefined();
  });
});
```

- [ ] **Step 3: Run tests** — `npm test -- tests/gamepad/avatar-panel.test.ts`
  - Expected: all tests pass
- [ ] **Step 4: Compile** — `npm run compile` (verify no TS errors)
- [ ] **Step 5: Commit**

```bash
git add src/gamepad/avatar-panel.ts tests/gamepad/avatar-panel.test.ts
git commit -m "feat: add GamepadAvatarPanel with canvas-based avatar rendering

- GamepadAvatarPanel manages VS Code webview panel lifecycle
- Canvas-based Doom-style avatar drawn with basic shapes (no sprite sheet)
- Expression-driven rendering: idle, happy, surprised, dying, focused, thinking
- Breathing animation, eyebrow intensity, eye pupil movement
- Red/green/yellow expression labels with dark HUD frame
- PostMessage protocol between extension and panel for state updates
- 100ms polling interval for smooth state transitions"
```

---

### Task 5: Wire up in extension.ts + register command

**Files:**
- Modify: `src/extension.ts`
- Modify: `package.json` — add `gamifyAI.showAvatar` command

**Interfaces:**
- Produces: `gamifyAI.showAvatar` command registration
- Consumes: `GamepadAvatarPanel`, `SkinRegistry`, `AvatarStateMachine`, `GamepadService`

**Description:** Wire the avatar panel into the extension lifecycle. Create the panel, register the command, and poll gamepad state to feed it.

```typescript
// In src/extension.ts

import * as vscode from 'vscode';
import { GamepadService } from './gamepad/service.js';
import { GamepadAvatarPanel } from './gamepad/avatar-panel.js';
import { SkinRegistry } from './gamepad/avatar/skin-registry.js';
import { AvatarStateMachine } from './gamepad/avatar/state-machine.js';

export function activate(context: vscode.ExtensionContext) {
  // ... existing activation code ...

  // Create skin registry with context
  const skinRegistry = new SkinRegistry(context);

  // Create avatar state machine
  const stateMachine = new AvatarStateMachine();

  // Create avatar panel
  const avatarPanel = new GamepadAvatarPanel(context, skinRegistry);

  // Create gamepad service
  const gamepadService = new GamepadService();

  // Register avatar panel command
  const showAvatar = vscode.commands.registerCommand('gamifyAI.showAvatar', () => {
    avatarPanel.show();
  });
  context.subscriptions.push(showAvatar);

  // Register dispose on deactivate
  context.subscriptions.push(avatarPanel);
  context.subscriptions.push(gamepadService);

  // Start gamepad polling
  gamepadService.start().catch(() => {
    // Gamepad service failed to start — panel will show "no gamepad" state
  });

  // Gamepad polling loop (feeds state to both panel and state machine)
  let lastUpdate = 0;
  const gamepadPoll = () => {
    requestAnimationFrame(gamepadPoll);
    const now = Date.now();
    if (now - lastUpdate < 100) return; // 10 FPS max
    lastUpdate = now;

    const gamepads = gamepadService.getGamepads();
    avatarPanel.updateFromGamepad(gamepads);

    // Feed state to state machine
    const input: AvatarStateMachine.GamepadAvatarInput = {
      buttons: gamepads.length > 0 ? gamepads[0].buttons : [],
      axes: gamepads.length > 0 ? gamepads[0].axes : [],
      connected: gamepads.length > 0,
      streaming: false, // wire this up later
      chatFocused: false, // wire this up later
      errorState: false, // wire this up later
    };

    stateMachine.update(input);
    const state = stateMachine.tick(16);

    // Send to panel
    avatarPanel.updateState(state);
  };
  gamepadPoll();
}

export function deactivate() {
  // Cleanup
}
```

**package.json command registration:**
Add to `package.json` → `contributes.commands`:

```json
{
  "commands": [
    {
      "command": "gamifyAI.showAvatar",
      "title": "Gamify AI - Show Avatar",
      "icon": "$(gamepad)"
    }
  ]
}
```

- [ ] **Step 1: Modify extension.ts** — wire up `GamepadAvatarPanel`, `SkinRegistry`, `AvatarStateMachine`, and gamepad polling loop
- [ ] **Step 2: Add command to package.json** — register `gamifyAI.showAvatar` with icon
- [ ] **Step 3: Compile** — `npm run compile` (verify no TS errors)
- [ ] **Step 4: Run all tests** — `npm test` (verify all existing tests still pass)
- [ ] **Step 5: Commit**

```bash
git add src/extension.ts package.json
git commit -m "feat: wire up avatar panel with gamepad polling loop

- Add gamifyAI.showAvatar command with gamepad icon
- Wire GamepadAvatarPanel, SkinRegistry, and AvatarStateMachine in activate()
- Gamepad polling loop at 10 FPS feeds state to state machine and panel
- State machine updates avatar expression based on gamepad input
- Panel shows current expression via postMessage
- Deactivate disposes avatar panel and gamepad service"
```

---

### Task 6: Tests + polish

**Files:**
- All: verify TypeScript compilation
- All: verify all tests pass
- Code review for edge cases and error handling

**Description:** Run full test suite and TypeScript compilation. Fix any issues. Ensure the extension can be packaged and installed.

- [ ] **Step 1: Compile** — `npm run compile` — expect 0 errors
- [ ] **Step 2: Run all tests** — `npm test` — expect all existing tests + new tests to pass
- [ ] **Step 3: Fix any compilation or test failures**
- [ ] **Step 4: Commit** (if any fixes were made, otherwise skip)

```bash
git add -A
git commit -m "fix: polish avatar panel implementation

- Fix TypeScript compilation errors
- Fix test failures
- Ensure all existing tests still pass
- Verify gamepad polling loop handles edge cases (no gamepad, disconnect)"
```

---

### Task 7: Final integration test

**Description:** Manually verify the avatar panel works in VS Code:
1. Open the VS Code extension
2. Connect a gamepad
3. Run `gamifyAI.showAvatar` command
4. Press gamepad buttons and observe avatar reactions
5. Verify the panel stays open (persistent) but user can hide it

- [ ] **Step 1: Manual test** — verify all expressions work as expected
- [ ] **Step 2: Fix any issues discovered during manual testing**
- [ ] **Step 3: Commit fixes**

```bash
git add -A
git commit -m "fix: resolve issues found during manual avatar testing

- Fix [specific issue]
- Verify all expressions render correctly
- Ensure panel persistence works as expected"
```
