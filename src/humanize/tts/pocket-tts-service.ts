import { TTSService, SpeechStatus } from './tts-service.js';
import { Logger } from '../../logger.js';

/** Configuration for the Ziomek TTS HTTP client. */
export interface ZiomekTTSConfig {
  /** Base URL of the ziomek server (default: http://localhost:5003). */
  url?: string;
  /** Default voice to use for synthesis. */
  voice?: string;
  /** Request timeout in milliseconds (default: 30000). */
  timeoutMs?: number;
}

const DEFAULTS = {
  url: 'http://localhost:5003',
  voice: 'cosette',
  timeoutMs: 30_000,
} as const;

/**
 * HTTP client for the ziomek TTS server.
 *
 * Communicates with a locally running ziomek server via HTTP.
 * No Python process management — the server must be started separately.
 */
export class ZiomekTTSClient extends TTSService {
  private readonly _url: string;
  private readonly _voice: string;
  private readonly _timeoutMs: number;
  private readonly _logger: Logger;
  private _isAvailableCache: boolean | null = null;

  private _speakResolve: (() => void) | null = null;
  private _abort: boolean = false;

  constructor(config?: ZiomekTTSConfig) {
    super();
    this._url = config?.url ?? DEFAULTS.url;
    this._voice = config?.voice ?? DEFAULTS.voice;
    this._timeoutMs = config?.timeoutMs ?? DEFAULTS.timeoutMs;
    this._logger = new Logger('debug');

    if (!this._url.endsWith('/')) {
      this._url = this._url + '/';
    }
  }

  /** Check if the ziomek server is reachable. */
  private async _checkServer(): Promise<boolean> {
    try {
      const url = `${this._url}api/tts/status`;
      const res = await fetch(url, {
        method: 'GET',
        signal: AbortSignal.timeout(3000),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  override speak(text: string): Promise<void> {
    return new Promise<void>((resolve) => {
      // Check server availability (with cache)
      if (this._isAvailableCache === null) {
        // Don't block — check async
        this._checkServer().then((available) => {
          this._isAvailableCache = available;
          if (!available) {
            this._logger.error('ziomek-tts', 'ziomek server not reachable');
            this._setStatus('error');
            resolve();
            return;
          }
          this._doSpeak(text, resolve);
        });
        return;
      }

      if (!this._isAvailableCache) {
        this._logger.error('ziomek-tts', 'ziomek server not available');
        this._setStatus('error');
        resolve();
        return;
      }

      this._doSpeak(text, resolve);
    });
  }

  /** Perform the POST to the ziomek server. */
  private _doSpeak(text: string, resolve: () => void): void {
    if (this._abort) {
      this._setStatus('idle');
      this._speakResolve?.();
      this._speakResolve = null;
      return;
    }

    this._setStatus('speaking');
    this._abort = false;
    this._speakResolve = resolve;

    const url = `${this._url}api/tts/speak`;

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice: this._voice }),
      signal: AbortSignal.timeout(this._timeoutMs),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(() => {
        if (this._abort) return;
        this._setStatus('idle');
        this._speakResolve?.();
        this._speakResolve = null;
      })
      .catch((err) => {
        if (this._abort) return;
        const msg = err instanceof Error ? err.message : String(err);
        this._logger.error('ziomek-tts', `POST /api/tts/speak failed: ${msg}`);
        this._isAvailableCache = null; // force re-check
        this._setStatus('error');
        this._speakResolve?.();
        this._speakResolve = null;
      });
  }

  override stop(): Promise<void> {
    this._abort = true;
    this._setStatus('stopping');

    if (this._speakResolve) {
      this._speakResolve();
      this._speakResolve = null;
    }

    this._setStatus('idle');
    return Promise.resolve();
  }

  override getStatus(): SpeechStatus {
    return this._status;
  }

  override isAvailable(): boolean {
    if (this._isAvailableCache === null) {
      // Can't block on async check — return unknown
      return true; // Assume available until proven otherwise
    }
    return this._isAvailableCache;
  }

  /** Clean up resources. */
  cleanup(): void {
    this._abort = true;
    if (this._speakResolve) {
      this._speakResolve();
      this._speakResolve = null;
    }
    this._isAvailableCache = null;
  }
}

// Keep PocketTTSService as an alias for backward compatibility
export { ZiomekTTSClient as PocketTTSService };
