/**
 * Tests for the dashboard overlay module.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardManager } from "../src/dashboard";
import type { Config } from "../src/config";

function createMockCtx() {
  const customCalls: unknown[] = [];
  return {
    ui: {
      custom: vi.fn((component: unknown) => {
        customCalls.push(component);
      }),
    },
    mode: "tui",
    hasUI: true,
    customCalls,
  };
}

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

describe("DashboardManager", () => {
  let ctx: ReturnType<typeof createMockCtx>;
  let config: Config;
  let dashboard: DashboardManager;

  beforeEach(() => {
    ctx = createMockCtx();
    config = createMockConfig();
    dashboard = new DashboardManager(ctx, config);
  });

  afterEach(() => {
    dashboard.stop();
    vi.restoreAllMocks();
  });

  describe("show/hide", () => {
    it("shows the dashboard", () => {
      dashboard.show();
      expect(dashboard.isVisible()).toBe(true);
      expect(ctx.ui.custom).toHaveBeenCalled();
    });

    it("hides the dashboard", () => {
      dashboard.show();
      dashboard.hide();
      expect(dashboard.isVisible()).toBe(false);
    });

    it("toggles visibility", () => {
      expect(dashboard.isVisible()).toBe(false);
      dashboard.toggle();
      expect(dashboard.isVisible()).toBe(true);
      dashboard.toggle();
      expect(dashboard.isVisible()).toBe(false);
    });
  });

  describe("state updates", () => {
    it("updates mode", () => {
      dashboard.show();
      dashboard.setMode("listening");
      const state = dashboard.getState();
      expect(state.mode).toBe("listening");
    });

    it("updates engine info", () => {
      dashboard.show();
      dashboard.setEngineInfo("faster_whisper", "tiny.en");
      const state = dashboard.getState();
      expect(state.engine).toBe("faster_whisper");
      expect(state.model).toBe("tiny.en");
    });

    it("adds transcription", () => {
      dashboard.show();
      dashboard.addTranscription("Hello world", true);
      const state = dashboard.getState();
      expect(state.transcriptions.length).toBe(1);
      expect(state.transcriptions[0].text).toBe("Hello world");
    });

    it("limits transcription entries", () => {
      dashboard.show();
      for (let i = 0; i < 25; i++) {
        dashboard.addTranscription(`Transcription ${i}`, true);
      }
      const state = dashboard.getState();
      expect(state.transcriptions.length).toBe(20); // maxEntries
    });

    it("updates gamepad state", () => {
      dashboard.show();
      dashboard.setGamepadState(true, "Xbox Controller");
      const state = dashboard.getState();
      expect(state.gamepadConnected).toBe(true);
      expect(state.gamepadId).toBe("Xbox Controller");
    });

    it("clears entries", () => {
      dashboard.show();
      dashboard.addTranscription("Hello", true);
      dashboard.setMode("listening");
      dashboard.clear();
      const state = dashboard.getState();
      expect(state.transcriptions.length).toBe(0);
      expect(state.activity.length).toBe(0);
    });
  });

  describe("render output", () => {
    it("renders state indicator", () => {
      dashboard.show();
      dashboard.setMode("listening");
      const call = ctx.customCalls[ctx.customCalls.length - 1] as { content: string };
      expect(call.content).toContain("Listening");
    });

    it("renders engine info", () => {
      dashboard.show();
      dashboard.setEngineInfo("faster_whisper", "tiny.en");
      const call = ctx.customCalls[ctx.customCalls.length - 1] as { content: string };
      expect(call.content).toContain("faster_whisper");
      expect(call.content).toContain("tiny.en");
    });

    it("renders gamepad section", () => {
      dashboard.show();
      dashboard.setGamepadState(true, "Xbox Controller");
      const call = ctx.customCalls[ctx.customCalls.length - 1] as { content: string };
      expect(call.content).toContain("Xbox Controller");
    });

    it("renders activity section", () => {
      dashboard.show();
      dashboard.setMode("listening");
      const call = ctx.customCalls[ctx.customCalls.length - 1] as { content: string };
      expect(call.content).toContain("mode: listening");
    });
  });

  describe("stop", () => {
    it("hides and stops refresh", () => {
      dashboard.show();
      dashboard.stop();
      expect(dashboard.isVisible()).toBe(false);
    });
  });
});
