import { jest } from '@jest/globals';
import { ModuleRegistry, GamepadModule } from '../../modules/base.js';

describe('ModuleRegistry', () => {
  let registry: ModuleRegistry;
  let mockModule: GamepadModule;

  beforeEach(() => {
    registry = new ModuleRegistry();
    mockModule = {
      name: 'copilotChat',
      displayName: 'Copilot Chat',
      actions: ['send-message', 'new-chat', 'cancel'],
      contexts: ['chat-focused', 'input-focused'],
      execute: jest.fn() as any,
    } as any;
  });

  test('should be defined', () => {
    expect(registry).toBeDefined();
  });

  test('should register a module', () => {
    registry.register(mockModule);
    expect(registry.getModule('copilotChat')).toBe(mockModule);
  });

  test('should register multiple modules', () => {
    const module2: GamepadModule = {
      name: 'test',
      displayName: 'Test',
      actions: ['test-action'],
      contexts: ['test'],
      execute: jest.fn() as any as unknown as (action: string, context: { context: string }) => Promise<void>,
    };

    registry.register(mockModule);
    registry.register(module2);

    expect(registry.getRegisteredModuleNames()).toContain('copilotChat');
    expect(registry.getRegisteredModuleNames()).toContain('test');
  });

  test('should return undefined for unregistered module', () => {
    const found = registry.getModule('nonexistent');
    expect(found).toBeUndefined();
  });

  test('should list registered module names', () => {
    const module2: GamepadModule = {
      name: 'test',
      displayName: 'Test',
      actions: ['test-action'],
      contexts: ['test'],
      execute: jest.fn() as any as unknown as (action: string, context: { context: string }) => Promise<void>,
    };

    registry.register(mockModule);
    registry.register(module2);

    const names = registry.getRegisteredModuleNames();
    expect(names).toContain('copilotChat');
    expect(names).toContain('test');
    expect(names).toHaveLength(2);
  });

  test('should resolve action to registered module and execute it', async () => {
    registry.register(mockModule);

    await registry.resolve('copilotChat', 'send-message', {
      context: 'input-focused',
    });

    expect(mockModule.execute).toHaveBeenCalledWith('send-message', {
      context: 'input-focused',
    });
  });

  test('should executeAction and forward to module', async () => {
    registry.register(mockModule);

    await registry.executeAction('copilotChat', 'cancel', {
      context: 'chat-focused',
    });

    expect(mockModule.execute).toHaveBeenCalledWith('cancel', {
      context: 'chat-focused',
    });
  });

  test('should throw when resolving unknown module', async () => {
    await expect(
      registry.resolve('unknown', 'send-message', { context: 'test' }),
    ).rejects.toThrow("No module found with name 'unknown'");
  });

  test('should throw when module does not handle action', async () => {
    registry.register(mockModule);

    await expect(
      registry.resolve('copilotChat', 'unknown-action', { context: 'test' }),
    ).rejects.toThrow(
      "Module 'copilotChat' does not handle action 'unknown-action'",
    );
  });

  test('should execute action in the specified context', async () => {
    const module2: GamepadModule = {
      name: 'copilotChat',
      displayName: 'Copilot Chat',
      actions: ['new-chat'],
      contexts: ['chat-focused'],
      execute: jest.fn() as any,
    } as unknown as GamepadModule;

    await registry.resolve('copilotChat', 'new-chat', {
      context: 'chat-focused',
    });

    expect(mockModule.execute).toHaveBeenCalledWith('new-chat', {
      context: 'chat-focused',
    });
  });

  test('should find module for an action', () => {
    registry.register(mockModule);

    const mod = registry.getModuleForAction('send-message');
    expect(mod).toBe(mockModule);
  });

  test('should return undefined for unregistered action', () => {
    registry.register(mockModule);

    const mod = registry.getModuleForAction('nonexistent-action');
    expect(mod).toBeUndefined();
  });

  test('should handle module with no actions gracefully', () => {
    const emptyModule: GamepadModule = {
      name: 'empty',
      displayName: 'Empty',
      actions: [],
      contexts: [],
      execute: jest.fn() as any,
    } as unknown as GamepadModule;

    registry.register(emptyModule);
    expect(registry.getModule('empty')).toBe(emptyModule);
    expect(registry.getRegisteredModuleNames()).toContain('empty');
  });

  test('should overwrite module when registering same name twice', () => {
    const module2: GamepadModule = {
      name: 'copilotChat',
      displayName: 'Copilot Chat V2',
      actions: ['new-action'],
      contexts: ['new-context'],
      execute: jest.fn() as any,
    } as unknown as GamepadModule;

    registry.register(mockModule);
    registry.register(module2);

    const updated = registry.getModule('copilotChat');
    expect(updated).toBe(module2);
    expect(updated?.actions).toContain('new-action');
  });

  test('should throw when executing action on unregistered module', async () => {
    await expect(
      registry.executeAction('unknown', 'action', { context: 'test' }),
    ).rejects.toThrow("No module found with name 'unknown'");
  });

  test('should support async module execution', async () => {
    let executed = false;
    const asyncModule: GamepadModule = {
      name: 'async',
      displayName: 'Async',
      actions: ['async-action'],
      contexts: ['test'],
      execute: jest.fn().mockImplementation(async () => {
        await new Promise((r) => setTimeout(r, 10));
        executed = true;
      }),
    } as unknown as GamepadModule;

    registry.register(asyncModule);
    await registry.resolve('async', 'async-action', { context: 'test' });
    expect(executed).toBe(true);
  });

  test('should allow multiple actions from one module', async () => {
    registry.register(mockModule);

    await registry.executeAction('copilotChat', 'send-message', {
      context: 'input-focused',
    });
    await registry.executeAction('copilotChat', 'new-chat', {
      context: 'chat-focused',
    });
    await registry.executeAction('copilotChat', 'cancel', {
      context: 'input-focused',
    });

    expect(mockModule.execute).toHaveBeenCalledTimes(3);
  });

  test('should return module names in registration order', () => {
    const module2: GamepadModule = {
      name: 'beta',
      displayName: 'Beta',
      actions: ['beta-action'],
      contexts: [],
      execute: jest.fn() as any,
    } as unknown as GamepadModule;

    registry.register(mockModule);
    registry.register(module2);

    const names = registry.getRegisteredModuleNames();
    expect(names[0]).toBe('copilotChat');
    expect(names[1]).toBe('beta');
  });
});
