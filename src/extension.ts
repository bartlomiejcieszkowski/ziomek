import * as vscode from 'vscode';
import { spawn } from 'child_process';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { Logger } from './logger.js';
import { GamepadService } from './gamepad/service.js';
import { GamepadAvatarPanel } from './gamepad/avatar-panel.js';
import { SkinRegistry } from './gamepad/avatar/skin-registry.js';
import { AvatarStateMachine, type GamepadAvatarInput } from './gamepad/avatar/state-machine.js';
import { ContextTracker } from './context.js';
import { ModuleRegistry } from './modules/base.js';
import { MappingResolver } from './mapping/resolver.js';
import { ConfigManager } from './mapping/config.js';
import { CopilotChatModule } from './modules/copilot-chat.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

let gamepadService: GamepadService | null = null;
let avatarPanel: GamepadAvatarPanel | null = null;
let stateMachine: AvatarStateMachine | null = null;
let avatarPollTimer: ReturnType<typeof setInterval> | null = null;
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

  gamepadService.start().catch((error) => {
    vscode.window.showErrorMessage(`Gamify AI: Failed to initialize gamepad service — ${error.message}`);
  });

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

  // Register gamepad debug window command
  const gamepadWindowDisposable = vscode.commands.registerCommand(
    'gamifyAI.showGamepadWindow',
    () => {
      showGamepadWindow();
    },
  );

  // Avatar panel — created after gamepadService so it can receive state
  const skinRegistry = SkinRegistry.getInstance();
  stateMachine = new AvatarStateMachine();
  avatarPanel = new GamepadAvatarPanel(context, skinRegistry, stateMachine);

  // Register the avatar view provider
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      GamepadAvatarPanel.viewType,
      avatarPanel,
    ),
  );

  // Register avatar panel command (to focus/reveal the view)
  const showAvatarDisposable = vscode.commands.registerCommand(
    'gamifyAI.showAvatar',
    () => {
      avatarPanel?.show();
    },
  );

  context.subscriptions.push(
    configDisposable,
    debugDisposable,
    logLevelDisposable,
    gamepadWindowDisposable,
    showAvatarDisposable,
    // Emotion setter (callable by other extensions)
    vscode.commands.registerCommand(
      'gamifyAI.setEmotion',
      (expressionName: string) => {
        if (!stateMachine) return;
        const success = stateMachine.setExpression(expressionName);
        const exprNames = stateMachine.getExpressionNames().join(', ');
        if (success) {
          vscode.window.showInformationMessage(`Avatar emotion set to: ${expressionName}`);
        } else {
          vscode.window.showErrorMessage(`Unknown expression '${expressionName}'. Valid: ${exprNames}`);
        }
      },
    ),
  );

  // Gamepad polling loop for avatar panel (10 FPS)
  let lastAvatarUpdate = 0;
  avatarPollTimer = setInterval(() => {
    const now = Date.now();
    if (!avatarPanel || !stateMachine) return;
    if (now - lastAvatarUpdate < 100) return;
    lastAvatarUpdate = now;

    const gamepads = gamepadService?.getGamepads() || [];
    avatarPanel.updateFromGamepad(gamepads);

    // Feed state to state machine
    const input: GamepadAvatarInput = {
      buttons: gamepads.length > 0 ? gamepads[0].buttons : [],
      axes: gamepads.length > 0 ? gamepads[0].axes : [],
      connected: gamepads.length > 0,
      streaming: false,
      chatFocused: false,
      errorState: false,
    };

    stateMachine.update(input);
    const state = stateMachine.tick(16);
    avatarPanel.updateState(state);
  }, 100);
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

/** Launch the SDL-based gamepad debug window in a separate process. */
function showGamepadWindow(): void {
  const scriptPath = join(__dirname, '..', 'debug_tools', 'gamepad-window.js');

  try {
    const child = spawn('node', [scriptPath], {
      stdio: ['ignore', 'ignore', 'inherit'],
      detached: true,
    });

    child.unref();
    vscode.window.showInformationMessage(
      `Gamify AI: Gamepad debug window launched.`,
    );
    logger?.info('extension', `Launched gamepad debug window (pid ${child.pid})`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    vscode.window.showErrorMessage(
      `Gamify AI: Failed to launch gamepad debug window — ${msg}`,
    );
    logger?.error('extension', `Failed to launch gamepad debug window: ${msg}`);
  }
}

export function deactivate(): void {
  debugChannel?.dispose();
  debugChannel = null;
  if (gamepadService) {
    gamepadService.stop();
  }
  if (avatarPollTimer) {
    clearInterval(avatarPollTimer);
    avatarPollTimer = null;
  }
}
