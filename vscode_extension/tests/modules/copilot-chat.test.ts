import { jest } from '@jest/globals';
import { CopilotChatModule } from '../../modules/copilot-chat.js';

describe('CopilotChatModule', () => {
  let mockExecuteCommand: any;
  let module: CopilotChatModule;

  beforeEach(() => {
    mockExecuteCommand = jest.fn() as any;
    module = new CopilotChatModule({
      commands: { executeCommand: mockExecuteCommand },
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('should be defined', () => {
    expect(module).toBeDefined();
  });

  test('should have correct name', () => {
    expect(module.name).toBe('copilotChat');
  });

  test('should have correct displayName', () => {
    expect(module.displayName).toBe('Copilot Chat');
  });

  test('should handle send-message action', async () => {
    await module.execute('send-message', { context: 'input-focused' });
    expect(mockExecuteCommand).toHaveBeenCalledWith('chat.sendRequest');
  });

  test('should handle new-chat action', async () => {
    await module.execute('new-chat', { context: 'chat-focused' });
    expect(mockExecuteCommand).toHaveBeenCalledWith(
      'workbench.action.chat.newChat',
    );
  });

  test('should handle cancel action', async () => {
    await module.execute('cancel', { context: 'chat-focused' });
    expect(mockExecuteCommand).toHaveBeenCalledWith(
      'workbench.action.chat.cancel',
    );
  });

  test('should handle toggle-panel action', async () => {
    await module.execute('toggle-panel', { context: 'chat-focused' });
    expect(mockExecuteCommand).toHaveBeenCalledWith(
      'workbench.action.chat.toggle',
    );
  });

  test('should handle open-slash-menu action', async () => {
    await module.execute('open-slash-menu', { context: 'any' });
    expect(mockExecuteCommand).toHaveBeenCalledWith('chat.triggerSlash');
  });

  test('should handle open-command-palette action', async () => {
    await module.execute('open-command-palette', { context: 'any' });
    expect(mockExecuteCommand).toHaveBeenCalledWith(
      'workbench.action.showCommands',
    );
  });

  test('should handle focus-up navigation action', async () => {
    await module.execute('focus-up', { context: 'any' });
    expect(mockExecuteCommand).toHaveBeenCalledWith(
      'workbench.action.navigateUp',
    );
  });

  test('should handle focus-down navigation action', async () => {
    await module.execute('focus-down', { context: 'any' });
    expect(mockExecuteCommand).toHaveBeenCalledWith(
      'workbench.action.navigateDown',
    );
  });

  test('should handle focus-left navigation action', async () => {
    await module.execute('focus-left', { context: 'any' });
    expect(mockExecuteCommand).toHaveBeenCalledWith(
      'workbench.action.navigateLeft',
    );
  });

  test('should handle focus-right navigation action', async () => {
    await module.execute('focus-right', { context: 'any' });
    expect(mockExecuteCommand).toHaveBeenCalledWith(
      'workbench.action.navigateRight',
    );
  });

  test('should handle scroll-up action', async () => {
    await module.execute('scroll-up', { context: 'any' });
    expect(mockExecuteCommand).toHaveBeenCalledWith(
      'workbench.action.scrollUp',
    );
  });

  test('should handle scroll-down action', async () => {
    await module.execute('scroll-down', { context: 'any' });
    expect(mockExecuteCommand).toHaveBeenCalledWith(
      'workbench.action.scrollDown',
    );
  });

  test('should handle step-forward action', async () => {
    await module.execute('step-forward', { context: 'any' });
    expect(mockExecuteCommand).toHaveBeenCalledWith(
      'workbench.action.nextEditor',
    );
  });

  test('should handle step-backward action', async () => {
    await module.execute('step-backward', { context: 'any' });
    expect(mockExecuteCommand).toHaveBeenCalledWith(
      'workbench.action.previousEditor',
    );
  });

  test('should throw on unknown action', async () => {
    await expect(
      module.execute('nonexistent-action', { context: 'any' }),
    ).rejects.toThrow('Unknown action');
  });

  test('should support all expected actions', () => {
    const expectedActions = [
      'send-message',
      'new-chat',
      'cancel',
      'open-slash-menu',
      'toggle-panel',
      'open-command-palette',
      'focus-up',
      'focus-down',
      'focus-left',
      'focus-right',
      'scroll-up',
      'scroll-down',
      'step-forward',
      'step-backward',
    ];
    for (const action of expectedActions) {
      expect(module.actions).toContain(action);
    }
  });

  test('should pass context through to execute', async () => {
    await module.execute('send-message', { context: 'chat-focused' });
    expect(mockExecuteCommand).toHaveBeenCalledWith('chat.sendRequest');
  });

  test('should call executeCommand for every supported action', async () => {
    for (const action of module.actions) {
      mockExecuteCommand.mockClear();
      await module.execute(action, { context: 'any' });
      expect(mockExecuteCommand).toHaveBeenCalledTimes(1);
    }
  });

  test('should have correct number of supported actions', () => {
    expect(module.actions).toHaveLength(14);
  });

  test('should support all required contexts', () => {
    expect(module.contexts).toContain('chat-focused');
    expect(module.contexts).toContain('input-focused');
    expect(module.contexts).toContain('sidebar-focused');
    expect(module.contexts).toContain('any');
  });

  test('should throw error when executeCommand is not injected', async () => {
    const moduleNoDeps = new CopilotChatModule();
    await expect(
      moduleNoDeps.execute('send-message', { context: 'any' }),
    ).rejects.toThrow('executeCommand called without vscode.commands');
  });
});
