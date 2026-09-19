import * as vscode from 'vscode';
import { Logger } from './logger.js';
import { GamepadService } from './gamepad/service.js';
import { ContextTracker } from './context.js';
import { ModuleRegistry } from './modules/base.js';
import { MappingResolver } from './mapping/resolver.js';
import { ConfigManager } from './mapping/config.js';
import { CopilotChatModule } from './modules/copilot-chat.js';

let gamepadService: GamepadService | null = null;
let contextTracker: ContextTracker | null = null;
let logger: Logger | null = null;
let debugChannel: vscode.OutputChannel | null = null;

export function activate(context: vscode.ExtensionContext) {
  logger = new Logger('debug');
  logger.info('extension', 'Activating Gamify AI extension');

  const configManager = new ConfigManager();
  const moduleRegistry = new ModuleRegistry(logger);
  const mappingResolver = new MappingResolver(
    configManager.loadMapping('copilotChat'),
    { logger },
  );
  contextTracker = new ContextTracker(undefined, logger);

  // Register the Copilot Chat module
  const copilotChatModule = new CopilotChatModule();
  moduleRegistry.register(copilotChatModule);

  // Wire resolver output to module registry
  mappingResolver.onAction((action) => {
    if (!contextTracker) return;
    const contextState = contextTracker.getState();
    const activeContext = detectContext(contextState);

    moduleRegistry
      .executeAction('copilotChat', action, { context: activeContext })
      .catch((error) => {
        vscode.window.showErrorMessage(`Gamify AI: ${error.message}`);
      });
  });

  // Start gamepad service
  const pollingInterval = vscode.workspace
    .getConfiguration('gamifyAI')
    .get('pollingIntervalMs', 16);
  gamepadService = new GamepadService(pollingInterval);

  gamepadService.on('button', (event) => {
    if (event.type === 'gamepadbutton') {
      mappingResolver.handleButton(event.buttonIndex, event.pressed, event.value);
    }
  });

  gamepadService.on('axis', (event) => {
    if (event.type === 'gamepadaxis') {
      mappingResolver.handleAxis(event.axisIndex, event.value);
    }
  });

  gamepadService.start();

  // Set up settings change watcher
  const configDisposable = vscode.workspace.onDidChangeConfiguration((event) => {
    if (event.affectsConfiguration('gamifyAI')) {
      refreshConfiguration(configManager, mappingResolver);
    }
  });

  // Register debug command with log level toggle
  const debugDisposable = vscode.commands.registerCommand(
    'gamifyAI.showDebugInfo',
    () => {
      showDebugInfo(moduleRegistry, gamepadService, logger!);
    },
  );

  const logLevelDisposable = vscode.commands.registerCommand(
    'gamifyAI.cycleLogLevel',
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
        `Gamify AI debug log level: ${nextLevel}`,
      );
    },
  );

  context.subscriptions.push(
    configDisposable,
    debugDisposable,
    logLevelDisposable,
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
  gamepadService: GamepadService | null,
  loggerRef: Logger,
): void {
  if (!debugChannel) {
    debugChannel = vscode.window.createOutputChannel('Gamify AI Debug');
    loggerRef.setFallbackChannel(debugChannel);
  }
  debugChannel.clear();
  const now = new Date();
  const timestamp = now.toLocaleTimeString();
  debugChannel.appendLine(`=== Gamify AI Debug Info [${timestamp}] ===`);
  debugChannel.appendLine(`Current time: ${now.toISOString()}`);
  debugChannel.appendLine(`Log level: ${loggerRef.getLevel()}`);
  debugChannel.appendLine(
    `Registered modules: ${moduleRegistry.getRegisteredModuleNames().join(', ')}`,
  );
  debugChannel.appendLine('');
  debugChannel.appendLine('=== Gamepad Service ===');
  if (gamepadService) {
    debugChannel.appendLine(`Started: ${gamepadService.isStarted()}`);
    debugChannel.appendLine(`Manager ready: ${gamepadService.isManagerReady()}`);
    debugChannel.appendLine(`Connected gamepads: ${gamepadService.getGamepadCount()}`);

    if (gamepadService.getGamepadCount() > 0) {
      debugChannel.appendLine('');
      for (let i = 0; i < 4; i++) {
        const detail = gamepadService.getGamepadDetail(i);
        if (detail) {
          debugChannel.appendLine(`Gamepad ${i}: ${detail.id}`);
          debugChannel.appendLine(`  Mapping: ${detail.mapping}`);
          debugChannel.appendLine(`  Buttons: ${detail.buttons}, Axes: ${detail.axes}`);
        }
      }
    } else {
      debugChannel.appendLine('No gamepads detected.');
      debugChannel.appendLine('Make sure:');
      debugChannel.appendLine('  1. Gamepad is plugged in before starting VS Code');
      debugChannel.appendLine('  2. No other app is using the gamepad');
      debugChannel.appendLine('  3. Windows Game Controller settings show it as connected');
    }
  } else {
    debugChannel.appendLine('Gamepad service not initialized (extension not activated?)');
  }
  debugChannel.show();
}

export function deactivate(): void {
  debugChannel?.dispose();
  debugChannel = null;
  if (gamepadService) {
    gamepadService.stop();
  }
}
