/**
 * TTS client — HTTP client for ziomek TTS endpoints.
 *
 * Mirrors the server API in src/ziomek/api/tts.py: /api/tts/speak (generate and
 * play), /api/tts/generate (return base64 WAV), /api/tts/voices.
 */

// ── Types ────────────────────────────────────────────────────────────────────

export interface VoiceList {
  voices: string[];
  default: string;
}

export interface TtsResult {
  success: boolean;
  error?: string;
  /** Playback duration in seconds reported by the server. */
  duration?: number;
  sampleRate?: number;
}

export interface GenerateResult extends TtsResult {
  /** Base64-encoded WAV bytes, as returned by /api/tts/generate. */
  audioBase64?: string | null;
}

// ── Client ───────────────────────────────────────────────────────────────────

export class TtsClient {
  private baseUrl: string;

  constructor(baseUrl: string = "http://localhost:5004") {
    this.baseUrl = baseUrl;
  }

  /**
   * Synthesize text and let the server play it (POST /api/tts/speak).
   */
  async speak(text: string, voice?: string): Promise<TtsResult> {
    return this.post("/api/tts/speak", text, voice);
  }

  /**
   * Synthesize text without playing it (POST /api/tts/generate).
   */
  async generate(text: string, voice?: string): Promise<GenerateResult> {
    return this.post("/api/tts/generate", text, voice);
  }

  /**
   * List available TTS voices (GET /api/tts/voices).
   */
  async getVoices(): Promise<VoiceList> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tts/voices`);
      if (!response.ok) return { voices: [], default: "" };
      const data = (await response.json()) as { voices?: string[]; default?: string };
      return { voices: data.voices ?? [], default: data.default ?? "" };
    } catch {
      return { voices: [], default: "" };
    }
  }

  /**
   * Update the base URL (e.g., after config reload).
   */
  setBaseUrl(url: string): void {
    this.baseUrl = url;
  }

  private async post(path: string, text: string, voice?: string): Promise<GenerateResult> {
    try {
      const body: Record<string, string> = { text };
      if (voice) body.voice = voice;

      const response = await fetch(`${this.baseUrl}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorText = await response.text();
        return { success: false, error: errorText || response.statusText };
      }

      const data = (await response.json()) as Record<string, unknown>;
      return {
        success: true,
        duration: typeof data.duration === "number" ? data.duration : undefined,
        sampleRate: typeof data.sample_rate === "number" ? data.sample_rate : undefined,
        audioBase64: typeof data.audio_b64 === "string" ? data.audio_b64 : undefined,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }
}
