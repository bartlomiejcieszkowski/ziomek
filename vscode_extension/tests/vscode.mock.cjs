// eslint-disable-next-line no-undef
const mockPanel = {
  html: '',
  onDidDispose: () => ({ dispose: () => {} }),
  onDidChangeViewState: () => ({ dispose: () => {} }),
  webview: {
    postMessage: jest.fn().mockResolvedValue(undefined),
  },
  reveal: () => {},
  visible: true,
};

module.exports = {
  window: {
    showInformationMessage: jest.fn().mockResolvedValue(undefined),
    showErrorMessage: jest.fn().mockResolvedValue(undefined),
    createOutputChannel: jest.fn().mockReturnValue({
      appendLine: jest.fn(),
      show: jest.fn(),
    }),
    createWebviewPanel: jest.fn().mockReturnValue(mockPanel),
    onDidChangeViewState: jest.fn(),
  },
  ViewColumn: {
    One: 1,
    Two: 2,
    Three: 3,
  },
  Disposable: {
    from: () => ({ dispose: () => {} }),
  },
  workspace: {
    getConfiguration: jest.fn(() => ({
      get: jest.fn((_, defaultValue) => defaultValue),
    })),
    onDidChangeConfiguration: jest.fn(),
  },
  commands: {
    registerCommand: jest.fn(),
  },
};