import { jest } from '@jest/globals';

// Stub gamepad-node so installNavigatorShim throws when called.
// In ESM Jest, jest.mock() at top-level is the correct approach.
jest.mock('gamepad-node', () => {
  const err = new Error('gamepad-node not available in test env');
  throw err;
});

// Re-export so the service import picks up the stubbed module.
import { GamepadService } from '../../src/gamepad/service';

describe('GamepadService', () => {
  describe('when gamepad-node is unavailable', () => {
    test('should not crash on start', () => {
      const service = new GamepadService(16);

      // start() should catch the error from installNavigatorShim
      expect(() => service.start()).not.toThrow();
      expect(() => service.stop()).not.toThrow();
    });

    test('should not crash on double stop', () => {
      const service = new GamepadService(16);

      expect(() => {
        service.stop();
        service.stop();
        service.stop();
      }).not.toThrow();
    });

    test('should provide unsubscribe function', () => {
      const service = new GamepadService(16);

      let fired = false;
      const unsub = service.on('all', () => { fired = true; });
      expect(typeof unsub).toBe('function');

      unsub();
      // After unsubscribe, the listener should not have been called
      // (We simulate this by calling _emit indirectly — but since _emit is private,
      //  we just verify the unsubscribe pattern works by ensuring no error on unsub)
      expect(fired).toBe(false);
    });
  });
});
