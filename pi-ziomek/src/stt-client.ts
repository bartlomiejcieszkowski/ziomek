/**
 * STT client — WebSocket client for ziomek STT streaming.
 *
 * Provides methods to connect to the STT streaming endpoint,
 * start/stop recording, and receive transcription callbacks.
 */

// ── Types ────────────────────────────────────────────────────────────────────

export interface SttTranscription {
  text: string;
  isFinal: boolean;
  realtime: boolean;
}

export type SttTranscriptionCallback = (result: SttTranscription) => void;

export type SttStatusCallback = (status: string) => void;

export interface SttState {
  state: string;
  engine: string;
  model: string;
  transcriptionCount: number;
}

// ── Client ───────────────────────────────────────────────────────────────────

export class SttClient {
  private ws: WebSocket | null = null;
  private baseUrl: string;
  private transcriptionCallbacks: SttTranscriptionCallback[] = [];
  private statusCallbacks: SttStatusCallback[] = [];
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private connected = false;

  constructor(baseUrl: string = "http://localhost:5003") {
    this.baseUrl = baseUrl;
  }

  /**
   * Connect to the STT streaming WebSocket endpoint.
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const wsUrl = this.baseUrl.replace("http", "ws") + "/api/stt/stream";

      try {
        this.ws = new WebSocket(wsUrl);
      } catch (error) {
        reject(error instanceof Error ? error : new Error(String(error)));
        return;
      }

      this.ws.onopen = () => {
        this.connected = true;
        resolve();
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as {
            type: string;
            text?: string;
            is_final?: boolean;
            realtime?: boolean;
            state?: string;
            engine?: string;
            model?: string;
            transcription_count?: number;
            error?: string;
          };

          switch (data.type) {
            case "transcription":
              for (const cb of this.transcriptionCallbacks) {
                cb({
                  text: data.text || "",
                  isFinal: data.is_final ?? false,
                  realtime: data.realtime ?? false,
                });
              }
              break;
            case "status":
              for (const cb of this.statusCallbacks) {
                cb(data.state || "unknown");
              }
              break;
            case "error":
              // Log error but don't reject — let the caller handle it
              console.error(`STT error: ${data.error}`);
              break;
            case "connected":
              // Server sends "connected" on initial connect — no action needed
              break;
          }
        } catch {
          // Ignore malformed messages
        }
      };

      this.ws.onerror = (error: Event) => {
        this.connected = false;
        reject(error);
      };

      this.ws.onclose = () => {
        this.connected = false;
        this.ws = null;
        // Auto-reconnect after 2s (exponential backoff up to 30s)
        this.scheduleReconnect();
      };
    });
  }

  /**
   * Start recording.
   */
  async start(): Promise<boolean> {
    return this.sendCommand("start");
  }

  /**
   * Stop recording.
   */
  async stop(): Promise<boolean> {
    return this.sendCommand("stop");
  }

  /**
   * Get current STT status.
   */
  async getStatus(): Promise<SttState | null> {
    try {
      const response = await fetch(`${this.baseUrl}/api/stt/status`);
      if (!response.ok) return null;
      const data = await response.json();
      return {
        state: data.state || "idle",
        engine: data.engine || "",
        model: data.model || "",
        transcriptionCount: data.transcription_count || 0,
      };
    } catch {
      return null;
    }
  }

  /**
   * Reconfigure STT engine/model.
   */
  async reconfigure(engine?: string, model?: string): Promise<boolean> {
    try {
      const body: Record<string, string> = {};
      if (engine) body.engine = engine;
      if (model) body.model = model;
      const response = await fetch(`${this.baseUrl}/api/stt/reconfigure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * Register a transcription callback.
   */
  onTranscription(callback: SttTranscriptionCallback): void {
    this.transcriptionCallbacks.push(callback);
  }

  /**
   * Remove a transcription callback.
   */
  offTranscription(callback: SttTranscriptionCallback): void {
    this.transcriptionCallbacks = this.transcriptionCallbacks.filter(
      (cb) => cb !== callback,
    );
  }

  /**
   * Register a status callback.
   */
  onStatus(callback: SttStatusCallback): void {
    this.statusCallbacks.push(callback);
  }

  /**
   * Remove a status callback.
   */
  offStatus(callback: SttStatusCallback): void {
    this.statusCallbacks = this.statusCallbacks.filter(
      (cb) => cb !== callback,
    );
  }

  /**
   * Disconnect from the STT streaming endpoint.
   */
  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
  }

  /**
   * Check if the client is connected.
   */
  isConnected(): boolean {
    return this.connected;
  }

  /**
   * Update the base URL (e.g., after config reload).
   */
  setBaseUrl(url: string): void {
    this.baseUrl = url;
  }

  // ── Private helpers ──────────────────────────────────────────────────────

  private sendCommand(command: string): Promise<boolean> {
    return new Promise((resolve) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        resolve(false);
        return;
      }

      // Set up a one-time message handler for the response
      const handler = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "command_result" && data.command === command) {
            this.ws?.removeEventListener("message", handler);
            resolve(data.success ?? false);
          }
        } catch {
          // Ignore malformed messages
        }
      };

      this.ws?.addEventListener("message", handler);

      // Send the command
      this.ws?.send(JSON.stringify({ action: command }));

      // Timeout after 5s
      setTimeout(() => {
        this.ws?.removeEventListener("message", handler);
        resolve(false);
      }, 5000);
    });
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    // Exponential backoff: 2s → 4s → 8s → ... → max 30s
    let delay = 2000;
    const attempt = () => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) return;
      this.reconnectTimer = setTimeout(() => {
        this.connect().catch(() => {
          // Connection failed, try again
          this.scheduleReconnect();
        });
      }, delay);
      delay = Math.min(delay * 2, 30000);
    };
    attempt();
  }
}
