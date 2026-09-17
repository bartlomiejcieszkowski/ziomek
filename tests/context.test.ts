import { ContextTracker } from '../src/context';

describe('ContextTracker', () => {
  test('should be defined', () => {
    const tracker = new ContextTracker();
    expect(tracker).toBeDefined();
  });

  test('should return default context state', () => {
    const tracker = new ContextTracker();
    const state = tracker.getState();
    expect(state).toEqual({
      chatFocused: false,
      inputFocused: false,
      sidebarFocused: false,
      streaming: false,
    });
  });
});
