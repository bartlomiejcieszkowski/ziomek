import { describe, test, expect, beforeAll, afterAll, beforeEach } from '@jest/globals';
import { spawn, type ChildProcess } from 'node:child_process';
import type { SpawnOptions } from 'node:child_process';
import { PocketTTSService } from '../../../humanize/tts/pocket-tts-service.js';

// Use an ephemeral port to avoid collisions
const TEST_PORT = 19877;

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

if (skipSuite) {
  test.skip('PocketTTSService — skipped (uv/pocket_tts not available)', () => {});
} else {
  describe('PocketTTSService — integration tests (real server)', () => {
    let child: ChildProcess | null = null;
    let service: PocketTTSService;

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
      await waitForServer(`http://localhost:${TEST_PORT}`);
    }, 60_000);

    beforeEach(() => {
      service = new PocketTTSService({
        port: TEST_PORT,
        voice: 'default',
        timeoutMs: 30_000,
      } as any);
    });

    afterAll(() => {
      if (child) {
        killProcess(child);
      }
    });

    test('isAvailable returns true when Python is running', () => {
      expect(service.isAvailable()).toBe(true);
    });

    test('speak() completes successfully', async () => {
      const result = await service.speak('hello integration');
      expect(result).toBeUndefined();
    });

    test('speak() updates status through lifecycle', async () => {
      // Status starts as idle
      expect(service.getStatus()).toBe('idle');

      // Set up callback to track status changes
      const statuses: string[] = [];
      service.addOnStatusChange((s) => statuses.push(s));

      // speak will go: speaking → idle
      await service.speak('status test');

      expect(statuses).toContain('speaking');
      expect(statuses).toContain('idle');
      expect(service.getStatus()).toBe('idle');
    });

    test('stop() returns immediately', async () => {
      const result = await service.stop();
      expect(result).toBeUndefined();
      expect(service.getStatus()).toBe('idle');
    });

    test('stop() sets status to stopping then idle', async () => {
      const statuses: string[] = [];
      service.addOnStatusChange((s) => statuses.push(s));

      await service.stop();

      expect(statuses).toContain('stopping');
      expect(statuses).toContain('idle');
    });

    test('multiple speak() calls work in sequence', async () => {
      await service.speak('first');
      await service.speak('second');
      await service.speak('third');
      expect(service.getStatus()).toBe('idle');
    });

    test('callback errors do not prevent status transitions', async () => {
      const badCb = () => {
        throw new Error('intentional error');
      };
      service.addOnStatusChange(badCb);

      // Should not throw
      await service.speak('test with bad callback');
      expect(service.getStatus()).toBe('idle');
    });

    test('cleanup() resets state', async () => {
      // First speak to populate cache
      service.isAvailable();

      // Now cleanup
      if ('cleanup' in service) {
        (service as { cleanup: () => void }).cleanup();
      }

      // After cleanup, isAvailable should re-check
      // The cache is reset so it will try spawnSync again
      // We expect it to still find python (it's running)
      service.isAvailable();
    });
  });
}
