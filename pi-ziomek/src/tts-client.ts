/**
 * TTS client — HTTP client for ziomek TTS endpoints.
 *
 * Provides methods to synthesize speech, cancel playback, and list voices.
 * Communicates with the ziomek server's TTS API over HTTP.
 */

// ── Types ────────────────────────────────────────────────────────────────────

export interface TtsVoice {
  name: string;
  language: string;
  description?: string;
}

export interface TtsResult {
  success: boolean;
  wavPath?: string | null;
  error?: string;
}

// ── Client ───────────────────────────────────────────────────────────────────

export class TtsClient {
  private baseUrl: string;
  private currentWavPath: string | null = null;

  constructor(baseUrl: string = "http://localhost:5004") {
    this.baseUrl = baseUrl;
  }

  /**
   * Synthesize speech from text. Returns the path to the generated WAV file.
   */
  async speak(text: string, voice?: string): Promise<TtsResult> {
    try {
      const url = `${this.baseUrl}/api/tts/synthesize`;
      const body: Record<string, string> = { text };
      if (voice) body.voice = voice;

      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorText = await response.text();
        return { success: false, error: errorText || response.statusText };
      }

      // The endpoint returns the WAV file path in the response body
      const result = (await response.json()) as { path?: string };
      this.currentWavPath = result.path || null;
      return { success: true, wavPath: this.currentWavPath };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  /**
   * Cancel current playback (if supported by the server).
   */
  async cancel(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tts/cancel`, {
        method: "POST",
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * List available TTS voices.
   */
  async getVoices(): Promise<TtsVoice[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tts/voices`);
      if (!response.ok) return [];
      return (await response.json()) as TtsVoice[];
    } catch {
      return [];
    }
  }

  /**
   * Get the last generated WAV file path.
   */
  getLastWavPath(): string | null {
    return this.currentWavPath;
  }

  /**
   * Update the base URL (e.g., after config reload).
   */
  setBaseUrl(url: string): void {
    this.baseUrl = url;
  }
}
