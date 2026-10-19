/**
 * Tests for the TTS client.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TtsClient } from "../src/tts-client";

describe("TtsClient", () => {
  let client: TtsClient;

  beforeEach(() => {
    client = new TtsClient("http://localhost:5003");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("speak", () => {
    it("returns success with wav path on 200", async () => {
      const mockResponse = { path: "/tmp/test.wav" };
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await client.speak("Hello world");
      expect(result.success).toBe(true);
      expect(result.wavPath).toBe("/tmp/test.wav");
    });

    it("returns error on non-200 response", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: false,
        statusText: "Not Found",
        text: async () => "Not found",
      } as Response);

      const result = await client.speak("Hello world");
      expect(result.success).toBe(false);
      expect(result.error).toContain("Not found");
    });

    it("returns error on network failure", async () => {
      vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));

      const result = await client.speak("Hello world");
      expect(result.success).toBe(false);
      expect(result.error).toBe("ECONNREFUSED");
    });

    it("passes voice parameter when provided", async () => {
      const mockResponse = { path: "/tmp/test.wav" };
      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      await client.speak("Hello world", "cosette");

      const [url, options] = fetchSpy.mock.calls[0];
      expect(url).toBe("http://localhost:5003/api/tts/synthesize");
      const body = JSON.parse((options as any).body);
      expect(body.text).toBe("Hello world");
      expect(body.voice).toBe("cosette");
    });
  });

  describe("cancel", () => {
    it("returns true on success", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
      } as Response);

      const result = await client.cancel();
      expect(result).toBe(true);
    });

    it("returns false on failure", async () => {
      vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));

      const result = await client.cancel();
      expect(result).toBe(false);
    });
  });

  describe("getVoices", () => {
    it("returns voices on success", async () => {
      const voices = [
        { name: "cosette", language: "en-US" },
        { name: "default", language: "en-US" },
      ];
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => voices,
      } as Response);

      const result = await client.getVoices();
      expect(result).toEqual(voices);
      expect(result).toHaveLength(2);
    });

    it("returns empty array on failure", async () => {
      vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));

      const result = await client.getVoices();
      expect(result).toEqual([]);
    });
  });

  describe("getLastWavPath", () => {
    it("returns null before any speak call", () => {
      expect(client.getLastWavPath()).toBeNull();
    });

    it("returns the wav path after successful speak", async () => {
      const mockResponse = { path: "/tmp/test.wav" };
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      await client.speak("Hello world");
      expect(client.getLastWavPath()).toBe("/tmp/test.wav");
    });

    it("returns null after failed speak", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: false,
        statusText: "Error",
        text: async () => "Error",
      } as Response);

      await client.speak("Hello world");
      expect(client.getLastWavPath()).toBeNull();
    });
  });

  describe("setBaseUrl", () => {
    it("updates the base URL", () => {
      client.setBaseUrl("http://example.com:8080");
      // We can't easily verify the private field, but we can test behavior
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: false,
        statusText: "Error",
        text: async () => "Error",
      } as Response);

      client.speak("test");

      const [url] = (globalThis.fetch as any).mock.calls[0];
      expect(url).toBe("http://example.com:8080/api/tts/synthesize");
    });
  });
});
