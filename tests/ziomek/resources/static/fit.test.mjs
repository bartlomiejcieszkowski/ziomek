import assert from "node:assert/strict";
import { test } from "node:test";

import { fit_scale } from "../../../../src/ziomek/resources/static/fit.mjs";

// The ratios are checked by hand: a frame drawn at its own size is one, and a box that is larger
// than the frame can only be filled by growing the skin. What a definition states decides which
// of the two sizes is taken when the two do not agree.
const frame = { width: 100, height: 50 };

test("a skin asked to fill the box is drawn at the size of each edge of the box", () => {
  assert.deepEqual(fit_scale("fill", frame.width, frame.height, 300, 100), [3, 2]);
});

test("a skin asked to cover the box is drawn at the larger of the two sizes", () => {
  assert.deepEqual(fit_scale("cover", frame.width, frame.height, 300, 100), [3, 3]);
});

test("a skin asked to keep its own size is drawn at one", () => {
  assert.deepEqual(fit_scale("none", frame.width, frame.height, 300, 100), [1, 1]);
});

test("a skin asked to be scaled down is not made larger, only smaller when it does not fit", () => {
  assert.deepEqual(fit_scale("scale-down", frame.width, frame.height, 300, 100), [1, 1]);
  assert.deepEqual(fit_scale("scale-down", frame.width, frame.height, 50, 40), [0.5, 0.5]);
});

test("nothing is stated about the size, so the smaller of the two is taken", () => {
  assert.deepEqual(fit_scale(undefined, frame.width, frame.height, 300, 100), [2, 2]);
});

test("a box smaller than the frame does not draw a skin upside down", () => {
  assert.deepEqual(fit_scale("fill", frame.width, frame.height, 50, 40), [0.5, 0.8]);
});
