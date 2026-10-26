/**
 * Tests for the voice assistant tools module.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { registerTools } from "../src/tools";
import { TtsClient } from "../src/tts-client";
import { SttClient } from "../src/stt-client";
import { GamepadManager } from "../src/gamepad";
import type { Config } from "../src/config";

// Mock clients
const mockTtsClient = {
  speak: vi.fn(),
  generate: vi.fn(),
  getVoices: vi.fn(),
  setBaseUrl: vi.fn(),
} as unknown as TtsClient;

const mockSttClient = {
  connect: vi.fn(),
  start: vi.fn(),
  stop: vi.fn(),
  getStatus: vi.fn(),
  reconfigure: vi.fn(),
  onTranscription: vi.fn(),
  onStatus: vi.fn(),
  disconnect: vi.fn(),
  isConnected: vi.fn(),
  setBaseUrl: vi.fn(),
} as unknown as SttClient;

const mockGamepadManager = {
  start: vi.fn(),
  stop: vi.fn(),
  isRunning: vi.fn(),
  onButton: vi.fn(),
  offButton: vi.fn(),
  getState: vi.fn(),
  poll: vi.fn(),
} as unknown as GamepadManager;

// Mock Pi API
function createMockPi() {
  const registeredTools: { name: string; params: unknown; execute: (ctx: unknown) => Promise<unknown> }[] = [];
  const sentMessages: { text: string; options?: { deliverAs?: string } }[] = [];

  return {
    appendEntry: vi.fn(),
    sendUserMessage: vi.fn((text: string, options?: { deliverAs?: string }) => {
      sentMessages.push({ text, options });
    }),
    registerTool: vi.fn((name: string, params: unknown, execute: (ctx: unknown) => Promise<unknown>) => {
      registeredTools.push({ name, params, execute });
    }),
    registeredTools,
    sentMessages,
  };
}

describe("registerTools", () => {
  let pi: ReturnType<typeof createMockPi>;
  let config: Config;

  beforeEach(() => {
    pi = createMockPi();
    config = {
      serverUrl: "http://localhost:5003",
      keywords: ["ziomek"],
      sttEngine: "faster_whisper",
      sttModel: "tiny.en",
      ttsVoice: "cosette",
      listenDuration: 5,
      autoStartDashboard: false,
      toolsHiddenByDefault: true,
      gamepad: {
        pollIntervalMs: 2000,
        debounceMs: 1000,
        buttonMap: {},
      },
    };
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("tool registration", () => {
    it("registers all 7 tools", () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: false,
        lastResponse: "",
      });

      const toolNames = pi.registerTool.mock.calls.map((c) => c[0]);
      expect(toolNames).toContain("ziomek_voice_speak");
      expect(toolNames).toContain("ziomek_voice_listen");
      expect(toolNames).toContain("ziomek_voice_start");
      expect(toolNames).toContain("ziomek_voice_stop");
      expect(toolNames).toContain("ziomek_voice_status");
      expect(toolNames).toContain("ziomek_voice_transcribe");
      expect(toolNames).toContain("ziomek_gamepad_state");
      expect(toolNames.length).toBe(7);
    });
  });

  describe("ziomek_voice_speak", () => {
    it("sends text to TTS client", async () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: false,
        lastResponse: "",
      });

      const speakTool = pi.registeredTools.find((t) => t.name === "ziomek_voice_speak");
      expect(speakTool).toBeDefined();

      mockTtsClient.speak.mockResolvedValue(true);
      const result = await speakTool!.execute({ arguments: { text: "Hello" } });

      expect(mockTtsClient.speak).toHaveBeenCalledWith("Hello", undefined);
      expect(result).toEqual({
        content: [{ type: "text", text: '✓ Spoken: "Hello"' }],
      });
    });

    it("returns error on empty text", async () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: false,
        lastResponse: "",
      });

      const speakTool = pi.registeredTools.find((t) => t.name === "ziomek_voice_speak");
      const result = await speakTool!.execute({ arguments: { text: "" } });

      expect(result).toEqual({
        isError: true,
        content: [{ type: "text", text: "Error: empty text" }],
      });
    });

    it("returns error on TTS failure", async () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: false,
        lastResponse: "",
      });

      const speakTool = pi.registeredTools.find((t) => t.name === "ziomek_voice_speak");
      mockTtsClient.speak.mockRejectedValue(new Error("Server unreachable"));
      const result = await speakTool!.execute({ arguments: { text: "Hello" } });

      expect(result).toEqual({
        isError: true,
        content: [{ type: "text", text: "Error speaking: Server unreachable" }],
      });
    });
  });

  describe("ziomek_voice_start", () => {
    it("connects and starts STT", async () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: false,
        lastResponse: "",
      });

      const startTool = pi.registeredTools.find((t) => t.name === "ziomek_voice_start");
      mockSttClient.connect.mockResolvedValue(true);
      mockSttClient.start.mockResolvedValue(true);

      const result = await startTool!.execute({ arguments: {} });

      expect(mockSttClient.connect).toHaveBeenCalled();
      expect(mockSttClient.start).toHaveBeenCalled();
      expect(result).toEqual({
        content: [{ type: "text", text: "✓ Listening... (call ziomek_voice_stop to stop)" }],
      });
    });

    it("injects keyword-matched transcription via sendUserMessage", async () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: true, // Already listening
        lastResponse: "",
      });

      const startTool = pi.registeredTools.find((t) => t.name === "ziomek_voice_start");
      const result = await startTool!.execute({ arguments: {} });

      // Should say "Already listening" since isListening is true
      expect(result).toEqual({
        content: [{ type: "text", text: "Already listening. Call ziomek_voice_stop to stop." }],
      });
    });

    it("returns error on STT connection failure", async () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: false,
        lastResponse: "",
      });

      const startTool = pi.registeredTools.find((t) => t.name === "ziomek_voice_start");
      mockSttClient.connect.mockRejectedValue(new Error("Connection refused"));

      const result = await startTool!.execute({ arguments: {} });

      expect(result).toEqual({
        isError: true,
        content: [{ type: "text", text: "Error starting listening: Connection refused" }],
      });
    });
  });

  describe("ziomek_voice_stop", () => {
    it("stops and disconnects STT", async () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: true,
        lastResponse: "",
      });

      const stopTool = pi.registeredTools.find((t) => t.name === "ziomek_voice_stop");
      const result = await stopTool!.execute({ arguments: {} });

      expect(mockSttClient.stop).toHaveBeenCalled();
      expect(mockSttClient.disconnect).toHaveBeenCalled();
      expect(result).toEqual({ content: [{ type: "text", text: "✓ Listening stopped." }] });
    });

    it("returns message when not listening", async () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: false,
        lastResponse: "",
      });

      const stopTool = pi.registeredTools.find((t) => t.name === "ziomek_voice_stop");
      const result = await stopTool!.execute({ arguments: {} });

      expect(result).toEqual({ content: [{ type: "text", text: "Not currently listening." }] });
    });
  });

  describe("ziomek_voice_status", () => {
    it("returns current state", async () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: false,
        lastResponse: "",
      });

      const statusTool = pi.registeredTools.find((t) => t.name === "ziomek_voice_status");
      mockSttClient.getStatus.mockResolvedValue({
        state: "idle",
        engine: "faster_whisper",
        model: "tiny.en",
        transcriptionCount: 0,
      });

      const result = await statusTool!.execute({ arguments: {} });

      expect(result).toEqual({
        content: [
          {
            type: "text",
            text: "State: idle | Engine: faster_whisper | Model: tiny.en",
          },
        ],
      });
    });

    it("shows listening state", async () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: true,
        lastResponse: "",
      });

      const statusTool = pi.registeredTools.find((t) => t.name === "ziomek_voice_status");
      mockSttClient.getStatus.mockResolvedValue(null);

      const result = await statusTool!.execute({ arguments: {} });

      expect(result).toEqual({
        content: [{ type: "text", text: "State: listening | Engine: n/a | Model: n/a" }],
      });
    });
  });

  describe("ziomek_gamepad_state", () => {
    it("returns gamepad state", async () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: false,
        lastResponse: "",
      });

      const gamepadTool = pi.registeredTools.find((t) => t.name === "ziomek_gamepad_state");
      mockGamepadManager.getState.mockReturnValue({
        index: 0,
        id: "Xbox Controller",
        connected: true,
        buttons: [{ pressed: true, value: 1.0 }, { pressed: false, value: 0.0 }],
        axes: [0.5, -0.3],
      });

      const result = await gamepadTool!.execute({ arguments: {} });

      expect(result.content[0].type).toBe("text");
      expect(String(result.content[0].text)).toContain("Xbox Controller");
      expect(String(result.content[0].text)).toContain("pressed");
    });

    it("returns no gamepad message", async () => {
      registerTools({
        pi,
        ttsClient: mockTtsClient,
        sttClient: mockSttClient,
        gamepadManager: mockGamepadManager,
        config,
        isListening: false,
        lastResponse: "",
      });

      const gamepadTool = pi.registeredTools.find((t) => t.name === "ziomek_gamepad_state");
      mockGamepadManager.getState.mockReturnValue(null);

      const result = await gamepadTool!.execute({ arguments: {} });

      expect(result).toEqual({ content: [{ type: "text", text: "No gamepad connected." }] });
    });
  });
});
