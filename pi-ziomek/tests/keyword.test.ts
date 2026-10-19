/**
 * Tests for the keyword gating module.
 */

import { describe, expect, it } from "vitest";

import { gateKeyword, matchKeyword, stripKeyword } from "../src/keyword";

describe("matchKeyword", () => {
  it("matches exact keyword", () => {
    expect(matchKeyword("ziomek", ["ziomek"])).toBe("ziomek");
  });

  it("matches keyword followed by space", () => {
    expect(matchKeyword("ziomek tell me a joke", ["ziomek"])).toBe("ziomek");
  });

  it("matches keyword followed by comma", () => {
    expect(matchKeyword("ziomek, tell me a joke", ["ziomek"])).toBe("ziomek");
  });

  it("is case-insensitive", () => {
    expect(matchKeyword("ZIOMEK tell me a joke", ["ziomek"])).toBe("ziomek");
    expect(matchKeyword("Ziomek tell me a joke", ["ziomek"])).toBe("ziomek");
  });

  it("returns null when no keyword matches", () => {
    expect(matchKeyword("hello world", ["ziomek"])).toBeNull();
  });

  it("returns null for empty text", () => {
    expect(matchKeyword("", ["ziomek"])).toBeNull();
  });

  it("returns null for empty keywords", () => {
    expect(matchKeyword("ziomek", [])).toBeNull();
  });

  it("matches first keyword in list", () => {
    expect(matchKeyword("hey tell me a joke", ["ziomek", "hey"])).toBe("hey");
  });

  it("does not match partial keyword", () => {
    expect(matchKeyword("ziomeks tell me a joke", ["ziomek"])).toBeNull();
    expect(matchKeyword("my ziomek is broken", ["ziomek"])).toBeNull();
  });
});

describe("stripKeyword", () => {
  it("strips keyword with trailing space", () => {
    expect(stripKeyword("ziomek tell me a joke", ["ziomek"])).toBe(
      "tell me a joke",
    );
  });

  it("strips keyword with trailing comma and space", () => {
    expect(stripKeyword("ziomek, tell me a joke", ["ziomek"])).toBe(
      "tell me a joke",
    );
  });

  it("returns original text when no keyword matches", () => {
    expect(stripKeyword("hello world", ["ziomek"])).toBe("hello world");
  });

  it("handles keyword at end of text", () => {
    expect(stripKeyword("ziomek", ["ziomek"])).toBe("");
  });

  it("strips keyword with multiple spaces", () => {
    expect(stripKeyword("ziomek   tell me a joke", ["ziomek"])).toBe(
      "tell me a joke",
    );
  });

  it("is case-insensitive", () => {
    expect(stripKeyword("ZIOMEK tell me a joke", ["ziomek"])).toBe(
      "tell me a joke",
    );
  });

  it("handles multiple keywords", () => {
    expect(stripKeyword("hey tell me a joke", ["ziomek", "hey"])).toBe(
      "tell me a joke",
    );
  });
});

describe("gateKeyword", () => {
  it("returns matched result with cleaned text", () => {
    const result = gateKeyword("ziomek tell me a joke", ["ziomek"]);
    expect(result).toEqual({
      matched: true,
      keyword: "ziomek",
      cleaned: "tell me a joke",
    });
  });

  it("returns no-match result", () => {
    const result = gateKeyword("hello world", ["ziomek"]);
    expect(result).toEqual({
      matched: false,
      cleaned: "hello world",
    });
  });

  it("strips keyword with comma", () => {
    const result = gateKeyword("ziomek, tell me a joke", ["ziomek"]);
    expect(result).toEqual({
      matched: true,
      keyword: "ziomek",
      cleaned: "tell me a joke",
    });
  });

  it("is case-insensitive", () => {
    const result = gateKeyword("ZIOMEK tell me a joke", ["ziomek"]);
    expect(result).toEqual({
      matched: true,
      keyword: "ziomek",
      cleaned: "tell me a joke",
    });
  });

  it("handles empty text", () => {
    const result = gateKeyword("", ["ziomek"]);
    expect(result).toEqual({
      matched: false,
      cleaned: "",
    });
  });

  it("handles empty keywords", () => {
    const result = gateKeyword("ziomek tell me a joke", []);
    expect(result).toEqual({
      matched: false,
      cleaned: "ziomek tell me a joke",
    });
  });

  it("preserves original casing in cleaned text", () => {
    const result = gateKeyword("ziomek Tell Me A Joke", ["ziomek"]);
    expect(result.cleaned).toBe("Tell Me A Joke");
  });
});
