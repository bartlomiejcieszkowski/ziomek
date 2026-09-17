// eslint-disable-next-line no-undef
module.exports = {
  window: {
    showInformationMessage: jest.fn().mockResolvedValue(undefined),
    showErrorMessage: jest.fn().mockResolvedValue(undefined),
    createOutputChannel: jest.fn().mockReturnValue({
      appendLine: jest.fn(),
      show: jest.fn(),
    }),
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
