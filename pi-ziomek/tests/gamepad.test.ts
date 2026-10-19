/**
 * Tests for the gamepad module.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GamepadManager } from "../src/gamepad";

// Mock navigator.getGamepads
function createMockGamepad(
  index = 0,
  id = "Xbox Wireless Controller",
  buttons: boolean[] = [],
  axes: readonly number[] = [],
): Gamepad {
  return {
    index,
    id,
    connected: true,
    buttons: buttons.map((pressed) => ({ pressed, value: pressed ? 1.0 : 0.0 })),
    axes,
    mapping: "",
    prototype: undefined,
  } as unknown as Gamepad;
}

let originalGetGamepads: (() => Gamepad[] | null) | undefined;

beforeEach(() => {
  originalGetGamepads = (navigator as any).getGamepads;
  (navigator as any).getGamepads = vi.fn(() => []);
});

afterEach(() => {
  if (originalGetGamepads) {
    (navigator as any).getGamepads = originalGetGamepads;
  } else {
    delete (navigator as any).getGamepads;
  }
});

describe("GamepadManager", () => {
  describe("start/stop", () => {
    it("starts polling", () => {
      const manager = new GamepadManager({ pollIntervalMs: 100 });
      expect(manager.isRunning()).toBe(false);
      manager.start();
      expect(manager.isRunning()).toBe(true);
      manager.stop();
      expect(manager.isRunning()).toBe(false);
    });

    it("prevents duplicate start", () => {
      const manager = new GamepadManager({ pollIntervalMs: 100 });
      manager.start();
      manager.start(); // Should not create a second interval
      expect(manager.isRunning()).toBe(true);
      manager.stop();
    });

    it("stops polling", () => {
      const manager = new GamepadManager({ pollIntervalMs: 100 });
      manager.start();
      manager.stop();
      expect(manager.isRunning()).toBe(false);
    });
  });

  describe("poll", () => {
    it("returns null when no gamepad connected", () => {
      const manager = new GamepadManager();
      (navigator as any).getGamepads = vi.fn(() => []);
      const state = manager.poll();
      expect(state).toBeNull();
    });

    it("returns state when gamepad connected", () => {
      const manager = new GamepadManager();
      (navigator as any).getGamepads = vi.fn(() => [
        createMockGamepad(0, "Xbox Controller", [true, false, false, false]),
      ]);
      const state = manager.poll();
      expect(state).not.toBeNull();
      expect(state!.connected).toBe(true);
      expect(state!.id).toBe("Xbox Controller");
      expect(state!.buttons.length).toBe(4);
      expect(state!.buttons[0].pressed).toBe(true);
      expect(state!.buttons[1].pressed).toBe(false);
    });

    it("detects button press", () => {
      const manager = new GamepadManager({ debounceMs: 0 });
      const pressCb = vi.fn();
      manager.onButton(pressCb);

      // First poll: no gamepad
      (navigator as any).getGamepads = vi.fn(() => []);
      manager.poll();

      // Second poll: gamepad connected, A button pressed
      (navigator as any).getGamepads = vi.fn(() => [
        createMockGamepad(0, "Xbox Controller", [true, false, false, false]),
      ]);
      manager.poll();

      expect(pressCb).toHaveBeenCalledWith("A", "listen_short", true);
    });

    it("debounces button presses", () => {
      const manager = new GamepadManager({ debounceMs: 1000 });
      const pressCb = vi.fn();
      manager.onButton(pressCb);

      // First press
      (navigator as any).getGamepads = vi.fn(() => [
        createMockGamepad(0, "Xbox Controller", [true, false, false, false]),
      ]);
      manager.poll();
      expect(pressCb).toHaveBeenCalledTimes(1);

      // Second press immediately (should be debounced)
      manager.poll();
      expect(pressCb).toHaveBeenCalledTimes(1);
    });

    it("maps button to action from config", () => {
      const manager = new GamepadManager({
        debounceMs: 0,
        buttonMap: { A: "custom_action" },
      });
      const pressCb = vi.fn();
      manager.onButton(pressCb);

      (navigator as any).getGamepads = vi.fn(() => [
        createMockGamepad(0, "Xbox Controller", [true, false, false, false]),
      ]);
      manager.poll();

      expect(pressCb).toHaveBeenCalledWith("A", "custom_action", true);
    });

    it("fires release callback", () => {
      const manager = new GamepadManager({ debounceMs: 0 });
      const pressCb = vi.fn();
      manager.onButton(pressCb);

      // First poll: button pressed
      (navigator as any).getGamepads = vi.fn(() => [
        createMockGamepad(0, "Xbox Controller", [true, false, false, false]),
      ]);
      manager.poll();

      // Second poll: button released
      (navigator as any).getGamepads = vi.fn(() => [
        createMockGamepad(0, "Xbox Controller", [false, false, false, false]),
      ]);
      manager.poll();

      expect(pressCb).toHaveBeenCalledWith("A", "listen_short", true);
      expect(pressCb).toHaveBeenCalledWith("A", "listen_short", false);
    });

    it("handles axes", () => {
      const manager = new GamepadManager();

      (navigator as any).getGamepads = vi.fn(() => [
        createMockGamepad(0, "Xbox Controller", [], [0.5, -0.3]),
      ]);
      const state = manager.poll();
      expect(state!.axes).toEqual([0.5, -0.3]);
    });
  });

  describe("getState", () => {
    it("returns current state", () => {
      const manager = new GamepadManager();

      (navigator as any).getGamepads = vi.fn(() => [
        createMockGamepad(0, "Xbox Controller", [true, false]),
      ]);
      manager.poll();

      const state = manager.getState();
      expect(state).not.toBeNull();
      expect(state!.connected).toBe(true);
    });

    it("returns null when no gamepad", () => {
      const manager = new GamepadManager();
      expect(manager.getState()).toBeNull();
    });
  });

  describe("onButton / offButton", () => {
    it("calls registered callbacks", () => {
      const manager = new GamepadManager({ debounceMs: 0 });
      const cb1 = vi.fn();
      const cb2 = vi.fn();
      manager.onButton(cb1);
      manager.onButton(cb2);

      (navigator as any).getGamepads = vi.fn(() => [
        createMockGamepad(0, "Xbox Controller", [true, false, false, false]),
      ]);
      manager.poll();

      expect(cb1).toHaveBeenCalled();
      expect(cb2).toHaveBeenCalled();
    });

    it("removes unregistered callbacks", () => {
      const manager = new GamepadManager({ debounceMs: 0 });
      const cb1 = vi.fn();
      const cb2 = vi.fn();
      manager.onButton(cb1);
      manager.onButton(cb2);
      manager.offButton(cb1);

      (navigator as any).getGamepads = vi.fn(() => [
        createMockGamepad(0, "Xbox Controller", [true, false, false, false]),
      ]);
      manager.poll();

      expect(cb1).not.toHaveBeenCalled();
      expect(cb2).toHaveBeenCalled();
    });
  });
});
