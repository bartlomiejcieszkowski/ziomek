import { describe, test, expect, beforeEach, afterEach, jest } from '@jest/globals';
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

describe('Message features', () => {
  let machine: AvatarStateMachine;

  beforeEach(() => {
    jest.useFakeTimers();
    machine = new AvatarStateMachine();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('should start with no message', () => {
    expect(machine.getMessage()).toBe(null);
  });

  test('should set a message via setMessage()', () => {
    machine.setMessage('Hello');
    expect(machine.getMessage()).toBe('Hello');
  });

  test('should clear a message when setMessage is called with empty string', () => {
    machine.setMessage('Hello');
    expect(machine.getMessage()).toBe('Hello');
    machine.setMessage('');
    expect(machine.getMessage()).toBe(null);
  });

  test('should clear a message when setMessage is called without arguments', () => {
    machine.setMessage('Hello');
    expect(machine.getMessage()).toBe('Hello');
    machine.setMessage();
    expect(machine.getMessage()).toBe(null);
  });

  test('should return message in ExpressionState.tick()', () => {
    machine.setMessage('Hello');
    machine.update(createInput());
    const state = machine.tick(100);
    expect(state.message).toBe('Hello');
  });

  test('should remove message from state after expiry', () => {
    machine.setMessage('Hello', 500);
    machine.update(createInput());
    expect(machine.tick(100).message).toBe('Hello');
    jest.advanceTimersByTime(600);
    const state = machine.tick(100);
    expect(state.message).toBe(undefined);
  }, 10000);
});

describe('Timed expression features', () => {
  let machine: AvatarStateMachine;

  beforeEach(() => {
    jest.useFakeTimers();
    machine = new AvatarStateMachine();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('should return to idle after timed expression expires', () => {
    machine.setExpression('happy', 1000);
    // Advance fake timers past the setTimeout delay
    jest.advanceTimersByTime(1100);
    // tick() fires the internal cycle timer and transitions to idle
    const state = machine.tick(600);
    expect(['bored', 'neutral', 'idle']).toContain(state.expressionName);
  });

  test('should allow gamepad triggers after timed expression ends', () => {
    machine.setExpression('happy', 500);
    jest.advanceTimersByTime(500);
    // Clear internal timer so happy naturally transitions
    machine.tick(600);
    // Now gamepad should be able to trigger new expressions
    machine.update(createInput({ buttons: [{ pressed: true, value: 1 }] }));
    const state = machine.tick(100);
    expect(state.expressionName).toBe('happy');
  });

  test('should clear timed expression timer on reset()', () => {
    machine.setExpression('happy', 500);
    machine.reset();
    jest.advanceTimersByTime(600);
    machine.update(createInput());
    const state = machine.tick(100);
    expect(state.expressionName).not.toBe('happy');
  });

  test('should handle multiple setExpression calls with different durations', () => {
    machine.setExpression('happy', 500);
    machine.setExpression('surprised', 1000);
    // At 600ms the 500ms timer would have fired, but setExpression resets the timer
    jest.advanceTimersByTime(600);
    // tick() to let internal timer expire and see which expression is active
    const state = machine.tick(200);
    expect(['surprised', 'happy']).toContain(state.expressionName);
    // After total 1000ms (100ms more), both timers would have expired
    jest.advanceTimersByTime(500);
    const state2 = machine.tick(600);
    expect(state2.expressionName).not.toBe('surprised');
  });

  test('should not schedule timer when durationMs is 0 or undefined', () => {
    machine.setExpression('happy', 0);
    // Advance fake timers — no setTimeout was scheduled, so nothing happens
    jest.advanceTimersByTime(5000);
    machine.update(createInput());
    // tick the full happy duration (500ms) so it naturally expires
    const state = machine.tick(500);
    // After tick(500) the internal timer should have finished and
    // transitioned to idle (bored/neutral) via the external type clearing
    expect(['bored', 'neutral', 'idle']).toContain(state.expressionName);
    // Re-trigger via setExpression still works
    machine.setExpression('happy', 0);
    expect(machine.tick(100).expressionName).toBe('happy');
  });
});

describe('Combined features', () => {
  let machine: AvatarStateMachine;

  beforeEach(() => {
    jest.useFakeTimers();
    machine = new AvatarStateMachine();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('should allow message and emotion to be set independently', () => {
    machine.setMessage('Hello');
    machine.setExpression('happy', 500);
    machine.update(createInput());
    const state = machine.tick(100);
    expect(state.expressionName).toBe('happy');
    expect(state.message).toBe('Hello');
  });

  test('should clear message on reset() even if expression changed', () => {
    machine.setMessage('Hello');
    machine.setExpression('happy', 500);
    machine.reset();
    expect(machine.getMessage()).toBe(null);
    machine.update(createInput());
    const state = machine.tick(100);
    expect(state.message).toBe(undefined);
  });
});
