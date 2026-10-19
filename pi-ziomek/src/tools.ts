/**
 * Tool definitions and handlers for the Ziomek Voice Assistant extension.
 *
 * Registers 7 tools with the Pi ExtensionAPI:
 * - ziomek_voice_speak — speak text via TTS
 * - ziomek_voice_listen — one-shot voice command
 * - ziomek_voice_start — start continuous listening
 * - ziomek_voice_stop — stop continuous listening
 * - ziomek_voice_status — check voice assistant state
 * - ziomek_voice_transcribe — transcribe an audio file
 * - ziomek_gamepad_state — get current gamepad state
 */

import { TtsClient } from "./tts-client";
import { SttClient } from "./stt-client";
import { GamepadManager } from "./gamepad";
import { gateKeyword } from "./keyword";
import type { Config } from "./config";

// ── Types ────────────────────────────────────────────────────────────────────

export interface VoiceToolContext {
  pi: unknown;
  ttsClient: TtsClient;
  sttClient: SttClient;
  gamepadManager: GamepadManager;
  config: Config;
  isListening: boolean;
  lastResponse: string;
}

// Helper to cast Pi API — avoids TS type assertion issues in parentheses
function piApi(pi: unknown): {
  registerTool(name: string, params: unknown, execute: (callCtx: any) => Promise<any>): void;
  sendUserMessage(text: string, options?: { deliverAs?: string }): void;
} {
  return pi as any;
}

// ── Tool registration ────────────────────────────────────────────────────────

/**
 * Register all voice assistant tools with the Pi ExtensionAPI.
 */
export function registerTools(ctx: VoiceToolContext): void {
  registerSpeak(ctx);
  registerListen(ctx);
  registerStart(ctx);
  registerStop(ctx);
  registerStatus(ctx);
  registerTranscribe(ctx);
  registerGamepadState(ctx);
}

// ── Tool: speak ──────────────────────────────────────────────────────────────

function registerSpeak(ctx: VoiceToolContext): void {
  const params = {
    type: "object",
    properties: {
      text: { type: "string", description: "Text to speak" },
      voice: { type: "string", description: "Voice name (optional)" },
    },
    required: ["text"],
  };

  const execute = async (callCtx: { arguments: { text: string; voice?: string } }) => {
    try {
      const { text, voice } = callCtx.arguments;
      if (!text) {
        return { isError: true, content: [{ type: "text", text: "Error: empty text" }] };
      }

      await ctx.ttsClient.speak(text, voice);
      ctx.lastResponse = text;

      return {
        content: [
          {
            type: "text",
            text: `✓ Spoken: "${text}"${voice ? ` (voice: ${voice})` : ""}`,
          },
        ],
      };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      return { isError: true, content: [{ type: "text", text: `Error speaking: ${msg}` }] };
    }
  };

  piApi(ctx.pi).registerTool("ziomek_voice_speak", params, execute);
}

// ── Tool: listen ─────────────────────────────────────────────────────────────

function registerListen(ctx: VoiceToolContext): void {
  const params = {
    type: "object",
    properties: {
      duration: { type: "number", description: "Max seconds to listen (default 5)", default: 5 },
      prompt: { type: "string", description: "Hint for what to listen for" },
    },
  };

  const execute = async (callCtx: { arguments: { duration?: number; prompt?: string } }) => {
    try {
      const duration = callCtx.arguments.duration || 5;

      // Start STT
      await ctx.sttClient.connect();
      const startOk = await ctx.sttClient.start();
      if (!startOk) {
        ctx.sttClient.disconnect();
        return { isError: true, content: [{ type: "text", text: "Error: could not start STT" }] };
      }

      // Wait for transcription
      return new Promise((resolve) => {
        const timeout = setTimeout(() => {
          ctx.sttClient.stop();
          ctx.sttClient.disconnect();
          resolve({ content: [{ type: "text", text: "Error: no speech detected" }] });
        }, duration * 1000);

        ctx.sttClient.onTranscription((result) => {
          if (result.isFinal && result.text.trim()) {
            clearTimeout(timeout);
            ctx.sttClient.stop();
            ctx.sttClient.disconnect();
            resolve({ content: [{ type: "text", text: `User said: "${result.text}"` }] });
          }
        });
      });
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      return { isError: true, content: [{ type: "text", text: `Error listening: ${msg}` }] };
    }
  };

  piApi(ctx.pi).registerTool("ziomek_voice_listen", params, execute);
}

// ── Tool: start ──────────────────────────────────────────────────────────────

function registerStart(ctx: VoiceToolContext): void {
  const params = { type: "object", properties: {} };

  const execute = async () => {
    try {
      if (ctx.isListening) {
        return { content: [{ type: "text", text: "Already listening. Call ziomek_voice_stop to stop." }] };
      }

      await ctx.sttClient.connect();
      const started = await ctx.sttClient.start();
      if (!started) {
        ctx.sttClient.disconnect();
        return { isError: true, content: [{ type: "text", text: "Error: could not start STT" }] };
      }

      ctx.isListening = true;

      // Set up transcription callback with keyword gating
      ctx.sttClient.onTranscription((result) => {
        if (!result.isFinal || !result.text.trim()) return;

        const keywords = ctx.config.voice.keywords || [ctx.config.voice.keyword || "ziomek"];
        const gateResult = gateKeyword(result.text, keywords);
        if (gateResult.matched && gateResult.cleaned) {
          piApi(ctx.pi).sendUserMessage(gateResult.cleaned, { deliverAs: "followUp" });
        }
      });

      return { content: [{ type: "text", text: "✓ Listening... (call ziomek_voice_stop to stop)" }] };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      return { isError: true, content: [{ type: "text", text: `Error starting listening: ${msg}` }] };
    }
  };

  piApi(ctx.pi).registerTool("ziomek_voice_start", params, execute);
}

// ── Tool: stop ───────────────────────────────────────────────────────────────

function registerStop(ctx: VoiceToolContext): void {
  const params = { type: "object", properties: {} };

  const execute = async () => {
    try {
      if (!ctx.isListening) {
        return { content: [{ type: "text", text: "Not currently listening." }] };
      }

      ctx.sttClient.stop();
      ctx.sttClient.disconnect();
      ctx.isListening = false;

      return { content: [{ type: "text", text: "✓ Listening stopped." }] };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      return { isError: true, content: [{ type: "text", text: `Error stopping: ${msg}` }] };
    }
  };

  piApi(ctx.pi).registerTool("ziomek_voice_stop", params, execute);
}

// ── Tool: status ─────────────────────────────────────────────────────────────

function registerStatus(ctx: VoiceToolContext): void {
  const params = { type: "object", properties: {} };

  const execute = async () => {
    try {
      const state = await ctx.sttClient.getStatus();
      const mode = ctx.isListening ? "listening" : "idle";
      const engine = state?.engine || "n/a";
      const model = state?.model || "n/a";

      return {
        content: [
          {
            type: "text",
            text: `State: ${mode} | Engine: ${engine} | Model: ${model}`,
          },
        ],
      };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      return { isError: true, content: [{ type: "text", text: `Error getting status: ${msg}` }] };
    }
  };

  piApi(ctx.pi).registerTool("ziomek_voice_status", params, execute);
}

// ── Tool: transcribe ─────────────────────────────────────────────────────────

function registerTranscribe(ctx: VoiceToolContext): void {
  const params = {
    type: "object",
    properties: {
      file: { type: "string", description: "Path to audio file (WAV/MP3)" },
    },
    required: ["file"],
  };

  const execute = async (callCtx: { arguments: { file: string } }) => {
    try {
      const { file } = callCtx.arguments;
      // Note: file transcription requires server-side upload endpoint
      // For now, return a placeholder
      return { content: [{ type: "text", text: `Transcription of "${file}" — server endpoint not yet implemented` }] };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      return { isError: true, content: [{ type: "text", text: `Error transcribing: ${msg}` }] };
    }
  };

  piApi(ctx.pi).registerTool("ziomek_voice_transcribe", params, execute);
}

// ── Tool: gamepad_state ──────────────────────────────────────────────────────

function registerGamepadState(ctx: VoiceToolContext): void {
  const params = { type: "object", properties: {} };

  const execute = async () => {
    try {
      const state = ctx.gamepadManager.getState();
      if (!state) {
        return { content: [{ type: "text", text: "No gamepad connected." }] };
      }

      const buttonStates = state.buttons
        .map((b, i) => `${i}: ${b.pressed ? "pressed" : "released"}`)
        .join(", ");

      return {
        content: [
          {
            type: "text",
            text: `Connected: ${state.connected} | ID: ${state.id} | Buttons: [${buttonStates}]`,
          },
        ],
      };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      return { isError: true, content: [{ type: "text", text: `Error getting gamepad state: ${msg}` }] };
    }
  };

  piApi(ctx.pi).registerTool("ziomek_gamepad_state", params, execute);
}
