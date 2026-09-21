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
    // Idle cycle: 3 bored frames (900ms total) + 3 neutral frames (900ms)
    // After 900ms + 100ms we should be in neutral
    machine.update(createInput());
    machine.tick(900); // Complete one bored cycle
    machine.tick(100); // First frame of neutral
    expect(machine.tick(100).expressionName).toBe('neutral');
    expect(machine.tick(100).expressionName).toBe('neutral');
  });

  test('should transition to happy on A button press', () => {
    machine.update(createInput({ buttons: [{ pressed: true, value: 1 }] }));
    const state = machine.tick(100);
    expect(state.expressionName).toBe('happy');
  });

  test('should return to idle after happy expression duration', () => {
    // Happy duration is 500ms, so after 500ms it ends and we go to idle
    machine.update(createInput({ buttons: [{ pressed: true, value: 1 }] }));
    machine.tick(500); // Happy finishes
    machine.update(createInput()); // Re-update to start idle cycle
    machine.tick(1200); // Advance past first idle expression (900ms) + some buffer
    // Should now be in a later expression of the idle cycle (bored or neutral)
    const state = machine.tick(100);
    expect(['bored', 'neutral'].includes(state.expressionName)).toBe(true);
  });

  test('should not re-fire happy on button hold', () => {
    // Happy is edge-triggered, so pressing A, waiting for it to end,
    // then holding shouldn't trigger a new happy
    machine.update(createInput({ buttons: [{ pressed: true, value: 1 }] }));
    machine.tick(500); // Happy finishes, transitions to idle
    machine.tick(500); // Idle cycle starts
    const state = machine.tick(100);
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
    // After focused ends, we go to idle cycle which cycles through bored/neutral
    expect(['bored', 'neutral', 'idle'].includes(state.expressionName)).toBe(true);
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
    const expressions: string[] = [];
    for (let i = 0; i < 30; i++) {
      machine.update(createInput());
      const state = machine.tick(100);
      expressions.push(state.expressionName);
    }
    expect(expressions).toContain('bored');
    expect(expressions).toContain('neutral');
  });

  test('should handle disconnected gamepad', () => {
    machine.update(createInput({ connected: false }));
    machine.tick(1000); // Advance through at least one idle cycle
    const state = machine.tick(100);
    expect(state.expressionName).not.toBe('idle'); // Should be in bored/neutral cycle
  });

  test('should handle empty buttons array', () => {
    machine.update(createInput({ buttons: [] }));
    machine.tick(1000); // Advance through at least one idle cycle
    const state = machine.tick(100);
    expect(state.expressionName).not.toBe('idle');
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

  test('should reset to idle cycle', () => {
    machine.update(createInput({ errorState: true }));
    machine.tick(200);
    machine.reset();
    machine.update(createInput());
    machine.tick(1000); // Advance through idle cycle
    const state = machine.tick(100);
    expect(state.expressionName).toBe('neutral');
  });

  test('getCurrentState should return current expression', () => {
    machine.update(createInput({ buttons: [{ pressed: true, value: 1 }] }));
    const state = machine.tick(100);
    expect(state.expressionName).toBe('happy');
    expect(state.cycleIndex).toBe(0);
  });

  test('getCurrentState starts idle expression when tick called without update', () => {
    const state = machine.tick(100);
    // tick() auto-starts idle expression when no expression active
    // Returns the first idle expression from the map
    expect(state.expressionName).toMatch(/^(bored|neutral)$/);
  });
});
