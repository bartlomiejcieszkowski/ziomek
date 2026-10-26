/**
 * Tests for the TTS client.
 *
 * The endpoints and response shapes here mirror the server implementation in
 * src/ziomek/api/tts.py: /api/tts/speak, /api/tts/generate, /api/tts/voices.
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
    it("returns success with playback details on 200", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => ({
          status: "playing",
          duration: 1.2,
          sample_rate: 24000,
          voice: "default",
        }),
      } as Response);

      const result = await client.speak("Hello world");
      expect(result.success).toBe(true);
      expect(result.duration).toBe(1.2);
      expect(result.sampleRate).toBe(24000);
    });

    it("calls the speak endpoint the server exposes", async () => {
      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => ({ status: "playing", duration: 0.5, sample_rate: 24000 }),
      } as Response);

      await client.speak("Hello world");

      const [url] = fetchSpy.mock.calls[0];
      expect(url).toBe("http://localhost:5003/api/tts/speak");
    });

    it("returns error on non-200 response", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
        text: async () => '{"error": "TTS not ready"}',
      } as Response);

      const result = await client.speak("Hello world");
      expect(result.success).toBe(false);
      expect(result.error).toContain("TTS not ready");
    });

    it("returns error on network failure", async () => {
      vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));

      const result = await client.speak("Hello world");
      expect(result.success).toBe(false);
      expect(result.error).toBe("ECONNREFUSED");
    });

    it("passes voice parameter when provided", async () => {
      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => ({ status: "playing", duration: 0.5, sample_rate: 24000 }),
      } as Response);

      await client.speak("Hello world", "cosette");

      const [, options] = fetchSpy.mock.calls[0];
      const body = JSON.parse((options as any).body);
      expect(body.text).toBe("Hello world");
      expect(body.voice).toBe("cosette");
    });
  });

  describe("generate", () => {
    it("returns base64 audio from the generate endpoint", async () => {
      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => ({
          audio_b64: "UklGRg==",
          duration: 2.5,
          sample_rate: 24000,
          voice: "cosette",
        }),
      } as Response);

      const result = await client.generate("Hello world", "cosette");

      const [url] = fetchSpy.mock.calls[0];
      expect(url).toBe("http://localhost:5003/api/tts/generate");
      expect(result.success).toBe(true);
      expect(result.audioBase64).toBe("UklGRg==");
      expect(result.duration).toBe(2.5);
    });

    it("returns error on non-200 response", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
        text: async () => '{"error": "TTS model not loaded"}',
      } as Response);

      const result = await client.generate("Hello world");
      expect(result.success).toBe(false);
      expect(result.error).toContain("TTS model not loaded");
    });
  });

  describe("getVoices", () => {
    it("returns the voice list and default from the server shape", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => ({ voices: ["cosette", "marius"], default: "cosette" }),
      } as Response);

      const result = await client.getVoices();
      expect(result.voices).toEqual(["cosette", "marius"]);
      expect(result.default).toBe("cosette");
    });

    it("returns an empty list on failure", async () => {
      vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));

      const result = await client.getVoices();
      expect(result.voices).toEqual([]);
    });
  });

  describe("setBaseUrl", () => {
    it("updates the base URL", () => {
      client.setBaseUrl("http://example.com:8080");
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Error",
        text: async () => "Error",
      } as Response);

      client.speak("test");

      const [url] = (globalThis.fetch as any).mock.calls[0];
      expect(url).toBe("http://example.com:8080/api/tts/speak");
    });
  });

  describe("default base URL", () => {
    it("uses the ziomek server port when no URL is given", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Error",
        text: async () => "Error",
      } as Response);

      await new TtsClient().speak("test");

      const [url] = (globalThis.fetch as any).mock.calls[0];
      expect(url.startsWith("http://localhost:5004")).toBe(true);
    });
  });
});
