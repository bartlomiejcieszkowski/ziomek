import { TTSService, SpeechStatus } from './tts-service.js';
import {
  spawn,
  spawnSync,
  type ChildProcess,
  type StdioOptions,
  type SpawnSyncOptions,
} from 'node:child_process';
import { Logger } from '../../logger.js';

/** Configuration for the Pocket TTS backend. */
export interface PocketTTSConfig {
  port?: number;
  modelPath?: string;
  voice?: string;
  timeoutMs?: number;
}

const DEFAULTS = {
  port: 5003,
  voice: 'default',
  timeoutMs: 30_000,
} as const;

/**
 * Pocket TTS service that wraps a Python HTTP server for speech synthesis.
 *
 * Manages the Python server lifecycle (lazy spawn, auto-reconnect, cleanup)
 * and exposes the TTSService interface with proper status callbacks.
 */
export class PocketTTSService extends TTSService {
  private readonly _port: number;
  private readonly _voice: string;
  private readonly _timeoutMs: number;
  private readonly _modelPath: string | undefined;

  private _child: ChildProcess | null = null;
  private readonly _logger: Logger;
  private _isAvailableCache: boolean | null = null;

  private _speakResolve: (() => void) | null = null;
  private _abort: boolean = false;

  constructor(config?: PocketTTSConfig) {
    super();
    this._port = config?.port ?? DEFAULTS.port;
    this._voice = config?.voice ?? DEFAULTS.voice;
    this._timeoutMs = config?.timeoutMs ?? DEFAULTS.timeoutMs;
    this._modelPath = config?.modelPath;
    this._logger = new Logger('debug');
  }

  /** Check if Python is available on the system PATH. */
  private _checkPython(): boolean {
    for (const pyCmd of ['python3', 'python']) {
      try {
        // SAFETY: spawnSync from node:child_process is available at
        // runtime in the VS Code extension host (Node.js environment).
        const result = spawnSync(pyCmd, ['--version'], {
          timeout: 2_000,
          stdio: ['ignore', 'ignore', 'pipe'],
        } as SpawnSyncOptions);
        if (result.status === 0) {
          return true;
        }
      } catch {
        // Python not found or spawn failed — try next
      }
    }
    return false;
  }

  /** Start the Pocket TTS Python server as a background process. */
  private _startServer(): void {
    if (this._child) return;

    try {
      const args: string[] = [];
      if (this._modelPath) {
        args.push('--model-path', this._modelPath);
      }
      args.push('--voice', this._voice);
      args.push('--port', String(this._port));

      // SAFETY: spawn from node:child_process returns a ChildProcess.
      // TypeScript stdio types are strict — we cast the stdio array
      // to the expected tuple type using an intermediate variable.
      const stdio: StdioOptions = ['ignore', 'ignore', 'pipe'];
      // SAFETY: spawn returns a ChildProcess; the type assertion
      // satisfies TypeScript's strict stdio validation.
      this._child = spawn(
        'python3',
        args,
        { stdio, detached: false } as SpawnSyncOptions,
      ) as unknown as ChildProcess;

      this._child.on('error', (err) => {
        this._logger.error('pocket-tts', `Python server error: ${err.message}`);
        this._child = null;
        this._isAvailableCache = false;
      });

      this._child.on('exit', (code, signal) => {
        this._logger.info(
          'pocket-tts',
          `Python server exited (code=${code}, signal=${signal})`,
        );
        this._child = null;
      });

      this._logger.info('pocket-tts', `Started Python server on port ${this._port}`);
    } catch (err) {
      this._logger.error(
        'pocket-tts',
        `Failed to start Python server: ${err instanceof Error ? err.message : String(err)}`,
      );
      this._isAvailableCache = false;
    }
  }

  /** Stop the Python server process. */
  private _stopServer(): void {
    if (!this._child) return;
    try {
      this._child.kill('SIGTERM');
    } catch {
      // Process may already be dead
    }
    this._child = null;
  }

  override speak(_text: string): Promise<void> {
    return new Promise<void>((resolve) => {
      // 1. Check availability (with cache)
      if (this._isAvailableCache === null) {
        this._isAvailableCache = this._checkPython();
      }
      if (!this._isAvailableCache) {
        this._logger.error('pocket-tts', 'Python not available for Pocket TTS');
        this._setStatus('error');
        resolve();
        return;
      }

      // 2. Start server if not running
      this._startServer();

      // 3. Wait briefly for server to be ready
      this._setStatus('speaking');
      this._abort = false;
      this._speakResolve = resolve;

      // Retry loop: wait for server, then POST
      this._doSpeak(_text);
    });
  }

  /** Actually perform the POST to the Python server, with retries. */
  private _doSpeak(text: string, retries: number = 3): void {
    if (this._abort) {
      this._setStatus('idle');
      this._speakResolve?.();
      this._speakResolve = null;
      return;
    }

    const url = `http://localhost:${this._port}/generate`;

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

        // Retry if server might not be ready yet
        if (retries > 0) {
          this._logger.warn(
            'pocket-tts',
            `POST /generate failed, retrying... (${retries} left): ${msg}`,
          );
          setTimeout(() => this._doSpeak(text, retries - 1), 500);
          return;
        }

        // Server may have died — kill and re-spawn on next speak
        this._logger.error('pocket-tts', `POST /generate failed after retries: ${msg}`);
        this._stopServer();
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

    this._stopServer();
    this._setStatus('idle');
    return Promise.resolve();
  }

  override getStatus(): SpeechStatus {
    return this._status;
  }

  override isAvailable(): boolean {
    if (this._isAvailableCache === null) {
      this._isAvailableCache = this._checkPython();
    }
    return this._isAvailableCache;
  }

  /** Clean up resources. Called on extension deactivate. */
  cleanup(): void {
    this._stopServer();
    this._child = null;
    this._isAvailableCache = null;
  }
}
