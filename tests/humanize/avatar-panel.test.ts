import { describe, test, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { GamepadAvatarPanel } from '../../src/humanize/avatar-panel';

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

  beforeEach(() => {
    panel = new GamepadAvatarPanel(
      { extensionUri: { fsPath: '/test' } } as any,
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

  test('should initialize with default HTML', () => {
    expect(panel['_htmlTemplate']).toContain('html');
  });

  test('should dispose without error', () => {
    panel.dispose();
    // Should not throw, should be safe to call multiple times
    panel.dispose();
  });

  test('should handle WebSocket disconnection on dispose', () => {
    panel.connectToClient('http://localhost:5004');
    panel.dispose();
    // Should not throw
  });

  test('should show view when visible', () => {
    panel.show();
    // show() should not throw, just reveal if view exists
  });
});
