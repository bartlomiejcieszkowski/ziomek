import assert from "node:assert/strict";
import { test } from "node:test";

import { frame_for_view, frame_to_show, interval_to_wait, moment_to_use } from "../../../../src/ziomek/resources/static/frame_order.mjs";

// Which frame a moment shows is decided from what an expression names, in the order it names it, and
// from whether the list returns to its first entry. The rule keeps no moment of its own, so a page can
// be read without a timer.

const looping = { frames: ["a", "b", "c"], loop: true };
const once = { frames: ["a", "b", "c"], loop: false };

test("the frames an expression names are shown in the order it names them", () => {
  assert.equal(frame_to_show(once, 0), "a");
  assert.equal(frame_to_show(once, 1), "b");
  assert.equal(frame_to_show(once, 2), "c");
});

test("a list that loops returns to its first entry after the last", () => {
  assert.equal(frame_to_show(looping, 3), "a");
  assert.equal(frame_to_show(looping, 6), "a");
});

test("a list that does not loop stays at its last entry", () => {
  assert.equal(frame_to_show(once, 3), "c");
  assert.equal(frame_to_show(once, 12), "c");
});

test("an expression that names one frame shows that frame at every moment", () => {
  assert.equal(frame_to_show({ frames: ["only"], loop: false }, 0), "only");
  assert.equal(frame_to_show({ frames: ["only"], loop: true }, 9), "only");
});

test("an expression that states nothing is answered for the moment it names", () => {
  // The rule is asked what a moment shows, and it answers for that moment. Where it states nothing, the
  // answer is the frame it was answered for the participant, not a frame picked by the caller.
test("an expression that states nothing is answered for the moment it names", () => {
  // The rule is asked what a moment shows, and it answers for that moment. Where it states nothing, the
  // answer is the frame it was answered for the participant, not a frame picked by the caller.
  assert.equal(frame_to_show({ frames: [], period: 5000 }, 2, "answered"), "answered");
});
});

// What a page draws for a participant is decided from the mapping it already has, so the choice between
// a list and the single frame that was answered for them is a rule too, read as a value.

const stated = { "happy": { frames: ["first", "second"], loop: false } };

test("a participant whose expression states a list is drawn with the frame that moment names", () => {
  assert.equal(frame_for_view(stated, "happy", "answered", 1), "second");
});

test("a participant whose expression states no list is drawn with the frame that was answered for them", () => {
  assert.equal(frame_for_view(stated, "sad", "answered", 0), "answered");
});

test("a skin that states nothing at all is drawn with the frame that was answered for a participant", () => {
  assert.equal(frame_for_view({}, "happy", "answered", 4), "answered");
});

test("nothing is drawn for a participant when nothing is stated and nothing was answered", () => {
  assert.equal(frame_for_view({}, "happy", undefined, 0), null);
});

// A moment belongs to what a participant shows. While they show the same thing the moment they reached
// is kept; when they show something else it starts again at its first entry.

test("the moment a participant reached is kept while they show the same thing", () => {
  assert.equal(moment_to_use("happy", "happy", 2), 2);
});

test("a participant who shows something else starts at its first entry", () => {
  assert.equal(moment_to_use("happy", "sad", 4), 0);
});

test("a participant seen for the first time starts at the first entry", () => {
  assert.equal(moment_to_use(undefined, "happy", undefined), 0);
});

// The time between frames comes from the definition. A skin that states none is drawn at the time the
// page keeps.

test("the time a skin states for its frames is the time it is drawn at", () => {
  assert.equal(interval_to_wait({ frames: ["a", "b"], interval_ms: 120 }, 200), 120);
});

test("a skin that states no time between its frames is drawn at the time the page keeps", () => {
  assert.equal(interval_to_wait({ frames: ["a", "b"] }, 200), 200);
});

test("a skin that shows one frame has no time between frames", () => {
  assert.equal(interval_to_wait({ frames: ["a"], interval_ms: 120 }, 200), null);
});
