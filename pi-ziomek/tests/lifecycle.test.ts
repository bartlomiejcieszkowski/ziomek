/**
 * Tests for the lifecycle module (slash commands + lifecycle hooks).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createVoiceExtension, VoiceExtensionState } from "../src/lifecycle";
import type { Config } from "../src/config";
import type { TtsClient } from "../src/tts-client";
import type { SttClient } from "../src/stt-client";
import type { GamepadManager } from "../src/gamepad";

function createMockConfig(): Config {
  return {
    voice: {
      serverUrl: "http://localhost:5003",
      keyword: "ziomek",
      keywords: ["ziomek"],
      maxListenDuration: 5,
    },
    gamepad: {
      enabled: true,
      pollIntervalMs: 2000,
      debounceMs: 1000,
      buttonMap: {},
    },
    dashboard: {
      enabled: true,
      autoShow: false,
      refreshIntervalMs: 2000,
    },
  };
}

function createMockPi() {
  const registeredTools: { name: string; params: unknown; execute: (callCtx: any) => Promise<any> }[] = [];
  const registeredSlashCommands: { name: string; description: string; handler: (args: string) => Promise<string> }[] = [];
  const eventHandlers: Record<string, (() => void)[]> = {};
  const appendEntries: string[] = [];

  const pi = {
    registerTool: vi.fn((name: string, params: unknown, execute: (callCtx: any) => Promise<any>) => {
      registeredTools.push({ name, params, execute });
    }),
    registerSlashCommand: vi.fn((name: string, description: string, handler: (args: string) => Promise<string>) => {
      registeredSlashCommands.push({ name, description, handler });
    }),
    on: vi.fn((event: string, handler: () => void) => {
      if (!eventHandlers[event]) eventHandlers[event] = [];
      eventHandlers[event].push(handler);
    }),
    appendEntry: vi.fn((text: string) => {
      appendEntries.push(text);
    }),
    sendUserMessage: vi.fn((text: string, options?: { deliverAs?: string }) => {
      // No-op for tests
    }),
    custom: vi.fn(),
    registeredTools,
    registeredSlashCommands,
    eventHandlers,
    appendEntries,
  };

  return pi as any;
}

describe("createVoiceExtension", () => {
  let pi: ReturnType<typeof createMockPi>;
  let config: Config;

  beforeEach(() => {
    pi = createMockPi();
    config = createMockConfig();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates extension with all components", () => {
    const state = createVoiceExtension({ pi, config });
    expect(state).toBeDefined();
    expect(state.ttsClient).toBeDefined();
    expect(state.sttClient).toBeDefined();
    expect(state.gamepadManager).toBeDefined();
    expect(state.dashboard).toBeDefined();
    expect(state.isListening).toBe(false);
  });

  it("registers tools", () => {
    createVoiceExtension({ pi, config });
    expect(pi.registerTool).toHaveBeenCalled();
    expect(pi.registerTool.mock.calls.length).toBeGreaterThan(0);
  });

  it("registers slash commands", () => {
    createVoiceExtension({ pi, config });
    expect(pi.registerSlashCommand).toHaveBeenCalled();
    expect(pi.registerSlashCommand.mock.calls.length).toBeGreaterThan(0);
  });

  it("registers lifecycle hooks", () => {
    createVoiceExtension({ pi, config });
    expect(pi.on).toHaveBeenCalledWith("session_start", expect.any(Function));
    expect(pi.on).toHaveBeenCalledWith("session_shutdown", expect.any(Function));
  });

  it("appends startup entry", () => {
    createVoiceExtension({ pi, config });
    expect(pi.appendEntry).toHaveBeenCalledWith("Ziomek Voice Assistant loaded");
  });

  it("session_start starts gamepad and shows dashboard", () => {
    const state = createVoiceExtension({ pi, config });
    const startHandler = pi.eventHandlers["session_start"][0];

    // Mock gamepad start
    vi.spyOn(state.gamepadManager, "start").mockImplementation(() => {});
    // Mock dashboard show
    vi.spyOn(state.dashboard, "show").mockImplementation(() => {});

    // Change config to enable dashboard auto-show
    config.dashboard.autoShow = true;

    startHandler();

    expect(state.gamepadManager.start).toHaveBeenCalled();
    expect(state.dashboard.show).toHaveBeenCalled();
  });

  it("session_shutdown stops listening, gamepad, dashboard", () => {
    const state = createVoiceExtension({ pi, config });
    const shutdownHandler = pi.eventHandlers["session_shutdown"][0];

    // Set isListening to true
    state.isListening = true;

    // Mock cleanup methods
    vi.spyOn(state.sttClient, "stop").mockImplementation(() => {});
    vi.spyOn(state.sttClient, "disconnect").mockImplementation(() => {});
    vi.spyOn(state.gamepadManager, "stop").mockImplementation(() => {});
    vi.spyOn(state.dashboard, "stop").mockImplementation(() => {});

    shutdownHandler();

    expect(state.sttClient.stop).toHaveBeenCalled();
    expect(state.sttClient.disconnect).toHaveBeenCalled();
    expect(state.gamepadManager.stop).toHaveBeenCalled();
    expect(state.dashboard.stop).toHaveBeenCalled();
  });
});
