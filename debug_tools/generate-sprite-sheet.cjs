#!/usr/bin/env node
/**
 * Generates a Doom-style avatar sprite sheet with distinct colors per frame.
 * Each frame cell gets a unique bright color so you can visually identify which
 * cell is which. Edit those colored rectangles in an image editor to draw your sprites.
 *
 * Frame layout (vertical strip, one column):
 *   Row 0: RED    - happy
 *   Row 1: BLUE   - surprised
 *   Row 2: GREEN  - curious / thinking / looking
 *   Row 3: PURPLE - focused / bored
 *   Row 4: ORANGE - dying
 *   Row 5: CYAN   - idle (neutral)
 *
 * Each frame is 100x100px. The face occupies the center 50x50 area.
 * The outer 25px border on each side is the background color.
 */

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const FRAME_W = 100;
const FRAME_H = 100;
const ROWS = 6;
const COLS = 1;
const CANVAS_W = FRAME_W * COLS;
const CANVAS_H = FRAME_H * ROWS;

// Each frame gets a distinct background color so you can see boundaries
const FRAME_COLORS = [
  [255, 50, 50],   // RED    - happy
  [50, 120, 255],  // BLUE   - surprised
  [50, 220, 80],   // GREEN  - curious / thinking / looking
  [190, 50, 230],  // PURPLE - focused / bored
  [255, 120, 30],  // ORANGE - dying
  [30, 210, 210],  // CYAN   - idle (neutral)
];

// PNG signature
const PNG_SIG = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);

// CRC32 lookup table
const CRC_TABLE = new Uint32Array(256);
for (let i = 0; i < 256; i++) {
  let c = i;
  for (let j = 0; j < 8; j++) {
    c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
  }
  CRC_TABLE[i] = c;
}

function crc32(buf) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) {
    crc = CRC_TABLE[(crc ^ buf[i]) & 0xFF] ^ (crc >>> 8);
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

// Build the raw image data (with filter bytes)
function buildImageRows() {
  const rows = [];
  const faceSize = 50;
  const faceLeft = 25;
  const faceTop = 25;
  const hair = [74, 55, 40];
  const white = [255, 255, 255];
  const black = [0, 0, 0];

  for (let r = 0; r < CANVAS_H; r++) {
    const rowBytes = 1 + CANVAS_W * 3; // 1 filter byte + 3 bytes per pixel
    const row = Buffer.alloc(rowBytes);
    row[0] = 0; // filter: None

    // Determine frame color for this row
    const frameIdx = Math.floor(r / FRAME_H);
    const [bgR, bgG, bgB] = FRAME_COLORS[frameIdx];

    // Fill entire row with frame background color
    for (let c = 0; c < CANVAS_W; c++) {
      const px = 1 + c * 3;
      row[px] = bgR;
      row[px + 1] = bgG;
      row[px + 2] = bgB;
    }

    // Draw face background in the center 50x50 area
    for (let dr = 0; dr < faceSize; dr++) {
      for (let dc = 0; dc < faceSize; dc++) {
        const px = 1 + (faceLeft + dc) * 3;
        row[px] = Math.max(0, bgR - 80);
        row[px + 1] = Math.max(0, bgG - 80);
        row[px + 2] = Math.max(0, bgB - 80);
      }
    }

    rows.push(row);
  }

  // Now draw all the expression features
  const expressions = ['happy', 'surprised', 'curious', 'focused', 'dying', 'idle'];

  for (let frameIdx = 0; frameIdx < ROWS; frameIdx++) {
    const frameBase = frameIdx * FRAME_H;
    const row0 = frameBase + faceTop; // first row that has face

    const setPx = (r, c, r2, g, b) => {
      if (c < 0 || c >= CANVAS_W || r < 0 || r >= CANVAS_H) return;
      const row = rows[r];
      row[1 + c * 3] = r2;
      row[1 + c * 3 + 1] = g;
      row[1 + c * 3 + 2] = b;
    };

    // Hair top (rows 18-31)
    for (let dr = 0; dr < 14; dr++) {
      const rr = frameBase + 18 + dr;
      for (let dc = 0; dc < 54; dc++) {
        setPx(rr, 23 + dc, ...hair);
      }
    }
    // Hair sides
    for (let dr = 0; dr < 8; dr++) {
      setPx(frameBase + 25 + dr, 22, ...hair);
      setPx(frameBase + 25 + dr, 72, ...hair);
    }

    // Expression features
    if (expressions[frameIdx] === 'happy') {
      for (let dr = 0; dr < 10; dr++) for (let dc = 0; dc < 12; dc++) setPx(row0 + dr, 32 + dc, ...white);
      for (let dr = 0; dr < 10; dr++) for (let dc = 0; dc < 12; dc++) setPx(row0 + dr, 58 + dc, ...white);
      for (let dr = 0; dr < 4; dr++) for (let dc = 0; dc < 4; dc++) setPx(row0 + 5 + dr, 35 + dc, ...black);
      for (let dr = 0; dr < 4; dr++) for (let dc = 0; dc < 4; dc++) setPx(row0 + 5 + dr, 61 + dc, ...black);
      for (let dc = 0; dc < 28; dc++) setPx(row0 + 25, 36 + dc, ...black);
    } else if (expressions[frameIdx] === 'surprised') {
      for (let dr = 0; dr < 14; dr++) for (let dc = 0; dc < 16; dc++) setPx(row0 - 3 + dr, 30 + dc, ...white);
      for (let dr = 0; dr < 14; dr++) for (let dc = 0; dc < 16; dc++) setPx(row0 - 3 + dr, 56 + dc, ...white);
      for (let dr = 0; dr < 4; dr++) for (let dc = 0; dc < 4; dc++) setPx(row0 - 2 + dr, 35 + dc, ...black);
      for (let dr = 0; dr < 4; dr++) for (let dc = 0; dc < 4; dc++) setPx(row0 - 2 + dr, 61 + dc, ...black);
      for (let dr = 0; dr < 6; dr++) for (let dc = 0; dc < 14; dc++) setPx(row0 + 23 + dr, 43 + dc, ...black);
      for (let dc = 0; dc < 20; dc++) setPx(row0 + 20, 40 + dc, ...black);
    } else if (expressions[frameIdx] === 'curious' || expressions[frameIdx] === 'thinking') {
      for (let dr = 0; dr < 10; dr++) for (let dc = 0; dc < 12; dc++) setPx(row0 + dr, 32 + dc, ...white);
      for (let dr = 0; dr < 10; dr++) for (let dc = 0; dc < 12; dc++) setPx(row0 + dr, 58 + dc, ...white);
      for (let dc = 0; dc < 4; dc++) setPx(row0 + 3, 38 + dc, ...black);
      for (let dc = 0; dc < 4; dc++) setPx(row0 + 3, 64 + dc, ...black);
      for (let dc = 0; dc < 16; dc++) setPx(row0 + 22, 42 + dc, ...black);
    } else if (expressions[frameIdx] === 'focused') {
      for (let dr = 0; dr < 8; dr++) for (let dc = 0; dc < 12; dc++) setPx(row0 + 3 + dr, 32 + dc, ...white);
      for (let dr = 0; dr < 8; dr++) for (let dc = 0; dc < 12; dc++) setPx(row0 + 3 + dr, 60 + dc, ...white);
      for (let dc = 0; dc < 4; dc++) setPx(row0 + 6, 34 + dc, ...black);
      for (let dc = 0; dc < 4; dc++) setPx(row0 + 6, 62 + dc, ...black);
      for (let dr = 0; dr < 3; dr++) {
        setPx(row0 + dr, 30, 60, 40, 30);
        setPx(row0 + dr, 54, 60, 40, 30);
      }
      for (let dc = 0; dc < 16; dc++) setPx(row0 + 24, 42 + dc, ...black);
    } else if (expressions[frameIdx] === 'dying') {
      // X eyes - left
      for (let i = 0; i < 10; i++) {
        setPx(row0 + i, 33 + i, ...black);
        setPx(row0 + i, 43 - i, ...black);
      }
      // X eyes - right
      for (let i = 0; i < 10; i++) {
        setPx(row0 + i, 57 + i, ...black);
        setPx(row0 + i, 67 - i, ...black);
      }
      for (let dr = 0; dr < 8; dr++) for (let dc = 0; dc < 24; dc++) setPx(row0 + 22 + dr, 38 + dc, ...black);
    } else {
      // Neutral / idle
      for (let dr = 0; dr < 10; dr++) for (let dc = 0; dc < 12; dc++) setPx(row0 + dr, 32 + dc, ...white);
      for (let dr = 0; dr < 10; dr++) for (let dc = 0; dc < 12; dc++) setPx(row0 + dr, 58 + dc, ...white);
      for (let dc = 0; dc < 4; dc++) setPx(row0 + 3, 35 + dc, ...black);
      for (let dc = 0; dc < 4; dc++) setPx(row0 + 3, 61 + dc, ...black);
      for (let dc = 0; dc < 16; dc++) setPx(row0 + 22, 42 + dc, ...black);
    }
  }

  // Flatten rows into single buffer (keep filter bytes)
  return Buffer.concat(rows);
}

// Build image data with filter bytes
const imageRows = buildImageRows();
console.log('Image rows size:', imageRows.length, 'bytes (expected:', CANVAS_H * (CANVAS_W * 3 + 1), ')');

// Compress
const compressed = zlib.deflateSync(imageRows, { level: 9 });
console.log('Compressed:', compressed.length, 'bytes');

// Build PNG file
const ihdr = Buffer.alloc(13);
ihdr.writeUInt32BE(CANVAS_W, 0);
ihdr.writeUInt32BE(CANVAS_H, 4);
ihdr[8] = 8; // bit depth
ihdr[9] = 2; // color type: RGB
ihdr[10] = 0; // compression
ihdr[11] = 0; // filter
ihdr[12] = 0; // interlace

// Calculate total size
let offset = PNG_SIG.length; // after signature
offset += 4 + 4 + 13 + 4;  // IHDR
offset += 4 + 4 + 1 + 4;   // sRGB
offset += 4 + 4 + 4 + 4;   // gAMA
offset += 4 + 4 + compressed.length + 4; // IDAT
offset += 4 + 4 + 0 + 4;   // IEND

const png = Buffer.alloc(offset);
offset = 0;
PNG_SIG.copy(png, offset);
offset += PNG_SIG.length;

// IHDR
offset += 4; // skip length
png.writeUInt32BE(13, offset - 4);
png.write('IHDR', offset);
offset += 4;
ihdr.copy(png, offset);
offset += 13;
const ihdrCrc = crc32(Buffer.concat([Buffer.from('IHDR'), ihdr]));
png.writeUInt32BE(ihdrCrc, offset);
offset += 4;

// sRGB
offset += 4;
png.writeUInt32BE(1, offset - 4);
png.write('sRGB', offset);
offset += 4;
png[offset] = 0;
offset += 1;
png.writeUInt32BE(crc32(Buffer.concat([Buffer.from('sRGB'), Buffer.from([0])])), offset);
offset += 4;

// gAMA
offset += 4;
png.writeUInt32BE(4, offset - 4);
png.write('gAMA', offset);
offset += 4;
const gamaBuf = Buffer.alloc(4);
gamaBuf.writeUInt32BE(45455, 0);
gamaBuf.copy(png, offset);
offset += 4;
png.writeUInt32BE(crc32(Buffer.concat([Buffer.from('gAMA'), gamaBuf])), offset);
offset += 4;

// IDAT
offset += 4;
png.writeUInt32BE(compressed.length, offset - 4);
png.write('IDAT', offset);
offset += 4;
compressed.copy(png, offset);
offset += compressed.length;
png.writeUInt32BE(crc32(Buffer.concat([Buffer.from('IDAT'), compressed])), offset);
offset += 4;

// IEND
offset += 4;
png.writeUInt32BE(0, offset - 4);
png.write('IEND', offset);
offset += 4;
png.writeUInt32BE(crc32(Buffer.from('IEND')), offset);
offset += 4;

// Write file
const outputPath = path.join(__dirname, '..', '3rd_party', 'single_frame_sprite_sheet.png');
fs.writeFileSync(outputPath, png);

console.log('\nGenerated:', outputPath);
console.log('PNG size:', png.length, 'bytes');
console.log('Dimensions:', CANVAS_W, 'x', CANVAS_H);
console.log('Frames: 6 rows of', FRAME_W, 'x', FRAME_H, 'px');
console.log('\nFrame colors:');
const names = ['RED', 'BLUE', 'GREEN', 'PURPLE', 'ORANGE', 'CYAN'];
FRAME_COLORS.forEach(([r, g, b], i) => {
  console.log('  Row', i, '(' + names[i].padEnd(6) + '): RGB(' + r + ', ' + g + ', ' + b + ')');
});
