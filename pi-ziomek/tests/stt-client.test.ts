/**
 * Tests for the STT client.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SttClient } from "../src/stt-client";

// A mock WebSocket class that satisfies `new WebSocket()`
class MockWebSocket {
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: Event) => void) | null = null;
  readyState = 1; // OPEN
  close = vi.fn();
  send = vi.fn();
  private _listeners: Map<string, Set<(...args: any[]) => void>> = new Map();

  addEventListener(event: string, fn: (...args: any[]) => void) {
    if (!this._listeners.has(event)) {
      this._listeners.set(event, new Set());
    }
    this._listeners.get(event)!.add(fn);
  }

  removeEventListener(event: string, fn: (...args: any[]) => void) {
    this._listeners.get(event)?.delete(fn);
  }

  private _emit(event: string, ...args: any[]) {
    this._listeners.get(event)?.forEach((fn) => fn(...args));
  }

  emitMessage(data: string) {
    const event = new MessageEvent("message", { data });
    // Invoke onmessage property (used by connect())
    if (this.onmessage) {
      this.onmessage(event);
    }
    // Also invoke addEventListener listeners (used by sendCommand())
    this._emit("message", event);
  }
}

let OriginalWebSocket: typeof WebSocket;
let lastWs: MockWebSocket | null = null; // Captures the WebSocket instance from connect()

describe("SttClient", () => {
  let client: SttClient;

  beforeEach(() => {
    client = new SttClient("http://localhost:5003");
    OriginalWebSocket = globalThis.WebSocket as unknown as typeof WebSocket;
    lastWs = null;
    // Replace global WebSocket — capture the instance for testing
    (globalThis as any).WebSocket = class WebSocket {
      private instance: MockWebSocket;
      static readonly OPEN = 1;
      constructor() {
        this.instance = new MockWebSocket();
        lastWs = this.instance;
      }
      get onopen() { return this.instance.onopen; }
      set onopen(v) { this.instance.onopen = v; }
      get onmessage() { return this.instance.onmessage; }
      set onmessage(v) { this.instance.onmessage = v; }
      get onerror() { return this.instance.onerror; }
      set onerror(v) { this.instance.onerror = v; }
      get onclose() { return this.instance.onclose; }
      set onclose(v) { this.instance.onclose = v; }
      get readyState() { return this.instance.readyState; }
      close() { return this.instance.close(); }
      send(msg: string) { return this.instance.send(msg); }
      addEventListener(event: string, fn: any) { return this.instance.addEventListener(event, fn); }
      removeEventListener(event: string, fn: any) { return this.instance.removeEventListener(event, fn); }
    } as unknown as typeof WebSocket;
  });

  afterEach(() => {
    client.disconnect();
    (globalThis as any).WebSocket = OriginalWebSocket;
    vi.restoreAllMocks();
    lastWs = null;
  });

  describe("connect", () => {
    it("resolves when WebSocket opens", async () => {
      const connectPromise = client.connect();
      // Manually trigger onopen to simulate successful connection
      lastWs?.onopen?.(new Event("open"));
      await connectPromise;
      expect(lastWs?.readyState).toBe(1);
    });

    it("rejects when WebSocket creation fails", async () => {
      (globalThis as any).WebSocket = class {
        constructor() {
          throw new Error("Invalid URL");
        }
      } as unknown as typeof WebSocket;

      await expect(client.connect()).rejects.toThrow("Invalid URL");
    });
  });

  describe("message handling", () => {
    it("calls transcription callbacks on transcription messages", async () => {
      const connectPromise = client.connect();
      lastWs?.onopen?.(new Event("open"));
      await connectPromise;

      const transcriptionCb = vi.fn();
      client.onTranscription(transcriptionCb);

      lastWs?.emitMessage(
        JSON.stringify({
          type: "transcription",
          text: "Hello world",
          is_final: true,
          realtime: false,
        }),
      );

      expect(transcriptionCb).toHaveBeenCalledWith({
        text: "Hello world",
        isFinal: true,
        realtime: false,
      });
    });

    it("calls status callbacks on status messages", async () => {
      const connectPromise = client.connect();
      lastWs?.onopen?.(new Event("open"));
      await connectPromise;

      const statusCb = vi.fn();
      client.onStatus(statusCb);

      lastWs?.emitMessage(
        JSON.stringify({ type: "status", state: "recording" }),
      );

      expect(statusCb).toHaveBeenCalledWith("recording");
    });

    it("ignores malformed JSON messages", async () => {
      const connectPromise = client.connect();
      lastWs?.onopen?.(new Event("open"));
      await connectPromise;

      const transcriptionCb = vi.fn();
      client.onTranscription(transcriptionCb);

      lastWs?.emitMessage("not json {{{");
      expect(() => lastWs?.emitMessage("not json {{{")).not.toThrow();
      expect(transcriptionCb).not.toHaveBeenCalled();
    });
  });

  describe("start/stop", () => {
    it("returns false when not connected", async () => {
      (globalThis as any).WebSocket = class {
        constructor() {
          throw new Error("No WS");
        }
      } as unknown as typeof WebSocket;
      const result = await client.start();
      expect(result).toBe(false);
    });

    it("sends command when connected", async () => {
      const connectPromise = client.connect();
      lastWs?.onopen?.(new Event("open"));
      await connectPromise;

      // Start the command — it returns a Promise that waits for a response
      const startPromise = client.start();

      // Yield one microtask so sendCommand registers its listener
      await Promise.resolve();

      // Now send the response
      lastWs?.emitMessage(
        JSON.stringify({
          type: "command_result",
          command: "start",
          success: true,
        }),
      );

      const result = await startPromise;
      expect(result).toBe(true);
    });
  });

  describe("getStatus", () => {
    it("returns state on success", async () => {
      const mockResponse = {
        state: "recording",
        engine: "faster_whisper",
        model: "tiny.en",
        transcription_count: 42,
      };
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const state = await client.getStatus();
      expect(state).toEqual({
        state: "recording",
        engine: "faster_whisper",
        model: "tiny.en",
        transcriptionCount: 42,
      });
    });

    it("returns null on failure", async () => {
      vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));

      const state = await client.getStatus();
      expect(state).toBeNull();
    });
  });

  describe("reconfigure", () => {
    it("returns true on success", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
      } as Response);

      const result = await client.reconfigure("faster_whisper", "base.en");
      expect(result).toBe(true);
    });

    it("returns false on failure", async () => {
      vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));

      const result = await client.reconfigure();
      expect(result).toBe(false);
    });
  });

  describe("disconnect", () => {
    it("closes the WebSocket", async () => {
      const connectPromise = client.connect();
      lastWs?.onopen?.(new Event("open"));
      await connectPromise;

      client.disconnect();
      expect(lastWs?.close).toHaveBeenCalled();
    });
  });

  describe("isConnected", () => {
    it("returns false before connect", () => {
      expect(client.isConnected()).toBe(false);
    });

    it("returns true after connect", async () => {
      const connectPromise = client.connect();
      lastWs?.onopen?.(new Event("open"));
      await connectPromise;
      expect(client.isConnected()).toBe(true);
    });
  });

  describe("setBaseUrl", () => {
    it("updates the base URL", () => {
      client.setBaseUrl("http://example.com:8080");
      vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));

      client.getStatus();

      const [url] = (globalThis.fetch as any).mock.calls[0];
      expect(url).toBe("http://example.com:8080/api/stt/status");
    });
  });

  describe("offTranscription / offStatus", () => {
    it("removes transcription callback", async () => {
      const connectPromise = client.connect();
      lastWs?.onopen?.(new Event("open"));
      await connectPromise;

      const cb1 = vi.fn();
      const cb2 = vi.fn();
      client.onTranscription(cb1);
      client.onTranscription(cb2);
      client.offTranscription(cb1);

      lastWs?.emitMessage(
        JSON.stringify({
          type: "transcription",
          text: "Hello",
          is_final: true,
        }),
      );

      expect(cb1).not.toHaveBeenCalled();
      expect(cb2).toHaveBeenCalled();
    });
  });

  describe("default base URL", () => {
    it("uses the ziomek server port when no URL is given", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => ({ state: "idle", engine: "faster_whisper", model: "tiny.en", transcriptionCount: 0 }),
      } as Response);

      await new SttClient().getStatus();

      const [url] = (globalThis.fetch as any).mock.calls[0];
      expect(url.startsWith("http://localhost:5004")).toBe(true);
    });
  });
});
