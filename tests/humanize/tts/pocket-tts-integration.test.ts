import { describe, test, expect, beforeAll, afterAll } from '@jest/globals';
import { spawn, type ChildProcess } from 'node:child_process';
import type { SpawnOptions } from 'node:child_process';

// Use an ephemeral port to avoid collisions
const TEST_PORT = 19876;

// Check if uv is available (try uv.exe on Windows as fallback)
function checkUV(): boolean {
  try {
    const { spawnSync } = require('child_process');
    const cmd = process.platform === 'win32' ? 'uv.exe' : 'uv';
    const { status } = spawnSync(cmd, ['--version'], {
      timeout: 3_000,
      stdio: ['ignore', 'ignore', 'pipe'],
    });
    return status === 0;
  } catch {
    return false;
  }
}

// Check if pocket_tts is installed (via uv run)
function checkPocketTTS(): boolean {
  try {
    const { spawnSync } = require('child_process');
    const cmd = process.platform === 'win32' ? 'uv.exe' : 'uv';
    const { status } = spawnSync(cmd, ['run', 'pocket-tts', '-c', 'import pocket_tts'], {
      timeout: 5_000,
      stdio: ['ignore', 'ignore', 'pipe'],
    });
    return status === 0;
  } catch {
    return false;
  }
}

// Wait for the server to become ready by polling /status
async function waitForServer(url: string, maxRetries: number = 20): Promise<void> {
  for (let i = 0; i < maxRetries; i += 1) {
    try {
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (data.ready === true) return;
      }
    } catch {
      // Server not ready yet
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error('Server did not become ready in time');
}

// Kill a process tree (works on Windows and Unix)
function killProcess(child: ChildProcess): void {
  try {
    // Kill the whole process group on Unix
    if (process.platform !== 'win32' && child.pid) {
      try {
        require('child_process').spawnSync('kill', [`-TERM`, `${child.pid}`]);
      } catch {
        // ignore
      }
    }
    child.kill('SIGTERM');
  } catch {
    // Process may already be dead
  }
}

const uvAvailable = checkUV();
const pocketTTSAvailable = checkPocketTTS();
const skipSuite = !uvAvailable || !pocketTTSAvailable;

describe.skipIf = function (
  condition: boolean,
  name: string,
  fn: () => void,
): void {
  if (condition) {
    test.skip(`Suite skipped: environment not available`, () => {});
  } else {
    describe(name, fn);
  }
};

if (skipSuite) {
  test.skip('Pocket TTS Server — skipped (uv/pocket_tts not available)', () => {});
} else {
  describe('Pocket TTS Server — integration tests', () => {
    let child: ChildProcess | null = null;
    const baseUrl = `http://localhost:${TEST_PORT}`;

    beforeAll(async () => {
      // Start the Python server on an ephemeral port
      const cmd = process.platform === 'win32' ? 'uv.exe' : 'uv';
      const args = ['run', 'pocket-tts', '--port', String(TEST_PORT)];
      child = spawn(cmd, args, {
        stdio: ['ignore', 'pipe', 'pipe'],
      } as SpawnOptions) as unknown as ChildProcess;

      child.on('error', () => {
        // Ignore — server may have already started
      });

      // Wait for server to be ready
      await waitForServer(baseUrl);
    }, 60_000);

    afterAll(() => {
      if (child) {
        killProcess(child);
      }
    });

    test('GET /status returns server info', async () => {
      const res = await fetch(`${baseUrl}/status`);
      expect(res.status).toBe(200);

      const data = await res.json();
      expect(data).toHaveProperty('ready', true);
      expect(data).toHaveProperty('voices');
      expect(data).toHaveProperty('model_loaded', true);
    });

    test('GET / returns server info', async () => {
      const res = await fetch(baseUrl);
      expect(res.status).toBe(200);

      const data = await res.json();
      expect(data.name).toBe('Pocket TTS Server');
      expect(data.endpoints.generate).toBe('POST /generate');
      expect(data.endpoints.status).toBe('GET /status');
    });

    test('POST /generate returns audio_b64', async () => {
      const res = await fetch(`${baseUrl}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: 'hello world' }),
      });

      expect(res.status).toBe(200);
      const data = await res.json();

      expect(data).toHaveProperty('audio_b64');
      expect(typeof data.audio_b64).toBe('string');
      expect(data).toHaveProperty('duration');
      expect(typeof data.duration).toBe('number');
      expect(data.duration).toBeGreaterThan(0);
      expect(data).toHaveProperty('sample_rate');
      expect(data).toHaveProperty('channels', 1);
      expect(data).toHaveProperty('bit_depth', 16);
      expect(data).toHaveProperty('voice', 'default');
    });

    test('POST /generate rejects missing text', async () => {
      const res = await fetch(`${baseUrl}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice: 'default' }),
      });

      expect(res.status).toBe(400);
      const data = await res.json();
      expect(data).toHaveProperty('error');
    });

    test('POST /generate with custom voice works', async () => {
      const res = await fetch(`${baseUrl}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: 'testing',
          voice: 'clipped',
        }),
      });

      expect(res.status).toBe(200);
      const data = await res.json();
      expect(data).toHaveProperty('audio_b64');
    });

    test('GET /unknown returns 404', async () => {
      const res = await fetch(`${baseUrl}/unknown`);
      expect(res.status).toBe(404);
      const data = await res.json();
      expect(data).toHaveProperty('error', 'Not Found');
    });

    test('POST /unknown returns 404', async () => {
      const res = await fetch(`${baseUrl}/unknown`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      expect(res.status).toBe(404);
    });
  });
}
