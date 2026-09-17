import { CopilotChatModule } from '../../src/modules/copilot-chat';

describe('CopilotChatModule', () => {
  test('should be defined', () => {
    const module = new CopilotChatModule();
    expect(module).toBeDefined();
  });

  test('should have correct name', () => {
    const module = new CopilotChatModule();
    expect(module.name).toBe('copilotChat');
  });
});
