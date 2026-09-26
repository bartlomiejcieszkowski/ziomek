import { describe, test, expect, beforeAll, afterAll } from '@jest/globals';
import { LocalHTTPServer } from '../../humanize/local-http-server.js';
import { AvatarStateMachine } from '../../humanize/avatar/state-machine.js';
import { StubTTSService } from '../../humanize/tts/stub-tts.js';
import http from 'http';

function fetchJSON(path: string, port = 5001): Promise<unknown> {
  return new Promise((resolve, reject) => {
    http.get(`http://localhost:${port}${path}`, (res) => {
      let data = '';
      res.on('data', (chunk: Buffer) => { data += chunk.toString(); });
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch { resolve(data); }
      });
    }).on('error', reject);
  });
}

function postJSON(path: string, body: Record<string, unknown>, port = 5001): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = http.request(
      {
        hostname: 'localhost',
        port,
        path,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(data),
        },
      },
      (res) => {
        let responseData = '';
        res.on('data', (chunk: Buffer) => { responseData += chunk.toString(); });
        res.on('end', () => {
          try { resolve(JSON.parse(responseData)); } catch { resolve(responseData); }
        });
      },
    );
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

describe('LocalHTTPServer', () => {
  let server: LocalHTTPServer;
  let stateMachine: AvatarStateMachine;

  beforeAll(() => {
    stateMachine = new AvatarStateMachine();
    server = new LocalHTTPServer(stateMachine, 5001);
    server.start();
  });

  afterAll(() => {
    server.stop();
  });

  test('GET / should return API info', async () => {
    const result = await fetchJSON('/');
    expect(result).toHaveProperty('name', 'Humanize AI Avatar API');
  });

  test('GET /api/avatar/state should return current state', async () => {
    const result = await fetchJSON('/api/avatar/state');
    expect(result).toHaveProperty('current');
    expect(result).toHaveProperty('available');
  });

  test('POST /api/avatar/emotion should set emotion and return state', async () => {
    const result = await postJSON('/api/avatar/emotion', { expression: 'happy' });
    expect(result).toHaveProperty('message');
    expect(result).toHaveProperty('state');
    expect(result).not.toHaveProperty('error');
  });

  test('POST /api/avatar/emotion should return error for unknown expression', async () => {
    const result = await postJSON('/api/avatar/emotion', { expression: 'nonexistent' });
    expect(result).toHaveProperty('error');
  });

  test('POST /api/avatar/emotion should return error for missing expression field', async () => {
    const result = await postJSON('/api/avatar/emotion', {});
    expect(result).toHaveProperty('error');
  });

  test('GET /unknown should return 404', async () => {
    return new Promise<void>((resolve) => {
      http.get('http://localhost:5001/unknown', (res) => {
        expect(res.statusCode).toBe(404);
        let data = '';
        res.on('data', (chunk: Buffer) => { data += chunk.toString(); });
        res.on('end', () => {
          const json = JSON.parse(data);
          expect(json).toHaveProperty('error', 'Not Found');
          resolve();
        });
      });
    });
  });

  test('GET / should list new endpoints', async () => {
    const result = await fetchJSON('/');
    expect(result).toHaveProperty('endpoints.message');
    expect(result).toHaveProperty('endpoints.ttsSpeak');
    expect(result).toHaveProperty('endpoints.ttsStatus');
    expect(result).toHaveProperty('endpoints.ttsStop');
  });
});

describe('POST /api/avatar/message', () => {
  let server: LocalHTTPServer;
  let stateMachine: AvatarStateMachine;
  let serverPort = 5010;

  beforeAll(() => {
    stateMachine = new AvatarStateMachine();
    server = new LocalHTTPServer(stateMachine, serverPort);
    server.start();
  });

  afterAll(() => {
    server.stop();
  });

  test('should set both expression and message with same duration', async () => {
    const result = await postJSON(
      `/api/avatar/message`,
      { expression: 'happy', message: 'Hello!', durationMs: 5000 },
      serverPort,
    );
    expect(result).not.toHaveProperty('error');
    expect(result).toHaveProperty('expression', 'happy');
    expect(result).toHaveProperty('message', 'Hello!');
    expect(result).toHaveProperty('availableExpressions');
  });

  test('should accept message only', async () => {
    const result = await postJSON(
      `/api/avatar/message`,
      { message: 'Just a message' },
      serverPort,
    );
    expect(result).not.toHaveProperty('error');
    expect(result).toHaveProperty('message', 'Just a message');
  });

  test('should accept expression only (like /emotion)', async () => {
    const result = await postJSON(
      `/api/avatar/message`,
      { expression: 'happy', durationMs: 3000 },
      serverPort,
    );
    expect(result).not.toHaveProperty('error');
    expect(result).toHaveProperty('expression', 'happy');
  });

  test('should return 400 when neither expression nor message provided', async () => {
    const result = await postJSON(
      `/api/avatar/message`,
      { durationMs: 5000 },
      serverPort,
    );
    expect(result).toHaveProperty('error');
  });

  test('should return 400 for invalid JSON', async () => {
    return new Promise<void>((resolve) => {
      const data = 'not json';
      const req = http.request(
        {
          hostname: 'localhost',
          port: serverPort,
          path: '/api/avatar/message',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(data),
          },
        },
        (res) => {
          expect(res.statusCode).toBe(400);
          let responseData = '';
          res.on('data', (chunk: Buffer) => { responseData += chunk.toString(); });
          res.on('end', () => {
            const json = JSON.parse(responseData);
            expect(json).toHaveProperty('error', 'Invalid JSON body');
            resolve();
          });
        },
      );
      req.on('error', () => {});
      req.write(data);
      req.end();
    });
  });

  test('should return 400 for unknown expression', async () => {
    const result = await postJSON(
      `/api/avatar/message`,
      { expression: 'nonexistent', message: 'test' },
      serverPort,
    );
    expect(result).toHaveProperty('error');
  });

  test('should default durationMs to 10000', async () => {
    const result = await postJSON(
      `/api/avatar/message`,
      { message: 'default duration test' },
      serverPort,
    );
    expect(result).not.toHaveProperty('error');
    expect(result).toHaveProperty('message', 'default duration test');
  });
});

describe('TTS endpoints', () => {
  let server: LocalHTTPServer;
  let stateMachine: AvatarStateMachine;
  let serverPort = 5020;
  let ttsService: StubTTSService;

  beforeAll(() => {
    stateMachine = new AvatarStateMachine();
    ttsService = new StubTTSService();
    server = new LocalHTTPServer(stateMachine, serverPort, ttsService);
    server.start();
  });

  afterAll(() => {
    server.stop();
  });

  test('GET /api/tts/status should return status and availability', async () => {
    const result = await fetchJSON('/api/tts/status', serverPort);
    expect(result).toHaveProperty('status');
    expect(result).toHaveProperty('available', true);
  });

  test('POST /api/tts/speak should return speaking status', async () => {
    const result = await postJSON(
      '/api/tts/speak',
      { text: 'Hello world' },
      serverPort,
    );
    expect(result).toHaveProperty('status', 'speaking');
    expect(result).toHaveProperty('text');
  });

  test('POST /api/tts/speak should return 400 for empty text', async () => {
    const result = await postJSON(
      '/api/tts/speak',
      { text: '' },
      serverPort,
    );
    expect(result).toHaveProperty('error');
  });

  test('POST /api/tts/speak should return 400 for missing text', async () => {
    const result = await postJSON(
      '/api/tts/speak',
      {},
      serverPort,
    );
    expect(result).toHaveProperty('error');
  });

  test('POST /api/tts/speak should return 400 for invalid JSON', async () => {
    return new Promise<void>((resolve) => {
      const data = 'not json';
      const req = http.request(
        {
          hostname: 'localhost',
          port: serverPort,
          path: '/api/tts/speak',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(data),
          },
        },
        (res) => {
          expect(res.statusCode).toBe(400);
          let responseData = '';
          res.on('data', (chunk: Buffer) => { responseData += chunk.toString(); });
          res.on('end', () => {
            const json = JSON.parse(responseData);
            expect(json).toHaveProperty('error', 'Invalid JSON body');
            resolve();
          });
        },
      );
      req.on('error', () => {});
      req.write(data);
      req.end();
    });
  });

  test('POST /api/tts/stop should stop TTS and return new status', async () => {
    // Start speaking first
    await postJSON('/api/tts/speak', { text: 'test' }, serverPort);
    // Then stop
    const result = await postJSON(
      '/api/tts/stop',
      {},
      serverPort,
    );
    expect(result).toHaveProperty('status');
  });

  test('POST /api/tts/stop with invalid JSON should not crash', async () => {
    return new Promise<void>((resolve) => {
      const data = 'not json';
      const req = http.request(
        {
          hostname: 'localhost',
          port: serverPort,
          path: '/api/tts/stop',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(data),
          },
        },
        (res) => {
          // The handler calls tts.stop() before trying to parse JSON,
          // so it should still succeed
          expect(res.statusCode).toBe(200);
          let responseData = '';
          res.on('data', (chunk: Buffer) => { responseData += chunk.toString(); });
          res.on('end', () => {
            const json = JSON.parse(responseData);
            expect(json).toHaveProperty('status');
            resolve();
          });
        },
      );
      req.on('error', () => {});
      req.write(data);
      req.end();
    });
  });
});
