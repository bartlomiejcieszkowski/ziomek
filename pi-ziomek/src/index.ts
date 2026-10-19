/**
 * Ziomek Voice Assistant — Pi extension
 *
 * Provides hands-free voice interaction with the Pi coding agent via
 * ziomek's TTS/STT endpoints. Supports continuous listening mode,
 * gamepad controls, and a TUI dashboard overlay.
 */

/**
 * Extension factory — called by Pi when loading extensions.
 * The ExtensionAPI type is provided by @earendil-works/pi-coding-agent
 * at runtime; we use a minimal type definition here for compilation.
 */
interface ExtensionAPI {
  appendEntry(entry: { type: string; text: string }): void;
  sendUserMessage(text: string, options?: { deliverAs?: string }): void;
  registerTool(
    name: string,
    params: unknown,
    execute: (ctx: unknown) => Promise<unknown>,
  ): void;
  registerCommand(
    name: string,
    handler: (ctx: unknown) => Promise<void>,
  ): void;
  on(event: string, handler: (...args: unknown[]) => void): void;
  ui: {
    custom(component: unknown): void;
  };
  mode: string;
  hasUI: boolean;
}

export default function factory(pi: ExtensionAPI): void {
  // Placeholder — tasks 2–9 will implement the full extension here
  pi.appendEntry({ type: "info", text: "Ziomek Voice extension loaded (stub)" });
}
