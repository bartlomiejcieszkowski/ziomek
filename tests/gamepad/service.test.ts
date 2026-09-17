import { GamepadService } from '../../src/gamepad/service';

describe('GamepadService', () => {
  test('should be defined', () => {
    const service = new GamepadService();
    expect(service).toBeDefined();
  });
});
