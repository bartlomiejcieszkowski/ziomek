import { getDefaultModuleConfig } from '../../src/mapping/config';

describe('getDefaultModuleConfig', () => {
  test('should return config with enabled true', () => {
    const config = getDefaultModuleConfig();
    expect(config.enabled).toBe(true);
  });

  test('should return config with empty mapping', () => {
    const config = getDefaultModuleConfig();
    expect(config.mapping).toEqual({});
  });
});
