export interface ContextState {
  chatFocused: boolean;
  inputFocused: boolean;
  sidebarFocused: boolean;
  streaming: boolean;
}

export class ContextTracker {
  getState(): ContextState {
    return {
      chatFocused: false,
      inputFocused: false,
      sidebarFocused: false,
      streaming: false,
    };
  }
}
