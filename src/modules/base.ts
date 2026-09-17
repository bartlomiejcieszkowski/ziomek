export interface GamepadModule {
  name: string;
  displayName: string;
  actions: readonly string[];
  contexts: readonly string[];
  execute(action: string, context: { context: string }): Promise<void>;
}

export class ModuleRegistry {
  register(_module: GamepadModule): void {}
  resolve(_moduleId: string, _action: string, _context: { context: string }): Promise<void> {
    return Promise.resolve();
  }
  getModule(_moduleId: string): GamepadModule | undefined {
    return undefined;
  }
}
