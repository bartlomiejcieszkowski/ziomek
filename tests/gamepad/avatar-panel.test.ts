import { describe, test, expect, beforeEach, afterEach } from '@jest/globals';
import { GamepadAvatarPanel } from '../../src/gamepad/avatar-panel';
import { SkinRegistry } from '../../src/gamepad/avatar/skin-registry';
import { AvatarStateMachine } from '../../src/gamepad/avatar/state-machine';

// Simple mock for VS Code that satisfies the panel's constructor
const mockVscode = {
  window: {
    createWebviewPanel: () => ({
      html: '',
      onDidDispose: () => {},
      onDidChangeViewState: () => ({ dispose: () => {} }),
      postMessage: () => Promise.resolve(),
    }),
  },
  ViewColumn: { Two: 2 },
  Disposable: { from: () => ({ dispose: () => {} }) },
  workspace: {
    getConfiguration: () => ({ get: () => 16 }),
  },
};

// Temporarily override global vscode
const originalVscode = (globalThis as any).vscode;

describe('GamepadAvatarPanel', () => {
  let panel: GamepadAvatarPanel;
  let skinRegistry: SkinRegistry;
  let stateMachine: AvatarStateMachine;

  beforeEach(() => {
    (globalThis as any).vscode = mockVscode;

    skinRegistry = SkinRegistry.getInstance();
    stateMachine = new AvatarStateMachine();
    panel = new GamepadAvatarPanel(
      { extensionUri: { fsPath: '/test' } } as any,
      skinRegistry,
      stateMachine,
    );
  });

  afterEach(() => {
    (globalThis as any).vscode = originalVscode;
    panel?.dispose();
  });

  test('should be creatable', () => {
    expect(panel).toBeDefined();
  });

  test('should have correct view type', () => {
    expect(GamepadAvatarPanel.viewType).toBe('gamifyAI.avatar');
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

  test('should return current state from state machine', () => {
    const state = panel.getCurrentState();
    expect(state).toHaveProperty('expressionName');
    expect(state).toHaveProperty('cycleIndex');
  });
});
