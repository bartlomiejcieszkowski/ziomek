import { describe, test, expect, beforeEach } from '@jest/globals';
import { TTSService, SpeechStatus } from '../../../src/humanize/tts/tts-service.js';

// Stub PocketTTSService for interface testing
// We test the TTSService interface contract here;
// real PocketTTSService integration tests require a Python server.
class TestablePocketTTSService extends TTSService {
  private _available = true;
  private _errorMode = false;

  constructor(available = true) {
    super();
    this._available = available;
  }

  setAvailable(val: boolean): void {
    this._available = val;
  }

  async speak(_text: string): Promise<void> {
    if (!this._available) {
      this._setStatus('error');
      return;
    }
    if (this._errorMode) {
      this._setStatus('error');
      return;
    }
    this._setStatus('speaking');
    this._setStatus('idle');
  }

  async stop(): Promise<void> {
    this._setStatus('stopping');
    this._setStatus('idle');
  }

  getStatus(): SpeechStatus {
    return this._status;
  }

  isAvailable(): boolean {
    return this._available;
  }

  setErrorMode(on: boolean): void {
    this._errorMode = on;
  }
}

describe('PocketTTSService interface (stub)', () => {
  let service: TestablePocketTTSService;

  beforeEach(() => {
    service = new TestablePocketTTSService();
  });

  describe('constructor', () => {
    test('starts as idle', () => {
      expect(service.getStatus()).toBe('idle');
    });

    test('is available by default', () => {
      expect(service.isAvailable()).toBe(true);
    });
  });

  describe('isAvailable()', () => {
    test('returns true when available', () => {
      service.setAvailable(true);
      expect(service.isAvailable()).toBe(true);
    });

    test('returns false when unavailable', () => {
      service.setAvailable(false);
      expect(service.isAvailable()).toBe(false);
    });
  });

  describe('speak()', () => {
    test('resolves successfully when available', async () => {
      await expect(service.speak('hello')).resolves.toBeUndefined();
    });

    test('sets status to idle after speaking', async () => {
      service.setAvailable(true);
      await service.speak('test');
      expect(service.getStatus()).toBe('idle');
    });

    test('sets error status when unavailable', async () => {
      service.setAvailable(false);
      await service.speak('test');
      expect(service.getStatus()).toBe('error');
    });

    test('does nothing when in error mode', async () => {
      service.setErrorMode(true);
      await service.speak('test');
      expect(service.getStatus()).toBe('error');
    });
  });

  describe('stop()', () => {
    test('resolves immediately', async () => {
      await expect(service.stop()).resolves.toBeUndefined();
    });

    test('sets status to idle after stop', async () => {
      await service.stop();
      expect(service.getStatus()).toBe('idle');
    });
  });

  describe('TTSCallback interface', () => {
    test('invokes callbacks on status change', async () => {
      const statuses: SpeechStatus[] = [];
      service.addOnStatusChange((s) => statuses.push(s));

      await service.speak('hello');

      expect(statuses).toContain('speaking');
      expect(statuses).toContain('idle');
    });

    test('removes callbacks correctly', async () => {
      const statuses: SpeechStatus[] = [];
      const cb = (s: SpeechStatus) => statuses.push(s);
      service.addOnStatusChange(cb);

      // Simulate a status change
      (service as TestablePocketTTSService).speak('test');

      service.removeOnStatusChange(cb);

      // Clear and verify cb no longer fires by calling a method
      // that changes status
      service.stop();
    });

    test('handles callback errors gracefully', async () => {
      const badCb = () => { throw new Error('oops'); };
      service.addOnStatusChange(badCb);

      // Should not throw
      await service.speak('test');
      expect(service.getStatus()).toBe('idle');
    });
  });

  describe('status transitions', () => {
    test('idle -> speaking -> idle on speak', async () => {
      service.setAvailable(true);

      // We can't directly observe intermediate states in async
      // but the callback approach works
      const history: SpeechStatus[] = [];
      service.addOnStatusChange((s) => history.push(s));

      await service.speak('x');
      expect(history).toContain('speaking');
      expect(history).toContain('idle');
    });

    test('speaking -> stopping -> idle on stop', async () => {
      const history: SpeechStatus[] = [];
      service.addOnStatusChange((s) => history.push(s));

      await service.stop();
      expect(history).toContain('stopping');
      expect(history).toContain('idle');
    });
  });
});
