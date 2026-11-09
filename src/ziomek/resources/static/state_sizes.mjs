import { read_number } from "./numbers.mjs";

// A page cannot state what it measured on its own: the values only exist in the browser. It asks for
// them through this, and a part that a server started with --dev adds is what carries them to the
// debug path. Without that part nothing is stated.
export const state_sizes = { report: null };

// One block is the whole grid, which the values already state, so nothing is added for it.
export function describe_blocks(blocks) {
  if (blocks.length < 2) return null;
  return blocks;
}

// A track is measured from the space left after padding and gaps, so the area a page measured is kept apart from what padding takes from it.
// The values are read from the page rather than written here, since CSS is what sets them.
export function room_for(read_number, box, styles) {
  const taken = {
    padding: { x: read_number(styles.paddingLeft) + read_number(styles.paddingRight), y: read_number(styles.paddingTop) + read_number(styles.paddingBottom) },
    gap: { x: read_number(styles.columnGap), y: read_number(styles.rowGap) },
  };
  // Nothing was taken from the area measured, so there is no space left to count in.
  if (taken.padding.x <= 0 || taken.padding.y <= 0) return { measured: box, taken: null };
  return { measured: box, taken };
}

// The values a page measured are put together here, so the page itself does not hold the shape of a report.
export function build_report(room, path, grid, frame, frames, blocks) {
  const taken = room.taken ? { padding: room.taken.padding, gap: grid ? { x: room.taken.gap.x * (grid.cols - 1), y: room.taken.gap.y * (grid.rows - 1) } : null } : null;
  return {
    path: path,
    measured: room.measured,
    taken: taken,
    room: room,
    frames: frames,
    tile: frame ? { width: frame, height: frame } : null,
    blocks: describe_blocks(blocks),
  };
}
