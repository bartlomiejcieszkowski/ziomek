import { ModuleRegistry } from '../../src/modules/base';

describe('ModuleRegistry', () => {
  test('should be defined', () => {
    const registry = new ModuleRegistry();
    expect(registry).toBeDefined();
  });
});
