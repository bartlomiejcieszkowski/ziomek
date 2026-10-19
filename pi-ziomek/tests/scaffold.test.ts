/**
 * Tests for the extension scaffold — verifies imports work and no errors.
 */

import { describe, expect, it } from "vitest";

describe("extension scaffold", () => {
  it("imports without errors", async () => {
    // Dynamic import to verify the module loads cleanly
    const mod = await import("../src/index.js");
    expect(mod.default).toBeDefined();
    expect(typeof mod.default).toBe("function");
  });
});
