import { ContextTracker, ContextState } from '../context.js';

// Create a mock vscode API object
function createMockVscode() {
  const listeners = new Map<string, Array<(...args: any[]) => void>>();

  function on(event: string, listener: (...args: any[]) => void) {
    if (!listeners.has(event)) {
      listeners.set(event, []);
    }
    listeners.get(event)!.push(listener);

    return {
      dispose: () => {
        const list = listeners.get(event) || [];
        const index = list.indexOf(listener);
        if (index !== -1) list.splice(index, 1);
      },
    };
  }

  const m: any = {
    window: {
      onDidChangeActiveTextEditor: (listener: (...args: any[]) => void) =>
        on('textEditor', listener),
      onDidChangeActiveTerminal: (listener: () => void) =>
        on('terminal', listener),
    },
    workspace: {
      getConfiguration: () => ({
        get: () => undefined,
        update: () => {},
      }),
      onDidChangeConfiguration: () => ({ dispose: () => {} }),
    },
    commands: {
      registerCommand: () => {},
      executeCommand: () => Promise.resolve(),
    },
    Disposable: {
      from: (...disposables: Array<{ dispose: () => void }>) => ({
        dispose: () => disposables.forEach((d) => d.dispose()),
      }),
    },
  };

  // Fire event helper
  m.__fireEvent = function (event: string, ...args: any[]) {
    const list = listeners.get(event) || [];
    list.forEach((l) => l(...args));
  };

  return m;
}

describe('ContextTracker', () => {
  let mockVscode: ReturnType<typeof createMockVscode>;

  beforeEach(() => {
    mockVscode = createMockVscode();
  });

  test('should be defined', () => {
    const tracker = new ContextTracker(mockVscode);
    expect(tracker).toBeDefined();
  });

  test('should return default context state with all false', () => {
    const tracker = new ContextTracker(mockVscode);
    const state: ContextState = tracker.getState();
    expect(state).toEqual({
      chatFocused: false,
      inputFocused: false,
      sidebarFocused: false,
      streaming: false,
    });
  });

  test('should update chatFocused when setChatFocused is called', () => {
    const tracker = new ContextTracker(mockVscode);
    tracker.setChatFocused(true);
    expect(tracker.getState().chatFocused).toBe(true);
  });

  test('should update inputFocused when setInputFocused is called', () => {
    const tracker = new ContextTracker(mockVscode);
    tracker.setInputFocused(true);
    expect(tracker.getState().inputFocused).toBe(true);
  });

  test('should update sidebarFocused when setSidebarFocused is called', () => {
    const tracker = new ContextTracker(mockVscode);
    tracker.setSidebarFocused(true);
    expect(tracker.getState().sidebarFocused).toBe(true);
  });

  test('should update streaming when setStreaming is called', () => {
    const tracker = new ContextTracker(mockVscode);
    tracker.setStreaming(true);
    expect(tracker.getState().streaming).toBe(true);
  });

  test('should allow multiple context updates', () => {
    const tracker = new ContextTracker(mockVscode);
    tracker.setChatFocused(true);
    tracker.setInputFocused(true);
    tracker.setStreaming(true);

    const state = tracker.getState();
    expect(state.chatFocused).toBe(true);
    expect(state.inputFocused).toBe(true);
    expect(state.streaming).toBe(true);
    expect(state.sidebarFocused).toBe(false);
  });

  test('should update state when VS Code text editor event fires', () => {
    const tracker = new ContextTracker(mockVscode);

    let state = tracker.getState();
    expect(state.chatFocused).toBe(false);
    expect(state.inputFocused).toBe(false);

    // Simulate a chat editor becoming active
    (mockVscode as any).__fireEvent('textEditor', {
      document: { languageId: 'chat' },
    });

    state = tracker.getState();
    expect(state.chatFocused).toBe(true);
    expect(state.inputFocused).toBe(true);
  });
});
