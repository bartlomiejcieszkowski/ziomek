import * as vscode from 'vscode';

export interface MappingConfig {
  buttons: Record<number, string>;
  dpad: Record<0 | 1 | 2 | 3, string>;
  axes: Record<string, [number, string]>;
  triggers?: { left?: string; right?: string };
}

export const defaultMapping: MappingConfig = {
  buttons: {
    0: 'send-message',       // A / South
    1: 'cancel',             // B / South
    2: 'new-chat',           // X / West
    3: 'open-slash-menu',   // Y / North
    4: 'scroll-up',         // L1 / LB
    5: 'scroll-down',       // R1 / RB
    6: 'step-forward',      // L2 / LT
    7: 'step-backward',     // R2 / RT
    8: 'open-command-palette', // Select
    9: 'toggle-panel',      // Start
  },
  dpad: {
    0: 'focus-up',    // Up
    1: 'focus-right', // Right
    2: 'focus-down',  // Down
    3: 'focus-left',  // Left
  },
  axes: {
    yAxis: [0, 'scroll-up'],   // Left stick Y (negative = up)
    xAxis: [2, 'scroll-right'], // Right stick X
  },
  triggers: {
    left: 'step-forward',
    right: 'step-backward',
  },
};

export interface ModuleConfig {
  enabled: boolean;
  mapping: MappingConfig;
}

export class ConfigManager {
  private _moduleConfigs: Map<string, ModuleConfig> = new Map();

  constructor() {
    this._loadDefaults();
  }

  private _loadDefaults(): void {
    this._moduleConfigs.set('copilotChat', {
      enabled: true,
      mapping: { ...defaultMapping },
    });
  }

  loadMapping(moduleId: string): MappingConfig {
    const config = this._moduleConfigs.get(moduleId);
    if (!config) {
      return this._deepCloneMapping(defaultMapping);
    }
    return this._deepCloneMapping(config.mapping);
  }

  private _deepCloneMapping(mapping: MappingConfig): MappingConfig {
    const triggers = mapping.triggers
      ? { ...mapping.triggers }
      : undefined;
    return {
      buttons: { ...mapping.buttons },
      dpad: { ...mapping.dpad },
      axes: { ...mapping.axes },
      triggers,
    };
  }

  isEnabled(moduleId: string): boolean {
    const config = this._moduleConfigs.get(moduleId);
    return config?.enabled ?? true;
  }

  setEnabled(moduleId: string, enabled: boolean): void {
    const config = this._moduleConfigs.get(moduleId);
    if (config) {
      config.enabled = enabled;
    }
  }

  refreshSettings(): void {
    const config = vscode.workspace.getConfiguration('gamifyAI');
    const copilotEnabled = config.get('modules.copilotChat.enabled', true);
    this.setEnabled('copilotChat', copilotEnabled);
  }
}
