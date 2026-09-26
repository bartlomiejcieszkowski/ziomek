export default {
  preset: 'ts-jest/presets/default-esm',
  testEnvironment: 'node',
  extensionsToTreatAsEsm: ['.ts'],
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
    '^vscode$': '<rootDir>/tests/vscode.mock.cjs',
  },
  transform: {
    '^.+\\.tsx?$': [
      'ts-jest',
      {
        useESM: true,
        tsconfig: { module: 'NodeNext', 'moduleResolution': 'NodeNext' },
      },
    ],
  },
  testMatch: ['**/tests/**/*.test.ts'],
  testPathIgnorePatterns: ['/.worktrees/', '/node_modules/', '/ziomek/'],
  coverageDirectory: 'coverage',
  injectGlobals: true,
};
