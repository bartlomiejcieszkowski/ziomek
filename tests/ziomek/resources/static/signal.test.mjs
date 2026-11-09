import assert from "node:assert/strict";
import { test } from "node:test";

import { what_to_ask_for, what_to_ask_on_connection } from "../../../../src/ziomek/resources/static/signal.mjs";

// What a signal names decides which part a page asks for. A signal that names nothing a page can
// draw leaves it asking for nothing, and the first picture is still the whole picture.

test("a signal that names the room asks for the room only", () => {
  assert.deepEqual(what_to_ask_for({ kind: "room" }), ["room"]);
});

test("a signal that names the record asks for the record only", () => {
  assert.deepEqual(what_to_ask_for({ kind: "record" }), ["record"]);
});

test("a signal that names nothing asks for nothing", () => {
  assert.deepEqual(what_to_ask_for({}), []);
  assert.deepEqual(what_to_ask_for({ kind: "expression" }), []);
});

test("a page that connects is asked for both parts once", () => {
  assert.deepEqual(what_to_ask_on_connection(), ["room", "record"]);
});
