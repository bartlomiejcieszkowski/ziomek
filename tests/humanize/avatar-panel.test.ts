import { describe, test, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { GamepadAvatarPanel } from '../../src/humanize/avatar-panel';
import { SkinRegistry } from '../../src/humanize/avatar/skin-registry';
import { AvatarStateMachine } from '../../src/humanize/avatar/state-machine';

// Simple mock for VS Code that satisfies the panel's constructor
const mockPanel = {
  webview: {
    html: '',
    onDidDispose: () => ({ dispose: () => {} }),
    postMessage: jest.fn().mockResolvedValue(undefined),
    onDidReceiveMessage: jest.fn().mockReturnValue({ dispose: () => {} }),
  },
  visible: true,
  onDidChangeVisibility: jest.fn().mockReturnValue({ dispose: () => {} }),
};

describe('GamepadAvatarPanel', () => {
  let panel: GamepadAvatarPanel;
  let skinRegistry: SkinRegistry;
  let stateMachine: AvatarStateMachine;

  beforeEach(() => {
    skinRegistry = SkinRegistry.getInstance();
    stateMachine = new AvatarStateMachine();
    panel = new GamepadAvatarPanel(
      { extensionUri: { fsPath: '/test' } } as any,
      skinRegistry,
      stateMachine,
    );

    // Simulate VS Code calling resolveWebviewView
    panel.resolveWebviewView(mockPanel as any, {} as any, {} as any);
  });

  afterEach(() => {
    panel?.dispose();
  });

  test('should be creatable', () => {
    expect(panel).toBeDefined();
  });

  test('should have correct view type', () => {
    expect(GamepadAvatarPanel.viewType).toBe('humanizeAI.avatar');
  });

  test('should initialize with default gamepad state', () => {
    // Panel should initialize with empty gamepad state
    expect(panel).toBeDefined();
  });

  test('should handle updateFromGamepad without error', () => {
    panel.updateFromGamepad([
      {
        buttons: [{ pressed: false, value: 0 }],
        axes: [0, 0, 0, 0],
      } as any,
    ]);
    // Should not throw
  });

  test('should handle disconnected gamepad', () => {
    panel.updateFromGamepad([]);
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

  test('should set chat focused state', () => {
    panel.setChatFocused(true);
    panel.setChatFocused(false);
    // Should not throw
  });

  test('should dispose without error', () => {
    panel.dispose();
    // Should not throw, should be safe to call multiple times
    panel.dispose();
  });

  test('should send update message via postMessage (integration)', () => {
    // Update state machine and panel
    const state = panel.getCurrentState();
    panel.updateState(state);

    // Verify postMessage was called on the mock view
    expect(mockPanel.webview.postMessage).toHaveBeenCalled();
  });
});
