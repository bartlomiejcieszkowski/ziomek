import { MappingResolver } from '../../src/mapping/resolver';
import type { MappingConfig } from '../../src/mapping/config';

describe('MappingResolver', () => {
  let resolver: MappingResolver;
  let actions: string[];

  const defaultConfig: MappingConfig = {
    buttons: {
      0: 'send-message',
      1: 'cancel',
    },
    dpad: {
      0: 'focus-up',
      2: 'focus-down',
      1: 'focus-right',
      3: 'focus-left',
    },
    axes: {},
  };

  beforeEach(() => {
    actions = [];
    resolver = new MappingResolver(defaultConfig);
    resolver.onAction((action) => {
      actions.push(action);
    });
  });

  test('should be defined', () => {
    expect(resolver).toBeDefined();
  });

  test('should fire action on button press', () => {
    resolver.handleButton(0, true, 1);
    expect(actions).toContain('send-message');
  });

  test('should not fire action on button release', () => {
    resolver.handleButton(0, false, 0);
    expect(actions).toHaveLength(0);
  });

  test('should not fire action if button was already pressed', () => {
    resolver.handleButton(0, true, 1);
    actions.length = 0;
    resolver.handleButton(0, true, 1);
    expect(actions).toHaveLength(0);
  });

  test('should fire action on subsequent press after release', () => {
    // Use 0ms debounce so rapid press works
    resolver = new MappingResolver(defaultConfig, { debounceMs: 0 });
    actions.length = 0;
    resolver.onAction((action) => {
      actions.push(action);
    });
    resolver.handleButton(0, true, 1);
    actions.length = 0;
    resolver.handleButton(0, false, 0);
    resolver.handleButton(0, true, 1);
    expect(actions).toContain('send-message');
  });

  test('should fire dpad action on dpad press', () => {
    resolver.handleButton(4, true, 1); // D-pad up is button 4
    expect(actions).toContain('focus-up');
  });

  test('should fire dpad action on dpad down', () => {
    resolver.handleButton(6, true, 1); // D-pad down is button 6
    expect(actions).toContain('focus-down');
  });

  test('should fire dpad action on dpad right', () => {
    resolver.handleButton(5, true, 1);
    expect(actions).toContain('focus-right');
  });

  test('should fire dpad action on dpad left', () => {
    resolver.handleButton(7, true, 1);
    expect(actions).toContain('focus-left');
  });

  test('should not fire dpad action on release', () => {
    resolver.handleButton(4, false, 0);
    expect(actions).toHaveLength(0);
  });

  test('should debounce consecutive button presses', () => {
    // Use 0ms debounce for testable timing
    resolver = new MappingResolver(defaultConfig, { debounceMs: 0 });
    actions.length = 0;
    resolver.onAction((action) => {
      actions.push(action);
    });

    resolver.handleButton(0, true, 1);
    // Immediately press again — should be debounced since _lastActionTime is now
    resolver.handleButton(0, true, 1);
    expect(actions).toContain('send-message');
    expect(actions).toHaveLength(1);
  });

  test('should resolve axis to action when past threshold', () => {
    // First call stores value, second call fires when past threshold
    resolver.handleAxis(0, -0.6);
    resolver.handleAxis(0, -0.8);
    expect(actions.length).toBeGreaterThan(0);
  });

  test('should not fire axis action within dead zone', () => {
    resolver.handleAxis(0, 0.1);
    expect(actions).toHaveLength(0);
  });

  test('should not fire axis action on first call (no previous value)', () => {
    resolver.handleAxis(0, 0.2); // within dead zone effectively
    expect(actions).toHaveLength(0);
  });

  test('should not fire axis action when direction changed', () => {
    resolver.handleAxis(0, -0.8);
    resolver.handleAxis(0, 0.8); // direction changed
    // No new action should fire after direction flip
    expect(actions).toHaveLength(0); // first value doesn't fire, second flips direction
  });

  test('should clear pressed buttons and axis state', () => {
    resolver.handleButton(0, true, 1);
    expect(actions).toContain('send-message');
    resolver.clear();
    expect((resolver as any)._pressedButtons.size).toBe(0);
  });

  test('should update config when setConfig is called', () => {
    const newConfig: MappingConfig = {
      buttons: { 0: 'new-action' },
      dpad: {},
      axes: {},
    };
    resolver.setConfig(newConfig);
    resolver.handleButton(0, true, 1);
    expect(actions).toContain('new-action');
  });

  test('should not fire action when no callback is set', () => {
    resolver = new MappingResolver(defaultConfig);
    // No onAction() called
    resolver.handleButton(0, true, 1);
    // Should not throw, just silently do nothing
  });

  test('should fire axis scroll-up on negative Y axis value', () => {
    resolver.handleAxis(0, -0.8);
    resolver.handleAxis(0, -0.9); // maintain direction past threshold
    expect(actions).toContain('scroll-up');
  });

  test('should fire axis scroll-down on positive Y axis value', () => {
    resolver.handleAxis(0, 0.8);
    resolver.handleAxis(0, 0.9);
    expect(actions).toContain('scroll-down');
  });
});
