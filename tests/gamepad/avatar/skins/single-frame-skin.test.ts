import { describe, test, expect } from '@jest/globals';
import { SingleFrameSkin } from '../../../../src/gamepad/avatar/skins/single-frame-skin.js';

describe('SingleFrameSkin', () => {
  test('should create skin with default sprite path', () => {
    const skin = new SingleFrameSkin({ spritePath: 'tests/test_single_frame.png' });
    expect(skin.id).toBe('single-frame');
    expect(skin.name).toBe('Single Frame');
  });

  test('should report sprite dimensions', () => {
    const skin = new SingleFrameSkin({ spritePath: 'tests/test_single_frame.png' });
    expect(skin.spriteWidth).toBe(100);
    expect(skin.spriteHeight).toBe(600);
  });

  test('should calculate frame dimensions', () => {
    const skin = new SingleFrameSkin({ spritePath: 'tests/test_single_frame.png' });
    expect(skin.frameWidth).toBe(100);
    expect(skin.frameHeight).toBe(100);
  });

  test('should map expressions to rows', () => {
    const skin = new SingleFrameSkin({ spritePath: 'tests/test_single_frame.png' });
    // Check that all expected expressions are mapped
    expect(skin.getFrameRow('happy', 0)).toBe(0);
    expect(skin.getFrameRow('surprised', 0)).toBe(1);
    expect(skin.getFrameRow('curious', 0)).toBe(2);
    expect(skin.getFrameRow('looking', 0)).toBe(2);
    expect(skin.getFrameRow('focused', 0)).toBe(3);
    expect(skin.getFrameRow('thinking', 0)).toBe(2);
    expect(skin.getFrameRow('dying', 0)).toBe(4);
    expect(skin.getFrameRow('bored', 0)).toBe(3);
    expect(skin.getFrameRow('neutral', 0)).toBe(1);
  });

  test('should return 1 frame count per expression', () => {
    const skin = new SingleFrameSkin({ spritePath: 'tests/test_single_frame.png' });
    expect(skin.getFrameCount('happy')).toBe(1);
    expect(skin.getFrameCount('dying')).toBe(1);
  });

  test('should return expression names', () => {
    const skin = new SingleFrameSkin({ spritePath: 'tests/test_single_frame.png' });
    const names = skin.getExpressionNames();
    expect(names).toContain('happy');
    expect(names).toContain('dying');
    expect(names).toContain('bored');
    expect(names).toContain('neutral');
  });

  test('should default to neutral row for unknown expressions', () => {
    const skin = new SingleFrameSkin({ spritePath: 'tests/test_single_frame.png' });
    expect(skin.getFrameRow('unknown_expression', 0)).toBe(1);
  });
});
