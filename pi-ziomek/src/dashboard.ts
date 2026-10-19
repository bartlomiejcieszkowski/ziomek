/**
 * Dashboard overlay — TUI overlay showing voice assistant state.
 *
 * Renders a non-capturing overlay (like kijek's log overlay, todo.ts pattern)
 * showing:
 * - State indicator (listening/idle/speaking)
 * - Engine and model info
 * - Live transcription entries
 * - Gamepad state
 * - Recent activity log
 *
 * Uses @earendil-works/pi-tui components (Text, truncateToWidth, theme.fg).
 */

import type { Config } from "./config";

// ── Types ────────────────────────────────────────────────────────────────────

export interface DashboardEntry {
  time: string;
  text: string;
  type: "transcription" | "activity" | "system";
}

export interface DashboardState {
  mode: "idle" | "listening" | "speaking";
  engine: string;
  model: string;
  transcriptions: DashboardEntry[];
  activity: DashboardEntry[];
  gamepadConnected: boolean;
  gamepadId: string;
}

// ── Dashboard manager ────────────────────────────────────────────────────────

export class DashboardManager {
  private state: DashboardState;
  private maxEntries = 20;
  private ctx: {
    ui: { custom: (component: unknown) => void };
    mode: string;
    hasUI: boolean;
  };
  private config: Config;
  private visible: boolean;
  private intervalId: ReturnType<typeof setInterval> | null = null;

  constructor(
    ctx: {
      ui: { custom: (component: unknown) => void };
      mode: string;
      hasUI: boolean;
    },
    config: Config,
  ) {
    this.ctx = ctx;
    this.config = config;
    this.state = {
      mode: "idle",
      engine: "n/a",
      model: "n/a",
      transcriptions: [],
      activity: [],
      gamepadConnected: false,
      gamepadId: "",
    };
    this.visible = false;
  }

  /**
   * Show the dashboard overlay.
   */
  show(): void {
    this.visible = true;
    this.render();
    // Auto-refresh at configured interval
    if (this.config.dashboard.refreshIntervalMs) {
      this.intervalId = setInterval(() => this.render(), this.config.dashboard.refreshIntervalMs);
    }
  }

  /**
   * Hide the dashboard overlay.
   */
  hide(): void {
    this.visible = false;
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    // Clear the overlay by rendering empty
    this.ctx.ui.custom(this.buildComponent(""));
  }

  /**
   * Toggle dashboard visibility.
   */
  toggle(): void {
    if (this.visible) {
      this.hide();
    } else {
      this.show();
    }
  }

  /**
   * Check if dashboard is visible.
   */
  isVisible(): boolean {
    return this.visible;
  }

  /**
   * Update the voice assistant mode.
   */
  setMode(mode: "idle" | "listening" | "speaking"): void {
    this.state.mode = mode;
    this.addActivity(`mode: ${mode}`);
    if (this.visible) this.render();
  }

  /**
   * Update engine/model info.
   */
  setEngineInfo(engine: string, model: string): void {
    this.state.engine = engine;
    this.state.model = model;
    if (this.visible) this.render();
  }

  /**
   * Add a transcription entry.
   */
  addTranscription(text: string, isFinal: boolean): void {
    const entry: DashboardEntry = {
      time: this.getTime(),
      text: text,
      type: "transcription",
    };
    this.state.transcriptions.push(entry);
    if (this.state.transcriptions.length > this.maxEntries) {
      this.state.transcriptions.shift();
    }
    this.addActivity(isFinal ? `transcription: "${text}"` : `realtime: "${text}"`);
    if (this.visible) this.render();
  }

  /**
   * Update gamepad state.
   */
  setGamepadState(connected: boolean, id: string): void {
    this.state.gamepadConnected = connected;
    this.state.gamepadId = id;
    if (this.visible) this.render();
  }

  /**
   * Clear all entries.
   */
  clear(): void {
    this.state.transcriptions = [];
    this.state.activity = [];
    if (this.visible) this.render();
  }

  /**
   * Get current state.
   */
  getState(): DashboardState {
    return { ...this.state };
  }

  /**
   * Stop the dashboard.
   */
  stop(): void {
    this.hide();
  }

  // ── Private helpers ──────────────────────────────────────────────────────

  private getTime(): string {
    return new Date().toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  private addActivity(text: string): void {
    const entry: DashboardEntry = {
      time: this.getTime(),
      text,
      type: "activity",
    };
    this.state.activity.push(entry);
    if (this.state.activity.length > 10) {
      this.state.activity.shift();
    }
  }

  private render(): void {
    if (!this.visible) return;
    this.ctx.ui.custom(this.buildComponent(this.buildText()));
  }

  private buildText(): string {
    const { mode, engine, model, transcriptions, activity, gamepadConnected, gamepadId } = this.state;

    // State indicator
    const stateIcon = mode === "listening" ? "🔴" : mode === "speaking" ? "🟡" : "🟢";
    const lines: string[] = [];
    lines.push(`┌─ Ziomek Voice ─────────────────────────────`);
    lines.push(`│ State: ${stateIcon} ${mode.charAt(0).toUpperCase() + mode.slice(1)}`);
    lines.push(`│ Engine: ${engine} / ${model}`);
    lines.push(`│`);

    // Live transcription
    lines.push(`│ ─ Live Transcription ─`);
    if (transcriptions.length === 0) {
      lines.push(`│ (no transcriptions yet)`);
    } else {
      const recent = transcriptions.slice(-5);
      for (const entry of recent) {
        const truncated = entry.text.length > 30 ? entry.text.slice(0, 27) + "..." : entry.text;
        lines.push(`│ [${entry.time}] ${truncated}`);
      }
    }
    lines.push(`│`);

    // Gamepad
    lines.push(`│ ─ Gamepad ─`);
    if (gamepadConnected) {
      lines.push(`│ Connected: ✓ ${gamepadId}`);
    } else {
      lines.push(`│ Not connected`);
    }
    lines.push(`│`);

    // Recent activity
    lines.push(`│ ─ Recent Activity ─`);
    if (activity.length === 0) {
      lines.push(`│ (no activity yet)`);
    } else {
      for (const entry of activity.slice(-3)) {
        lines.push(`│ ${entry.text}`);
      }
    }
    lines.push(`└─────────────────────────────────────────────┘`);

    return lines.join("\n");
  }

  private buildComponent(text: string): unknown {
    // Return a component object that Pi's TUI system understands.
    // The exact shape depends on @earendil-works/pi-tui — we use a
    // simple text component with the rendered dashboard string.
    return {
      type: "text",
      content: text,
    };
  }
}
