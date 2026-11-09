import assert from "node:assert/strict";
import { test } from "node:test";

import { AGAIN_AFTER, DRAWERS, ask_for } from "../../../../src/ziomek/resources/static/roster.mjs";
import { what_to_ask_for, what_to_ask_on_connection } from "../../../../src/ziomek/resources/static/signal.mjs";

// The page is read here as values: what a signal names reaches only the drawer for that part.
// The drawers are replaced with recorders, so a signal can be followed without a page on screen.
const reached_by = (signal) => {
  const reached = [];
  for (const part of Object.keys(DRAWERS)) DRAWERS[part] = () => reached.push(part);
  ask_for(what_to_ask_for(signal));
  return reached;
};

test("a page told about the room reaches only the drawer for the room", () => {
  assert.deepEqual(reached_by({ kind: "room" }), ["room"]);
});

test("a page told about the record reaches only the drawer for the record", () => {
  assert.deepEqual(reached_by({ kind: "record" }), ["record"]);
});

test("a page told about something it cannot draw reaches no drawer", () => {
  assert.deepEqual(reached_by({ kind: "expression" }), []);
});

test("each part of the picture has a drawer of its own", () => {
  assert.deepEqual(Object.keys(DRAWERS).sort(), ["record", "room"]);
});

test("a page that connects reaches both parts once", () => {
  const reached = [];
  for (const part of Object.keys(DRAWERS)) DRAWERS[part] = () => reached.push(part);
  ask_for(what_to_ask_on_connection());
  assert.deepEqual(reached, ["room", "record"]);
});

test("a page that lost its connection waits three seconds before asking again", () => {
  assert.equal(AGAIN_AFTER, 3000);
});
