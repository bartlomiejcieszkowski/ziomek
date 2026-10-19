/**
 * Tests for the config module.
 */

import fs from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Config } from "../src/config";
import { loadConfig, saveConfig, reloadConfig } from "../src/config";

describe("config module", () => {
  let tmpDir: string;

  beforeEach(() => {
    // Create a temporary directory for test config files
    tmpDir = fs.mkdtempSync("/tmp/ziomek-config-test-");
    // Override the config dir by creating the expected path
    vi.stubEnv("HOME", tmpDir);
  });

  afterEach(() => {
    // Clean up
    fs.rmSync(tmpDir, { recursive: true, force: true });
    vi.unstubAllEnvs();
  });

  describe("loadConfig", () => {
    it("returns defaults when no config file exists", () => {
      const config = loadConfig();
      expect(config).toBeDefined();
      expect(config.voice.serverUrl).toBe("http://localhost:5003");
      expect(config.voice.keyword).toBe("ziomek");
      expect(config.voice.keywords).toEqual(["ziomek"]);
      expect(config.voice.maxListenDuration).toBe(5);
      expect(config.gamepad.enabled).toBe(true);
      expect(config.gamepad.pollIntervalMs).toBe(2000);
      expect(config.gamepad.debounceMs).toBe(1000);
      expect(config.dashboard.enabled).toBe(true);
      expect(config.dashboard.autoShow).toBe(true);
      expect(config.dashboard.refreshIntervalMs).toBe(2000);
    });

    it("returns defaults when config file contains invalid JSON", () => {
      const configDir = path.join(tmpDir, ".pi", "agent", "extensions", "pi-ziomek");
      fs.mkdirSync(configDir, { recursive: true });
      fs.writeFileSync(path.join(configDir, "config.json"), "not valid json {{{", "utf-8");

      const config = loadConfig();
      expect(config.voice.serverUrl).toBe("http://localhost:5003");
    });

    it("merges partial config with defaults", () => {
      const configDir = path.join(tmpDir, ".pi", "agent", "extensions", "pi-ziomek");
      fs.mkdirSync(configDir, { recursive: true });
      fs.writeFileSync(
        path.join(configDir, "config.json"),
        JSON.stringify({ voice: { serverUrl: "http://example.com:8080" } }),
        "utf-8",
      );

      const config = loadConfig();
      expect(config.voice.serverUrl).toBe("http://example.com:8080");
      // Other fields should use defaults
      expect(config.voice.keyword).toBe("ziomek");
      expect(config.gamepad.enabled).toBe(true);
    });

    it("preserves gamepad button map on reload", () => {
      const configDir = path.join(tmpDir, ".pi", "agent", "extensions", "pi-ziomek");
      fs.mkdirSync(configDir, { recursive: true });
      fs.writeFileSync(
        path.join(configDir, "config.json"),
        JSON.stringify({
          gamepad: { buttonMap: { "0": "listen_short", "2": "listen_long" } },
        }),
        "utf-8",
      );

      const config = loadConfig();
      expect(config.gamepad.buttonMap["0"]).toBe("listen_short");
      expect(config.gamepad.buttonMap["2"]).toBe("listen_long");
    });
  });

  describe("saveConfig", () => {
    it("creates the config file", () => {
      const config = loadConfig();
      saveConfig(config);
      const configPath = path.join(tmpDir, ".pi", "agent", "extensions", "pi-ziomek", "config.json");
      expect(fs.existsSync(configPath)).toBe(true);
    });

    it("writes valid JSON", () => {
      const config = loadConfig();
      saveConfig(config);
      const configPath = path.join(tmpDir, ".pi", "agent", "extensions", "pi-ziomek", "config.json");
      const raw = fs.readFileSync(configPath, "utf-8");
      const parsed = JSON.parse(raw);
      expect(parsed.voice.serverUrl).toBe("http://localhost:5003");
    });

    it("persists and reloads custom values", () => {
      const config = loadConfig();
      config.voice.serverUrl = "http://custom:9999";
      config.voice.keyword = "hey";
      saveConfig(config);

      const reloaded = reloadConfig();
      expect(reloaded.voice.serverUrl).toBe("http://custom:9999");
      expect(reloaded.voice.keyword).toBe("hey");
    });
  });

  describe("reloadConfig", () => {
    it("re-reads from disk", () => {
      // Save a custom config
      const config = loadConfig();
      config.voice.serverUrl = "http://reload-test:1234";
      saveConfig(config);

      // Reload should pick up the changes
      const reloaded = reloadConfig();
      expect(reloaded.voice.serverUrl).toBe("http://reload-test:1234");
    });
  });
});
