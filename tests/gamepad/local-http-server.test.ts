import { describe, test, expect, beforeAll, afterAll } from '@jest/globals';
import { LocalHTTPServer } from '../../src/gamepad/local-http-server.js';
import { AvatarStateMachine } from '../../src/gamepad/avatar/state-machine.js';
import http from 'http';

function fetchJSON(path: string): Promise<unknown> {
  return new Promise((resolve, reject) => {
    http.get(`http://localhost:5001${path}`, (res) => {
      let data = '';
      res.on('data', (chunk: Buffer) => { data += chunk.toString(); });
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch { resolve(data); }
      });
    }).on('error', reject);
  });
}

function postJSON(path: string, body: Record<string, unknown>): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = http.request(
      {
        hostname: 'localhost',
        port: 5001,
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
    expect(result).toHaveProperty('name', 'Gamify AI Avatar API');
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
});
