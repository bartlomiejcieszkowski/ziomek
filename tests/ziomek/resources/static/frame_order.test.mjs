import assert from "node:assert/strict";

import { test } from "node:test";



import { frame_to_show } from "../../../../src/ziomek/resources/static/frame_order.mjs";



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



test("an expression that names nothing shows nothing", () => {

  assert.equal(frame_to_show({ frames: [], loop: true }, 0), null);

});

