import * as vscode from 'vscode';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

export class Logger {
  private readonly _channels = new Map<string, vscode.OutputChannel>();
  private _minLevel: LogLevel = 'info';
  private _fallbackChannel?: vscode.OutputChannel;

  constructor(minLevel: LogLevel = 'info') {
    this._minLevel = minLevel;
  }

  setLevel(level: LogLevel): void {
    this._minLevel = level;
  }

  getLevel(): LogLevel {
    return this._minLevel;
  }

  debug(module: string, message: string, data?: unknown): void {
    this._log('debug', module, message, data);
  }

  info(module: string, message: string, data?: unknown): void {
    this._log('info', module, message, data);
  }

  warn(module: string, message: string, data?: unknown): void {
    this._log('warn', module, message, data);
  }

  error(module: string, message: string, data?: unknown): void {
    this._log('error', module, message, data);
  }

  private _log(
    level: LogLevel,
    module: string,
    message: string,
    data?: unknown,
  ): void {
    if (LEVELS[level] < LEVELS[this._minLevel]) return;

    const timestamp = new Date().toISOString().substring(11, 23);
    const prefix = `[${timestamp}] ${module} [${level.toUpperCase()}]`;

    if (data !== undefined) {
      const output =
        typeof data === 'string' ? data : JSON.stringify(data, null, 2);
      this._appendLine(module, `${prefix} ${message}`);
      this._appendLine(module, output);
    } else {
      this._appendLine(module, `${prefix} ${message}`);
    }
  }

  private _appendLine(module: string, message: string): void {
    let channel = this._channels.get(module);
    if (!channel) {
      channel = vscode.window.createOutputChannel(`Gamify AI - ${module}`);
      this._channels.set(module, channel);
    }
    channel.appendLine(message);

    // Also route to fallback channel (e.g., the aggregated debug channel)
    if (this._fallbackChannel) {
      try {
        this._fallbackChannel.appendLine(message);
      } catch {
        // Fallback channel may have been disposed
        this._fallbackChannel = undefined;
      }
    }
  }

  setFallbackChannel(channel?: vscode.OutputChannel): void {
    this._fallbackChannel = channel;
  }

  getOutputChannels(): vscode.OutputChannel[] {
    return Array.from(this._channels.values());
  }

  clear(): void {
    for (const [module, channel] of this._channels) {
      channel.dispose();
      this._channels.set(module, vscode.window.createOutputChannel(`Gamify AI - ${module}`));
    }
  }
}
