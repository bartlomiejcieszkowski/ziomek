import { describe, test, expect, beforeEach, jest } from '@jest/globals';
import { StubTTSService } from '../../../humanize/tts/stub-tts.js';
import { TTSService, SpeechStatus } from '../../../humanize/tts/tts-service.js';

describe('StubTTSService', () => {
  let tts: StubTTSService;

  beforeEach(() => {
    tts = new StubTTSService();
  });

  test('should start in idle status', () => {
    expect(tts.getStatus()).toBe('idle');
  });

  test('should transition to speaking then idle on speak()', async () => {
    jest.useFakeTimers();

    const promise = tts.speak('hello');

    expect(tts.getStatus()).toBe('speaking');

    jest.advanceTimersByTime(2000);

    await promise;
    expect(tts.getStatus()).toBe('idle');

    jest.useRealTimers();
  }, 10000);

  test('should set status to stopping then idle on stop()', async () => {
    tts.stop();
    expect(tts.getStatus()).toBe('idle');
  }, 10000);

  test('should call status change callbacks when status changes', async () => {
    jest.useFakeTimers();

    const statuses: SpeechStatus[] = [];
    const callback = (status: SpeechStatus) => statuses.push(status);

    tts.addOnStatusChange(callback);

    const promise = tts.speak('hello');

    jest.advanceTimersByTime(2000);

    await promise;

    expect(statuses).toEqual(['speaking', 'idle']);

    tts.removeOnStatusChange(callback);
    jest.useRealTimers();
  }, 10000);

  test('should remove callbacks on removeOnStatusChange', async () => {
    jest.useFakeTimers();

    const firstCallCount = { count: 0 };
    const secondCallCount = { count: 0 };

    const firstCallback = (_status: SpeechStatus) => {
      firstCallCount.count++;
    };
    const secondCallback = (_status: SpeechStatus) => {
      secondCallCount.count++;
    };

    tts.addOnStatusChange(firstCallback);
    const promise1 = tts.speak('hello');
    jest.advanceTimersByTime(2000);
    await promise1;
    expect(firstCallCount.count).toBe(2);

    tts.removeOnStatusChange(firstCallback);
    tts.addOnStatusChange(secondCallback);
    const promise2 = tts.speak('world');
    jest.advanceTimersByTime(2000);
    await promise2;
    expect(firstCallCount.count).toBe(2);
    expect(secondCallCount.count).toBe(2);

    jest.useRealTimers();
  }, 10000);

  test('should handle error status correctly', () => {
    tts['_setStatus']('error');
    expect(tts.getStatus()).toBe('error');
  });

  test('should always report isAvailable as true', () => {
    expect(tts.isAvailable()).toBe(true);
  });

  test('should handle multiple concurrent speak calls', async () => {
    jest.useFakeTimers();

    const call1 = tts.speak('first');
    const call2 = tts.speak('second');

    expect(tts.getStatus()).toBe('speaking');

    const promise1 = call1;
    const promise2 = call2;

    jest.advanceTimersByTime(2000);

    await promise1;
    await promise2;

    expect(tts.getStatus()).toBe('idle');

    jest.useRealTimers();
  }, 10000);
});

describe('TTSService base class', () => {
  test('should be abstract — cannot instantiate directly', () => {
    // TTSService is abstract in TypeScript — direct instantiation is a compile-time error.
    // At runtime (ES2015+), the constructor still works but abstract methods are unbound.
    // @ts-expect-error — intentionally testing abstract class instantiation
    const instance = new TTSService();
    expect(() => instance.speak('text')).toThrow();
    expect(() => instance.stop()).toThrow();
    expect(() => instance.getStatus()).toThrow();
    expect(() => instance.isAvailable()).toThrow();
  });

  test('should allow multiple status change callbacks', async () => {
    jest.useFakeTimers();

    class TestTTSService extends TTSService {
      override speak(_text: string): Promise<void> {
        this._setStatus('speaking');
        return new Promise<void>((resolve) => {
          setTimeout(() => {
            this._setStatus('idle');
            resolve();
          }, 1000);
        });
      }

      override stop(): Promise<void> {
        this._setStatus('stopping');
        this._setStatus('idle');
        return Promise.resolve();
      }

      override getStatus(): SpeechStatus {
        return this._status;
      }

      override isAvailable(): boolean {
        return true;
      }
    }

    const service = new TestTTSService();

    const received1: SpeechStatus[] = [];
    const received2: SpeechStatus[] = [];

    service.addOnStatusChange((status) => received1.push(status));
    service.addOnStatusChange((status) => received2.push(status));

    const promise = service.speak('test');

    jest.advanceTimersByTime(1000);

    await promise;

    expect(received1).toEqual(['speaking', 'idle']);
    expect(received2).toEqual(['speaking', 'idle']);

    jest.useRealTimers();
  }, 10000);
});
