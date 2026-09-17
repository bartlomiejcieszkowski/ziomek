import { ConfigManager, defaultMapping } from '../../src/mapping/config';

describe('defaultMapping', () => {
  test('should be defined', () => {
    expect(defaultMapping).toBeDefined();
    expect(defaultMapping.buttons).toBeDefined();
    expect(defaultMapping.dpad).toBeDefined();
  });

  test('default mapping should have A button mapped to send-message', () => {
    expect(defaultMapping.buttons[0]).toBe('send-message');
  });

  test('default mapping should have B button mapped to cancel', () => {
    expect(defaultMapping.buttons[1]).toBe('cancel');
  });

  test('default mapping should have X button mapped to new-chat', () => {
    expect(defaultMapping.buttons[2]).toBe('new-chat');
  });

  test('default mapping should have Y button mapped to open-slash-menu', () => {
    expect(defaultMapping.buttons[3]).toBe('open-slash-menu');
  });

  test('default mapping should have D-pad directions mapped', () => {
    expect(defaultMapping.dpad[0]).toBe('focus-up');
    expect(defaultMapping.dpad[2]).toBe('focus-down');
  });
});

describe('ConfigManager', () => {
  let manager: ConfigManager;

  beforeEach(() => {
    manager = new ConfigManager();
  });

  test('should be defined', () => {
    expect(manager).toBeDefined();
  });

  test('should return current mapping on load', () => {
    const mapping = manager.loadMapping('copilotChat');
    expect(mapping).toBeDefined();
  });

  test('should use defaults when module not configured', () => {
    const mapping = manager.loadMapping('unknownModule');
    expect(mapping.buttons[0]).toBe(defaultMapping.buttons[0]);
  });

  test('should report copilotChat module as enabled', () => {
    expect(manager.isEnabled('copilotChat')).toBe(true);
  });

  test('should report unknown module as enabled by default', () => {
    expect(manager.isEnabled('unknownModule')).toBe(true);
  });

  test('should disable a module', () => {
    manager.setEnabled('copilotChat', false);
    expect(manager.isEnabled('copilotChat')).toBe(false);
  });

  test('should not error disabling unknown module', () => {
    expect(() => manager.setEnabled('unknownModule', false)).not.toThrow();
  });

  test('should return all expected button mappings', () => {
    const mapping = manager.loadMapping('copilotChat');
    expect(mapping.buttons[0]).toBe('send-message');
    expect(mapping.buttons[1]).toBe('cancel');
    expect(mapping.buttons[2]).toBe('new-chat');
    expect(mapping.buttons[3]).toBe('open-slash-menu');
    expect(mapping.buttons[4]).toBe('scroll-up');
    expect(mapping.buttons[5]).toBe('scroll-down');
    expect(mapping.buttons[6]).toBe('step-forward');
    expect(mapping.buttons[7]).toBe('step-backward');
    expect(mapping.buttons[8]).toBe('open-command-palette');
    expect(mapping.buttons[9]).toBe('toggle-panel');
  });

  test('should return D-pad mapping', () => {
    const mapping = manager.loadMapping('copilotChat');
    expect(mapping.dpad[0]).toBe('focus-up');
    expect(mapping.dpad[1]).toBe('focus-right');
    expect(mapping.dpad[2]).toBe('focus-down');
    expect(mapping.dpad[3]).toBe('focus-left');
  });

  test('should have axes mapping', () => {
    const mapping = manager.loadMapping('copilotChat');
    expect(mapping.axes.yAxis).toEqual([0, 'scroll-up']);
  });

  test('should have triggers mapping', () => {
    const mapping = manager.loadMapping('copilotChat');
    expect(mapping.triggers?.left).toBe('step-forward');
    expect(mapping.triggers?.right).toBe('step-backward');
  });

  test('should not share mutable state between load calls', () => {
    const mapping1 = manager.loadMapping('copilotChat');
    const mapping2 = manager.loadMapping('copilotChat');

    // Mutate one
    mapping1.buttons[0] = 'mutated';

    // Other should be unchanged
    expect(mapping2.buttons[0]).toBe('send-message');
  });
});
