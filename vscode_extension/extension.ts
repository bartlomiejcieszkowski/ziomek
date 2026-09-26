import * as vscode from 'vscode';
import { Logger } from './logger.js';
import { GamepadAvatarPanel } from './humanize/avatar-panel.js';
import { ContextTracker } from './context.js';
import { ModuleRegistry } from './modules/base.js';
import { MappingResolver } from './mapping/resolver.js';
import { ConfigManager } from './mapping/config.js';
import { CopilotChatModule } from './modules/copilot-chat.js';
import { StubTTSService } from './humanize/tts/stub-tts.js';
import { ZiomekTTSClient } from './humanize/tts/pocket-tts-service.js';
import type { TTSService } from './humanize/tts/tts-service.js';

let logger: Logger | null = null;
let debugChannel: vscode.OutputChannel | null = null;
let avatarPanel: GamepadAvatarPanel | null = null;

export function activate(context: vscode.ExtensionContext) {
  logger = new Logger('debug');
  logger.info('extension', 'Activating Humanize AI extension');

  const configManager = new ConfigManager();
  const moduleRegistry = new ModuleRegistry(logger);
  const mappingResolver = new MappingResolver(
    configManager.loadMapping('copilotChat'),
    { logger },
  );
  const contextTracker = new ContextTracker(undefined, logger);

  // Register the Copilot Chat module
  const copilotChatModule = new CopilotChatModule();
  moduleRegistry.register(copilotChatModule);

  // Wire resolver output to module registry
  mappingResolver.onAction((action) => {
    if (!contextTracker) return;
    const activeContext = detectContext(contextTracker.getState());
    moduleRegistry
      .executeAction('copilotChat', action, { context: activeContext })
      .catch((error) => {
        vscode.window.showErrorMessage(`Humanize AI: ${error.message}`);
      });
  });

  // Create TTS service based on configuration
  const ttsService = createTTS(logger);

  // Avatar panel — gamepad is now handled by ziomek client
  avatarPanel = new GamepadAvatarPanel(context);

  // Load HTML from ziomek client and connect WebSocket
  const clientUrl = vscode.workspace
    .getConfiguration('ziomek')
    .get('client.url', 'http://localhost:5004') as string;

  // Load HTML from client at runtime
  avatarPanel._loadSharedHtml(clientUrl).then(() => {
    // Connect WebSocket for avatar state updates
    avatarPanel?.connectToClient(clientUrl);
  });

  // Register the avatar view provider
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      GamepadAvatarPanel.viewType,
      avatarPanel,
    ),
  );

  // Register avatar panel command (to focus/reveal the view)
  const showAvatarDisposable = vscode.commands.registerCommand(
    'humanizeAI.showAvatar',
    () => {
      avatarPanel?.show();
    },
  );

  // Set up settings change watcher
  const configDisposable = vscode.workspace.onDidChangeConfiguration((event) => {
    if (event.affectsConfiguration('humanizeAI')) {
      refreshConfiguration(configManager, mappingResolver);
    }
  });

  // Register debug command with log level toggle
  const debugDisposable = vscode.commands.registerCommand(
    'humanizeAI.showDebugInfo',
    () => {
      showDebugInfo(moduleRegistry, logger!);
    },
  );

  const logLevelDisposable = vscode.commands.registerCommand(
    'humanizeAI.cycleLogLevel',
    () => {
      if (!logger) return;
      const levels: Array<'debug' | 'info' | 'warn' | 'error'> = [
        'debug',
        'info',
        'warn',
        'error',
      ];
      const currentIdx = levels.indexOf(logger.getLevel());
      const nextLevel = levels[(currentIdx + 1) % levels.length];
      logger.setLevel(nextLevel);
      logger.info('extension', `Log level changed to ${nextLevel}`);
      vscode.window.showInformationMessage(
        `Humanize AI debug log level: ${nextLevel}`,
      );
    },
  );

  context.subscriptions.push(
    configDisposable,
    debugDisposable,
    logLevelDisposable,
    showAvatarDisposable,
  );
}

function detectContext(
  state: { chatFocused: boolean; inputFocused: boolean; sidebarFocused: boolean },
): string {
  if (state.chatFocused) return 'chat-focused';
  if (state.inputFocused) return 'input-focused';
  if (state.sidebarFocused) return 'sidebar-focused';
  return 'any';
}

function refreshConfiguration(
  configManager: ConfigManager,
  mappingResolver: MappingResolver,
): void {
  configManager.refreshSettings();
  const newConfig = configManager.loadMapping('copilotChat');
  mappingResolver.setConfig(newConfig);
}

function showDebugInfo(
  moduleRegistry: ModuleRegistry,
  loggerRef: Logger,
): void {
  if (!debugChannel) {
    debugChannel = vscode.window.createOutputChannel('Humanize AI Debug');
    loggerRef.setFallbackChannel(debugChannel);
  }
  debugChannel.clear();
  const now = new Date();
  const timestamp = now.toLocaleTimeString();
  debugChannel.appendLine(`=== Humanize AI Debug Info [${timestamp}] ===`);
  debugChannel.appendLine(`Current time: ${now.toISOString()}`);
  debugChannel.appendLine(`Log level: ${loggerRef.getLevel()}`);
  debugChannel.appendLine(
    `Registered modules: ${moduleRegistry.getRegisteredModuleNames().join(', ')}`,
  );
  debugChannel.appendLine('');
  debugChannel.appendLine('Gamepad polling is now handled by ziomek client.');
  debugChannel.appendLine('Start ziomek-client to enable gamepad input.');
  debugChannel.show();
}

/**
 * Create a TTSService instance based on the configured backend.
 *
 * Supports two modes:
 * - 'stub'     → StubTTSService (default, always available)
 * - 'ziomek'   → ZiomekTTSClient (HTTP client to ziomek server)
 */
function createTTS(log: Logger): TTSService {
  const config = vscode.workspace.getConfiguration('ziomek');
  const backend = config.get<'stub' | 'ziomek'>('tts.backend', 'stub');

  // Ziomek TTS configuration
  const ttsUrl = config.get('tts.url', 'http://localhost:5003');
  const voice = config.get('tts.voice', 'cosette');

  if (backend === 'stub') {
    log.info('extension', 'Using StubTTSService');
    return new StubTTSService();
  }

  // Use Ziomek HTTP client
  try {
    const client = new ZiomekTTSClient({ url: ttsUrl, voice });
    log.info('extension', `Using ZiomekTTSClient (url=${ttsUrl}, voice=${voice})`);
    return client;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    log.error('extension', `Failed to initialize Ziomek TTS client: ${msg}, falling back to StubTTSService`);
  }

  return new StubTTSService();
}

export function deactivate(): void {
  debugChannel?.dispose();
  debugChannel = null;
  if (avatarPanel) {
    avatarPanel.dispose();
    avatarPanel = null;
  }
}
