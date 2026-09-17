import type * as vscode from 'vscode';
import type { Logger } from './logger.js';

export interface ContextState {
  chatFocused: boolean;
  inputFocused: boolean;
  sidebarFocused: boolean;
  streaming: boolean;
}

export interface VscodeApi {
  window: {
    onDidChangeActiveTextEditor: (
      listener: (e: vscode.TextEditor | undefined) => void,
    ) => vscode.Disposable;
    onDidChangeActiveTerminal: (
      listener: () => void,
    ) => vscode.Disposable;
  };
}

export class ContextTracker {
  private _state: ContextState = {
    chatFocused: false,
    inputFocused: false,
    sidebarFocused: false,
    streaming: false,
  };
  private _logger?: Logger;

  /**
   * @param api - vscode API instance (injected for testability).
   *                Pass `undefined` to use the global vscode module.
   * @param logger - Optional logger for debug output.
   */
  constructor(api?: typeof import('vscode'), logger?: Logger) {
    this._logger = logger;
    this._observeVsCodeEvents(api);
  }

  getState(): ContextState {
    return { ...this._state };
  }

  setChatFocused(focused: boolean): void {
    this._state.chatFocused = focused;
  }

  setInputFocused(focused: boolean): void {
    this._state.inputFocused = focused;
  }

  setSidebarFocused(focused: boolean): void {
    this._state.sidebarFocused = focused;
  }

  setStreaming(streaming: boolean): void {
    this._state.streaming = streaming;
  }

  private _observeVsCodeEvents(api?: typeof import('vscode')): void {
    // In production, api will be the vscode module.
    // In tests, it's injected (or undefined, meaning the module
    // won't be accessible and we gracefully skip VS Code wiring).
    if (!api) {
      this._logger?.debug('ContextTracker', 'No vscode API provided, skipping event observation');
      return;
    }

    const vscode = api as typeof import('vscode');

    // Detect when chat input editor is active
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor) {
        if (editor.document.languageId === 'chat') {
          this.setInputFocused(true);
          this.setChatFocused(true);
        } else {
          this.setInputFocused(false);
        }
      } else {
        this.setInputFocused(false);
      }
    });

    // Detect sidebar focus changes
    vscode.window.onDidChangeActiveTerminal(() => {
      this.setSidebarFocused(false);
    });
  }
}
