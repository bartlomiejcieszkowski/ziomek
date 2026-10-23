/**
 * Configuration module for the Ziomek Voice extension.
 *
 * Loads and saves configuration from `~/.pi/agent/extensions/pi-ziomek/config.json`.
 * Provides sensible defaults for all fields.
 */

import fs from "node:fs";
import path from "node:path";

// ── Types ────────────────────────────────────────────────────────────────────

export interface GamepadConfig {
  enabled: boolean;
  pollIntervalMs: number;
  debounceMs: number;
  buttonMap: Record<string, string>;
}

export interface VoiceConfig {
  serverUrl: string;
  keyword: string;
  keywords: string[];
  maxListenDuration: number;
}

export interface DashboardConfig {
  enabled: boolean;
  autoShow: boolean;
  refreshIntervalMs: number;
}

export interface Config {
  voice: VoiceConfig;
  gamepad: GamepadConfig;
  dashboard: DashboardConfig;
}

// ── Defaults ─────────────────────────────────────────────────────────────────

function getDefaultConfig(): Config {
  return {
    voice: {
      serverUrl: "http://localhost:5004",
      keyword: "ziomek",
      keywords: ["ziomek"],
      maxListenDuration: 5,
    },
    gamepad: {
      enabled: true,
      pollIntervalMs: 2000,
      debounceMs: 1000,
      buttonMap: {
        "0": "listen_short", // A
        "1": "cycle_responses", // B
        "2": "listen_long", // X
        "3": "tts_speak_last", // Y
        "4": "prev_response", // LB
        "5": "next_response", // RB
        "12": "history_up", // D-Pad Up
        "13": "history_down", // D-Pad Down
        "9": "toggle_dashboard", // Start
        "8": "show_status", // Select
      },
    },
    dashboard: {
      enabled: true,
      autoShow: true,
      refreshIntervalMs: 2000,
    },
  };
}

// ── Paths ────────────────────────────────────────────────────────────────────

function getConfigDir(): string {
  // ~/.pi/agent/extensions/pi-ziomek/
  const home = process.env.HOME || process.env.USERPROFILE || ".";
  return path.join(home, ".pi", "agent", "extensions", "pi-ziomek");
}

function getConfigPath(): string {
  return path.join(getConfigDir(), "config.json");
}

// ── Load / Save ──────────────────────────────────────────────────────────────

/**
 * Load configuration from disk. Falls back to defaults on any error.
 */
export function loadConfig(): Config {
  try {
    const configPath = getConfigPath();
    if (!fs.existsSync(configPath)) {
      return getDefaultConfig();
    }
    const raw = fs.readFileSync(configPath, "utf-8");
    const parsed = JSON.parse(raw) as Partial<Config>;
    // Deep merge with defaults
    return deepMerge(getDefaultConfig(), parsed);
  } catch {
    // Any error (file not found, parse error, etc.) → use defaults
    return getDefaultConfig();
  }
}

/**
 * Save configuration to disk. Creates parent directories if needed.
 */
export function saveConfig(config: Config): void {
  const configDir = getConfigDir();
  if (!fs.existsSync(configDir)) {
    fs.mkdirSync(configDir, { recursive: true });
  }
  fs.writeFileSync(getConfigPath(), JSON.stringify(config, null, 2), "utf-8");
}

/**
 * Reload configuration from disk (useful after external changes).
 */
export function reloadConfig(): Config {
  return loadConfig();
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Deep merge two objects. `source` values override `target` values.
 * Arrays and primitives are replaced; objects are merged recursively.
 */
function deepMerge<T extends object>(target: T, source: Partial<T>): T {
  const result = { ...target };
  for (const key of Object.keys(source)) {
    const sourceVal = source[key as keyof typeof source];
    const targetVal = result[key as keyof typeof result];
    if (
      sourceVal !== undefined &&
      typeof sourceVal === "object" &&
      !Array.isArray(sourceVal) &&
      targetVal !== null &&
      typeof targetVal === "object" &&
      !Array.isArray(targetVal)
    ) {
      (result as any)[key] = deepMerge(targetVal, sourceVal as object);
    } else if (sourceVal !== undefined) {
      (result as any)[key] = sourceVal;
    }
  }
  return result;
}
