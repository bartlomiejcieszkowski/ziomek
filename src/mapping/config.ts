export interface ModuleConfig {
  enabled: boolean;
  mapping: Record<string, string>;
}

export function getDefaultModuleConfig(): ModuleConfig {
  return {
    enabled: true,
    mapping: {},
  };
}
