import type { GamepadModule } from './base.js';

export type VscodeCommands = {
  executeCommand: (...args: unknown[]) => Promise<unknown>;
};

export interface CopilotChatModuleOptions {
  commands?: VscodeCommands;
}

export class CopilotChatModule implements GamepadModule {
  name = 'copilotChat';
  displayName = 'Copilot Chat';
  actions = [
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
  ] as const;
  contexts = ['chat-focused', 'input-focused', 'sidebar-focused', 'any'] as const;

  private _commands: VscodeCommands;

  constructor(options: CopilotChatModuleOptions = {}) {
    this._commands = options.commands ?? {
      executeCommand: async (...args: unknown[]) => {
        // Runtime fallback: should not be reached when injected via vscode
        throw new Error(
          `executeCommand called without vscode.commands: ${args.join(', ')}`,
        );
      },
    };
  }

  async execute(action: string, context: { context: string }): Promise<void> {
    switch (action) {
      case 'send-message':
        return this._send();
      case 'new-chat':
        return this._newChat();
      case 'cancel':
        return this._cancel();
      case 'open-slash-menu':
        return this._openSlashMenu();
      case 'toggle-panel':
        return this._togglePanel();
      case 'open-command-palette':
        return this._openCommandPalette();
      case 'focus-up':
        return this._focusUp();
      case 'focus-down':
        return this._focusDown();
      case 'focus-left':
        return this._focusLeft();
      case 'focus-right':
        return this._focusRight();
      case 'scroll-up':
        return this._scrollUp();
      case 'scroll-down':
        return this._scrollDown();
      case 'step-forward':
        return this._stepForward();
      case 'step-backward':
        return this._stepBackward();
      default:
        throw new Error(`Unknown action: ${action}`);
    }
  }

  private async _send(): Promise<void> {
    await this._commands.executeCommand('chat.sendRequest');
  }

  private async _newChat(): Promise<void> {
    await this._commands.executeCommand('workbench.action.chat.newChat');
  }

  private async _cancel(): Promise<void> {
    await this._commands.executeCommand('workbench.action.chat.cancel');
  }

  private async _openSlashMenu(): Promise<void> {
    await this._commands.executeCommand('chat.triggerSlash');
  }

  private async _togglePanel(): Promise<void> {
    await this._commands.executeCommand('workbench.action.chat.toggle');
  }

  private async _openCommandPalette(): Promise<void> {
    await this._commands.executeCommand('workbench.action.showCommands');
  }

  private async _focusUp(): Promise<void> {
    await this._commands.executeCommand('workbench.action.navigateUp');
  }

  private async _focusDown(): Promise<void> {
    await this._commands.executeCommand('workbench.action.navigateDown');
  }

  private async _focusLeft(): Promise<void> {
    await this._commands.executeCommand('workbench.action.navigateLeft');
  }

  private async _focusRight(): Promise<void> {
    await this._commands.executeCommand('workbench.action.navigateRight');
  }

  private async _scrollUp(): Promise<void> {
    await this._commands.executeCommand('workbench.action.scrollUp');
  }

  private async _scrollDown(): Promise<void> {
    await this._commands.executeCommand('workbench.action.scrollDown');
  }

  private async _stepForward(): Promise<void> {
    await this._commands.executeCommand('workbench.action.nextEditor');
  }

  private async _stepBackward(): Promise<void> {
    await this._commands.executeCommand('workbench.action.previousEditor');
  }
}
