/**
 * SkinRegistry — factory and lookup for avatar skins.
 *
 * Provides a simple factory pattern for creating named skins
 * and a registry for custom skin classes.
 */

import { Skin } from './state-machine.js';
import { SingleFrameSkin } from './skins/single-frame-skin.js';

/** Skin factory function signature */
export type SkinFactory = (options?: Record<string, unknown>) => Skin;

/** Registered skin class or factory */
type SkinEntry = {
  className: string;
  factory: SkinFactory;
};

/**
 * SkinRegistry manages available avatar skins.
 *
 * Built-in skins:
 *   - 'single-frame': Single-frame avatar skin
 *
 * Custom skins can be registered via registerSkin().
 */
export class SkinRegistry {
  private static readonly _instance = new SkinRegistry();
  private readonly _skins: Map<string, SkinEntry> = new Map();

  private constructor() {
    // Register built-in skins
    this._register('single-frame', SingleFrameSkin);
  }

  /** Get the singleton registry instance */
  static getInstance(): SkinRegistry {
    return SkinRegistry._instance;
  }

  /** Register a custom skin class or factory */
  registerSkin(name: string, factory: (options?: Record<string, unknown>) => Skin): void {
    // SAFETY: factory.name is a standard JS function property; cast hides it from TS
    this._skins.set(name, {
      className: (factory as unknown as { name: string }).name || 'AnonymousSkin',
      factory,
    });
  }

  /** Create a named skin instance with optional options */
  create(name: string, options?: Record<string, unknown>): Skin | null {
    const entry = this._skins.get(name);
    if (!entry) {
      return null;
    }
    return entry.factory(options);
  }

  /** Check if a skin name is registered */
  has(name: string): boolean {
    return this._skins.has(name);
  }

  /** Get all registered skin names */
  getNames(): string[] {
    return Array.from(this._skins.keys());
  }

  /** Get metadata for a registered skin */
  getMetadata(name: string): { className: string } | null {
    const entry = this._skins.get(name);
    if (!entry) {
      return null;
    }
    return { className: entry.className };
  }

  /** Clear all custom registrations (for testing) */
  clearCustom(): void {
    // Keep built-in skins, only remove custom ones
    for (const name of this._skins.keys()) {
      if (name !== 'single-frame') {
        this._skins.delete(name);
      }
    }
  }

  private _register(name: string, skinClass: new (options?: Record<string, unknown>) => Skin): void {
    this._skins.set(name, {
      className: skinClass.name || name,
      factory: (options) => new skinClass(options),
    });
  }
}
