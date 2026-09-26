import { describe, test, expect, beforeEach, jest } from '@jest/globals';
import { AvatarWebSocketClient, AvatarStateUpdate } from '../../humanize/avatar/websocket-client.js';

// Mock WebSocket globally
const mockSend = jest.fn();
const mockClose = jest.fn();

class MockWebSocket {
  url: string;
  binaryType = 'arraybuffer' as const;
  onmessage: ((event: any) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  onopen: (() => void) | null = null;
  readyState: number = 0;
  bufferedAmount = 0;
  extensions = '';
  protocol = '';

  constructor(url: string) {
    this.url = url;
  }

  send(data: string) {
    mockSend(data);
  }

  close(code?: number, reason?: string) {
    mockClose(code, reason);
  }

  addEventListener(event: string, listener: any) {
    if (event === 'message') this.onmessage = listener;
    if (event === 'close') this.onclose = listener;
    if (event === 'error') this.onerror = listener;
    if (event === 'open') this.onopen = listener;
  }

  removeEventListener(event: string, listener: any) {
    // no-op
  }
}

global.WebSocket = MockWebSocket as any;

describe('AvatarWebSocketClient', () => {
  let client: AvatarWebSocketClient;

  beforeEach(() => {
    jest.clearAllMocks();
    client = new AvatarWebSocketClient('http://localhost:5004');
  });

  test('converts http to ws URL', () => {
    const c = new AvatarWebSocketClient('http://localhost:5004');
    expect((c as any)._ws).toBe(null);
    c.connect();
    const ws = (c as any)._ws as MockWebSocket;
    expect(ws.url).toBe('ws://localhost:5004');
  });

  test('converts https to wss URL', () => {
    const c = new AvatarWebSocketClient('https://example.com');
    c.connect();
    const ws = (c as any)._ws as MockWebSocket;
    expect(ws.url).toBe('wss://example.com');
  });

  test('has required methods', () => {
    expect(typeof client.connect).toBe('function');
    expect(typeof client.disconnect).toBe('function');
    expect(typeof client.onStateChange).toBe('function');
  });

  test('triggers onStateChange on message', () => {
    client.connect();
    const handler = jest.fn();
    client.onStateChange(handler);

    const ws = (client as any)._ws as MockWebSocket;
    ws.onmessage?.({ data: JSON.stringify({ expression: 'happy', cycleIndex: 0 }) });

    expect(handler).toHaveBeenCalledWith({ expression: 'happy', cycleIndex: 0 });
  });

  test('skips duplicate state updates', () => {
    client.connect();
    const handler = jest.fn();
    client.onStateChange(handler);

    const ws = (client as any)._ws as MockWebSocket;
    ws.onmessage?.({ data: JSON.stringify({ expression: 'happy', cycleIndex: 0 }) });
    ws.onmessage?.({ data: JSON.stringify({ expression: 'happy', cycleIndex: 0 }) });

    expect(handler).toHaveBeenCalledTimes(1);
  });

  test('triggers onStateChange on state change', () => {
    client.connect();
    const handler = jest.fn();
    client.onStateChange(handler);

    const ws = (client as any)._ws as MockWebSocket;
    ws.onmessage?.({ data: JSON.stringify({ expression: 'happy', cycleIndex: 0 }) });
    ws.onmessage?.({ data: JSON.stringify({ expression: 'bored', cycleIndex: 1 }) });

    expect(handler).toHaveBeenCalledTimes(2);
    expect(handler).toHaveBeenLastCalledWith({ expression: 'bored', cycleIndex: 1 });
  });

  test('disconnects and closes WebSocket', () => {
    client.connect();
    const ws = (client as any)._ws as MockWebSocket;
    expect(mockClose).not.toBeCalled();

    client.disconnect();

    expect(mockClose).toBeCalled();
    expect((client as any)._ws).toBe(null);
  });
});
