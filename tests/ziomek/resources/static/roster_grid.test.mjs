import assert from "node:assert/strict";
import { test } from "node:test";

import { blocks_in_frames, count_tracks, pick_the_biggest, split_the_blocks, space_left, whole_frame_grid } from "../../../../src/ziomek/resources/static/roster_grid.mjs";

// The numbers here are checked by hand: a frame costs itself, and a gap only exists between two tracks.
// A room is given as what was measured on the page; padding is outside the area the grid is given.
const room = (width, height, padding, gap) => ({ measured: { width, height }, taken: { padding: { x: padding, y: padding }, gap: { x: gap, y: gap } } });

test("one frame in a space takes only itself, not the gap between frames", () => {
  assert.equal(count_tracks(100, 8, 100), 1);
  assert.equal(count_tracks(137, 8, 100), 1);
});

test("a second frame also costs the gap between the two", () => {
  assert.equal(count_tracks(207, 8, 100), 1);
  assert.equal(count_tracks(215, 8, 100), 2);
});

test("nothing is left for a track when padding takes the space", () => {
  assert.deepEqual(space_left(room(60, 60, 30, 8)), { width: 30, height: 30 });
  assert.equal(count_tracks(30, 8, 100), 0);
});

test("the room is divided in whole frames of the space left after padding", () => {
  assert.deepEqual(whole_frame_grid(room(2260, 1311, 30, 8), 100), { rows: 11, cols: 20 });
});

test("splitting the biggest block along its longer edge reaches the number asked for", () => {
  const blocks = split_the_blocks({ rows: 3, cols: 3 }, 4);
  assert.equal(blocks.length, 4);
  // Every block stays a whole number of tracks and the grid is covered exactly once.
  const covered = new Set();
  for (const block of blocks) {
    assert.ok(block.rowSpan >= 1 && block.colSpan >= 1);
    assert.ok(block.row >= 0 && block.col >= 0 && block.row + block.rowSpan <= 3 && block.col + block.colSpan <= 3);
    for (let row = block.row; row < block.row + block.rowSpan; row += 1) {
      for (let col = block.col; col < block.col + block.colSpan; col += 1) {
        const place = row + "-" + col;
        assert.ok(!covered.has(place), "track " + place + " is counted twice");
        covered.add(place);
      }
    }
  }
  assert.equal(covered.size, 9);
});

test("a grid one track wide stays as it is when more blocks are asked for", () => {
  const blocks = split_the_blocks({ rows: 1, cols: 5 }, 6);
  assert.equal(blocks.length, 5);
  assert.ok(blocks.every((block) => block.rowSpan === 1 && block.colSpan === 1));
});

test("the size a block is given is its number of frames times the frame", () => {
  assert.deepEqual(blocks_in_frames({ rows: 2, cols: 3 }, 1, 100), [
    { row: 0, col: 0, rows: 2, cols: 3, tile: { width: 300, height: 200 } },
  ]);
});

test("a block that is one track on both edges is never split", () => {
  const blocks = [{ row: 0, col: 0, rowSpan: 1, colSpan: 1 }, { row: 0, col: 1, rowSpan: 2, colSpan: 3 }];
  assert.deepEqual(pick_the_biggest(blocks), blocks[1]);
  assert.equal(pick_the_biggest([{ row: 0, col: 0, rowSpan: 1, colSpan: 1 }]), null);
});

test("the first block that can be cut is taken in position order", () => {
  const blocks = [{ row: 1, col: 0, rowSpan: 2, colSpan: 2 }, { row: 0, col: 0, rowSpan: 2, colSpan: 2 }];
  assert.deepEqual(pick_the_biggest(blocks), blocks[1]);
});

test("a gap belongs to no block, so a track is counted from what is left after padding and gaps", () => {
  // the numbers here are read from the part, not written by the test
  assert.equal(count_tracks(207 + 8, 8, 100), 2);
});
