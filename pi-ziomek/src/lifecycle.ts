/**
 * Slash commands and lifecycle hooks for the Ziomek Voice Assistant extension.
 *
 * Registers slash commands:
 * - /voice-start — start continuous listening
 * - /voice-stop — stop continuous listening
 * - /voice-status — check voice assistant state
 * - /voice-speak <text> — speak text via TTS
 * - /voice-listen — one-shot voice command
 * - /dashboard — toggle dashboard overlay
 * - /gamepad-state — show gamepad state
 *
 * Lifecycle hooks:
 * - session_start: initialize clients, start gamepad
 * - session_shutdown: cleanup (stop listening, disconnect, stop gamepad)
 */

import { TtsClient } from "./tts-client";
import { SttClient } from "./stt-client";
import { GamepadManager } from "./gamepad";
import { DashboardManager } from "./dashboard";
import { registerTools } from "./tools";
import { gateKeyword } from "./keyword";
import type { Config } from "./config";

// ── Types ────────────────────────────────────────────────────────────────────

export interface VoiceExtensionContext {
  pi: unknown;
  config: Config;
}

export interface VoiceExtensionState {
  ttsClient: TtsClient;
  sttClient: SttClient;
  gamepadManager: GamepadManager;
  dashboard: DashboardManager;
  isListening: boolean;
  lastResponse: string;
}

// Helper to cast Pi API
function piApi(pi: unknown): {
  registerTool(name: string, params: unknown, execute: (callCtx: any) => Promise<any>): void;
  sendUserMessage(text: string, options?: { deliverAs?: string }): void;
  registerSlashCommand(name: string, description: string, handler: (args: string) => Promise<string>): void;
  on(event: string, handler: () => void): void;
  appendEntry(text: string): void;
  custom?: (component: unknown) => void;
} {
  return pi as any;
}

// ── Extension factory ────────────────────────────────────────────────────────

/**
 * Main extension factory — called by Pi when loading the extension.
 *
 * Pattern follows kijek and pi-copilot-plugins:
 * - Export default factory(pi: ExtensionAPI)
 * - Create state, register tools/commands, set up lifecycle hooks
 */
export function createVoiceExtension(ctx: VoiceExtensionContext): VoiceExtensionState {
  const { pi, config } = ctx;

  // Create clients
  const ttsClient = new TtsClient(config.voice.serverUrl);
  const sttClient = new SttClient(config.voice.serverUrl);
  const gamepadManager = new GamepadManager(config.gamepad);
  const dashboard = new DashboardManager(
    { ui: { custom: piApi(pi).custom ?? (() => {}) }, mode: ctx.pi ? "tui" : "rpc", hasUI: true },
    config,
  );

  const state: VoiceExtensionState = {
    ttsClient,
    sttClient,
    gamepadManager,
    dashboard,
    isListening: false,
    lastResponse: "",
  };

  // Register tools
  registerTools({
    pi,
    ttsClient,
    sttClient,
    gamepadManager,
    config,
    isListening: false,
    lastResponse: "",
  });

  // Register slash commands
  registerSlashCommands({
    pi,
    config,
    ttsClient,
    sttClient,
    gamepadManager,
    dashboard,
    getIsListening: () => state.isListening,
    setIsListening: (v: boolean) => { state.isListening = v; },
    getLastResponse: () => state.lastResponse,
    setLastResponse: (v: string) => { state.lastResponse = v; },
  });

  // Set up lifecycle hooks
  setupLifecycle({
    pi,
    config,
    ttsClient,
    sttClient,
    gamepadManager,
    dashboard,
    getIsListening: () => state.isListening,
    setIsListening: (v: boolean) => { state.isListening = v; },
  });

  // Log startup
  piApi(pi).appendEntry("Ziomek Voice Assistant loaded");

  return state;
}

// ── Slash commands ───────────────────────────────────────────────────────────

interface SlashCommandContext {
  pi: unknown;
  config: Config;
  ttsClient: TtsClient;
  sttClient: SttClient;
  gamepadManager: GamepadManager;
  dashboard: DashboardManager;
  getIsListening: () => boolean;
  setIsListening: (v: boolean) => void;
  getLastResponse: () => string;
  setLastResponse: (v: string) => void;
}

function registerSlashCommands(ctx: SlashCommandContext): void {
  const { pi, config, ttsClient, sttClient, gamepadManager, dashboard, getIsListening, setIsListening } = ctx;

  // /voice-start
  piApi(pi).registerSlashCommand(
    "voice-start",
    "Start continuous voice listening with keyword gating",
    async () => {
      if (getIsListening()) {
        return "Already listening. Use /voice-stop to stop.";
      }
      try {
        await sttClient.connect();
        const started = await sttClient.start();
        if (!started) {
          sttClient.disconnect();
          return "Error: could not start STT";
        }
        setIsListening(true);

        // Set up transcription callback with keyword gating
        sttClient.onTranscription((result) => {
          if (!result.isFinal || !result.text.trim()) return;
          const keywords = config.voice.keywords || [config.voice.keyword || "ziomek"];
          const gateResult = gateKeyword(result.text, keywords);
          if (gateResult.matched && gateResult.cleaned) {
            piApi(pi).sendUserMessage(gateResult.cleaned, { deliverAs: "followUp" });
          }
        });

        return "✓ Listening... (call /voice-stop to stop)";
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        return `Error starting listening: ${msg}`;
      }
    },
  );

  // /voice-stop
  piApi(pi).registerSlashCommand(
    "voice-stop",
    "Stop continuous voice listening",
    async () => {
      if (!getIsListening()) {
        return "Not currently listening.";
      }
      try {
        sttClient.stop();
        sttClient.disconnect();
        setIsListening(false);
        return "✓ Listening stopped.";
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        return `Error stopping: ${msg}`;
      }
    },
  );

  // /voice-status
  piApi(pi).registerSlashCommand(
    "voice-status",
    "Check voice assistant state",
    async () => {
      try {
        const state = await sttClient.getStatus();
        const mode = getIsListening() ? "listening" : "idle";
        const engine = state?.engine || "n/a";
        const model = state?.model || "n/a";
        return `State: ${mode} | Engine: ${engine} | Model: ${model}`;
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        return `Error getting status: ${msg}`;
      }
    },
  );

  // /voice-speak <text>
  piApi(pi).registerSlashCommand(
    "voice-speak",
    "Speak text via TTS",
    async (args: string) => {
      if (!args || args.trim().length === 0) {
        return "Usage: /voice-speak <text>";
      }
      try {
        await ttsClient.speak(args.trim());
        return `✓ Spoken: "${args.trim()}"`;
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        return `Error speaking: ${msg}`;
      }
    },
  );

  // /voice-listen
  piApi(pi).registerSlashCommand(
    "voice-listen",
    "One-shot voice command (listens for 5 seconds)",
    async () => {
      try {
        await sttClient.connect();
        const started = await sttClient.start();
        if (!started) {
          sttClient.disconnect();
          return "Error: could not start STT";
        }

        return new Promise((resolve) => {
          const timeout = setTimeout(() => {
            sttClient.stop();
            sttClient.disconnect();
            resolve("Error: no speech detected");
          }, 5000);

          sttClient.onTranscription((result) => {
            if (result.isFinal && result.text.trim()) {
              clearTimeout(timeout);
              sttClient.stop();
              sttClient.disconnect();
              resolve(`User said: "${result.text}"`);
            }
          });
        });
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        return `Error listening: ${msg}`;
      }
    },
  );

  // /dashboard
  piApi(pi).registerSlashCommand(
    "dashboard",
    "Toggle voice assistant dashboard overlay",
    async () => {
      dashboard.toggle();
      return dashboard.isVisible() ? "✓ Dashboard shown" : "✓ Dashboard hidden";
    },
  );

  // /gamepad-state
  piApi(pi).registerSlashCommand(
    "gamepad-state",
    "Show current gamepad state",
    async () => {
      try {
        const state = gamepadManager.getState();
        if (!state) {
          return "No gamepad connected.";
        }
        const buttonStates = state.buttons
          .map((b, i) => `${i}: ${b.pressed ? "pressed" : "released"}`)
          .join(", ");
        return `Connected: ${state.connected} | ID: ${state.id} | Buttons: [${buttonStates}]`;
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        return `Error getting gamepad state: ${msg}`;
      }
    },
  );
}

// ── Lifecycle hooks ──────────────────────────────────────────────────────────

interface LifecycleContext {
  pi: unknown;
  config: Config;
  ttsClient: TtsClient;
  sttClient: SttClient;
  gamepadManager: GamepadManager;
  dashboard: DashboardManager;
  getIsListening: () => boolean;
  setIsListening: (v: boolean) => void;
}

function setupLifecycle(ctx: LifecycleContext): void {
  const { pi, config, ttsClient, sttClient, gamepadManager, dashboard, getIsListening, setIsListening } = ctx;

  // session_start: initialize clients, start gamepad, optionally show dashboard
  piApi(pi).on("session_start", () => {
    // Start gamepad polling
    if (config.gamepad.enabled) {
      gamepadManager.start();
    }

    // Show dashboard if configured
    if (config.dashboard.enabled && config.dashboard.autoShow) {
      dashboard.show();
    }

    piApi(pi).appendEntry("Ziomek Voice Assistant session started");
  });

  // session_shutdown: cleanup
  piApi(pi).on("session_shutdown", () => {
    // Stop listening if active
    if (getIsListening()) {
      try {
        sttClient.stop();
        sttClient.disconnect();
        setIsListening(false);
      } catch {
        // Ignore cleanup errors
      }
    }

    // Stop gamepad
    if (config.gamepad.enabled) {
      gamepadManager.stop();
    }

    // Hide dashboard
    dashboard.stop();

    // Disconnect clients
    try {
      sttClient.disconnect();
    } catch {
      // Ignore cleanup errors
    }

    piApi(pi).appendEntry("Ziomek Voice Assistant session ended");
  });
}
