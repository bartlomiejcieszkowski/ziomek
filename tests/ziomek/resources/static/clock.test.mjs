import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import path from "node:path";

// the tests sit under tests/ in the shape of the code they read, so the source is four levels up
const resources = path.join(import.meta.dirname, "../../../../src/ziomek/resources");

import { moving } from "../../../../src/ziomek/resources/static/clock.mjs";

test("a number that keeps moving is shown as the value plus the time since it was read", () => {
  assert.equal(moving(0, 5), 5);
  assert.equal(moving(116, 25), 141);
});

test("time that has not passed leaves the value as it was", () => {
  assert.equal(moving(0, 0), 0);
});

test("the part that counts time cannot ask for anything", () => {
  const code = readFileSync(path.join(resources, "static", "clock.mjs"), "utf8").replace(/\r\n/g, "\n");
  assert.ok(code.includes("export function moving("), "nothing is here to ask for");
  assert.ok(!code.includes("fetch("), "a part that counts time asks for something");
});
