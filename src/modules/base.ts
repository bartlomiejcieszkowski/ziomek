export interface GamepadModule {
  name: string;
  displayName: string;
  actions: readonly string[];
  contexts: readonly string[];
  execute(action: string, context: { context: string }): Promise<void>;
}

export class ModuleRegistry {
  private _modules = new Map<string, GamepadModule>();
  private _actionMap = new Map<string, string>(); // action → moduleId

  register(module: GamepadModule): void {
    this._modules.set(module.name, module);
    for (const action of module.actions) {
      this._actionMap.set(action, module.name);
    }
  }

  async resolve(
    moduleId: string,
    action: string,
    context: { context: string },
  ): Promise<void> {
    const module = this._modules.get(moduleId);
    if (!module) {
      throw new Error(`No module found with name '${moduleId}'`);
    }

    if (!module.actions.includes(action)) {
      throw new Error(
        `Module '${moduleId}' does not handle action '${action}'`,
      );
    }

    return module.execute(action, context);
  }

  async executeAction(
    moduleId: string,
    action: string,
    context: { context: string },
  ): Promise<void> {
    const module = this._modules.get(moduleId);
    if (!module) {
      throw new Error(`No module found with name '${moduleId}'`);
    }

    return module.execute(action, context);
  }

  getModule(moduleId: string): GamepadModule | undefined {
    return this._modules.get(moduleId);
  }

  getRegisteredModuleNames(): string[] {
    return Array.from(this._modules.keys());
  }

  getModuleForAction(action: string): GamepadModule | undefined {
    const moduleId = this._actionMap.get(action);
    if (!moduleId) {
      return undefined;
    }
    return this._modules.get(moduleId);
  }
}
