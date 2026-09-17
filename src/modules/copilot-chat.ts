import type { GamepadModule } from './base.js';

export class CopilotChatModule implements GamepadModule {
  name = 'copilotChat';
  displayName = 'Copilot Chat';
  actions = ['send-message', 'new-chat', 'cancel', 'open-slash-menu', 'toggle-panel', 'open-command-palette', 'focus-up', 'focus-down', 'focus-left', 'focus-right', 'scroll-up', 'scroll-down', 'step-forward', 'step-backward'];
  contexts = ['chat-focused', 'input-focused', 'sidebar-focused'];
  async execute(_action: string, _context: { context: string }): Promise<void> {
    // Stub
  }
}
