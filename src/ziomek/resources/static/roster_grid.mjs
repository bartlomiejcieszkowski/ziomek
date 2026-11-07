// The rules for counting tracks and splitting them into blocks, with nothing that draws.
// A frame costs itself, and a gap exists only between two tracks; padding is outside the area the grid is given.

export function count_tracks(space, gap, frame) {
  return Math.floor((space + gap) / (frame + gap));
}

export function space_left(room) {
  return { width: room.measured.width - room.taken.padding.x, height: room.measured.height - room.taken.padding.y };
}

export function whole_frame_grid(room, frame) {
  const left = space_left(room);
  return { rows: count_tracks(left.height, room.taken.gap.y, frame), cols: count_tracks(left.width, room.taken.gap.x, frame) };
}

// The biggest block that can be cut in half by a line between two tracks.
// Position order decides between blocks holding the same number of tracks.
export function pick_the_biggest(blocks) {
  let chosen = null;
  for (const block of blocks) {
    const area = block.rowSpan * block.colSpan;
    if (area < 2) continue;
    if (!chosen) {
      chosen = block;
      continue;
    }
    const chosen_area = chosen.rowSpan * chosen.colSpan;
    if (area > chosen_area || (area === chosen_area && (block.row < chosen.row || (block.row === chosen.row && block.col < chosen.col)))) {
      chosen = block;
    }
  }
  return chosen;
}

export function split_the_blocks(grid, count) {
  const blocks = [{ row: 0, col: 0, rowSpan: grid.rows, colSpan: grid.cols }];
  while (blocks.length < count) {
    const biggest = pick_the_biggest(blocks);
    if (!biggest) return blocks;
    if (biggest.rowSpan >= biggest.colSpan) {
      const half = Math.floor(biggest.rowSpan / 2);
      blocks.splice(blocks.indexOf(biggest), 1, { ...biggest, rowSpan: half }, { ...biggest, row: biggest.row + half, rowSpan: biggest.rowSpan - half });
    } else {
      const half = Math.floor(biggest.colSpan / 2);
      blocks.splice(blocks.indexOf(biggest), 1, { ...biggest, colSpan: half }, { ...biggest, col: biggest.col + half, colSpan: biggest.colSpan - half });
    }
  }
  return blocks;
}

export function blocks_in_frames(grid, count, frame) {
  return split_the_blocks(grid, count).map((block) => ({
    row: block.row,
    col: block.col,
    rows: block.rowSpan,
    cols: block.colSpan,
    tile: { width: block.colSpan * frame, height: block.rowSpan * frame },
  }));
}
