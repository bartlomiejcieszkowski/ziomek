import { describe, test, expect, beforeEach } from '@jest/globals';
import { SkinRegistry } from '../../../humanize/avatar/skin-registry.js';

describe('SkinRegistry', () => {
  const registry = SkinRegistry.getInstance();

  beforeEach(() => {
    registry.clearCustom();
  });

  test('should return singleton instance', () => {
    const instance1 = SkinRegistry.getInstance();
    const instance2 = SkinRegistry.getInstance();
    expect(instance1).toBe(instance2);
  });

  test('should have single-frame skin registered by default', () => {
    expect(registry.has('single-frame')).toBe(true);
  });

  test('should list single-frame skin in getNames', () => {
    const names = registry.getNames();
    expect(names).toContain('single-frame');
  });

  test('should create single-frame skin with options', () => {
    const skin = registry.create('single-frame', { spritePath: 'tests/test_single_frame.png' });
    expect(skin).not.toBeNull();
    expect(skin?.id).toBe('single-frame');
    expect(skin?.name).toBe('Single Frame');
  });

  test('should return null for unknown skin', () => {
    const skin = registry.create('nonexistent');
    expect(skin).toBeNull();
  });

  test('should register custom skin', () => {
    // Create a mock skin factory
    const mockSkin = { id: 'mock', name: 'Mock', frameWidth: 32, frameHeight: 32, spriteWidth: 64, spriteHeight: 64, getFrameRow: () => 0, getFrameCount: () => 1, getExpressionNames: () => ['mock'], getSpriteBuffer: () => Buffer.from([]) };
    registry.registerSkin('mock', () => mockSkin);
    expect(registry.has('mock')).toBe(true);
  });

  test('should create registered custom skin', () => {
    const mockSkin = { id: 'mock', name: 'Mock', frameWidth: 32, frameHeight: 32, spriteWidth: 64, spriteHeight: 64, getFrameRow: () => 0, getFrameCount: () => 1, getExpressionNames: () => ['mock'], getSpriteBuffer: () => Buffer.from([]) };
    registry.registerSkin('mock', () => mockSkin);
    const skin = registry.create('mock');
    expect(skin).toBe(mockSkin);
  });

  test('should get skin metadata', () => {
    const meta = registry.getMetadata('single-frame');
    expect(meta).not.toBeNull();
    expect(meta?.className).toBe('SingleFrameSkin');
  });

  test('should return null metadata for unknown skin', () => {
    const meta = registry.getMetadata('unknown');
    expect(meta).toBeNull();
  });

  test('should clear custom skins but keep built-in', () => {
    registry.registerSkin('custom', () => ({ id: 'custom', name: 'Custom', frameWidth: 16, frameHeight: 16, spriteWidth: 16, spriteHeight: 16, getFrameRow: () => 0, getFrameCount: () => 1, getExpressionNames: () => ['custom'], getSpriteBuffer: () => Buffer.from([]) }));
    registry.clearCustom();
    expect(registry.has('single-frame')).toBe(true);
    expect(registry.has('custom')).toBe(false);
  });
});
