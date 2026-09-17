export interface MappingConfig {
  buttons: Record<number, string>;
  dpad: Record<0 | 1 | 2 | 3, string>;
  axes: Record<string, [number, string]>;
  triggers: { left?: string; right?: string };
}

export class MappingResolver {
  resolve(action: string): void {
    // Stub
  }
}
