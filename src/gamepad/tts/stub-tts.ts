import { TTSService, SpeechStatus } from './tts-service.js';

/**
 * A stub TTS implementation suitable for environments where no real
 * speech synthesis engine is available (e.g., during tests or CI).
 *
 * Simulates speech by sleeping for 2 seconds per `speak` call.
 */
export class StubTTSService extends TTSService {
  override speak(text: string): Promise<void> {
    this._setStatus('speaking');
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        this._setStatus('idle');
        resolve();
      }, 2000);
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
