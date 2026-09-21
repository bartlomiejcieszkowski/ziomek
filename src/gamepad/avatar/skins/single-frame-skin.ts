/**
 * Single-frame avatar skin.
 *
 * Maps expressions to rows in a single-column sprite sheet.
 * The sprite sheet is assumed to have one expression per row,
 * arranged vertically. Frame layout:
 *   row 0: smiling (happy)
 *   row 1: wide-eyed (surprised/neutral)
 *   row 2: looking sideways (curious/looking/thinking)
 *   row 3: intense/scowling (focused/bored)
 *   row 4: dead/dark (dying)
 *   row 5: exhausted (extra bored)
 */

import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Skin } from '../state-machine.js';

/** Default sprite sheet path */
const __dirname = dirname(fileURLToPath(import.meta.url));
const DEFAULT_SPRITE_PATH = join(__dirname, '../../../../3rd_party/single_frame_sprite_sheet.png');

/** Row index map: expression name → sprite sheet row */
const ROW_MAP: Record<string, number> = {
  happy: 0,
  surprised: 1,
  curious: 2,
  looking: 2,
  focused: 3,
  thinking: 2,
  dying: 4,
  bored: 3,
  neutral: 1,
};

/** Parse PNG header to extract dimensions */
function parsePngHeader(buffer: Buffer): { width: number; height: number } {
  // PNG signature check (first 8 bytes)
  if (buffer[0] !== 0x89 || buffer[1] !== 0x50 || buffer[2] !== 0x4e || buffer[3] !== 0x47) {
    throw new Error('Not a valid PNG file');
  }

  // Width: bytes 16-19 (4 bytes, big-endian)
  const width = (buffer[16] << 24) | (buffer[17] << 16) | (buffer[18] << 8) | buffer[19];
  // Height: bytes 20-23 (4 bytes, big-endian)
  const height = (buffer[20] << 24) | (buffer[21] << 16) | (buffer[22] << 8) | buffer[23];

  if (width <= 0 || height <= 0) {
    throw new Error(`Invalid PNG dimensions: ${width}x${height}`);
  }

  return { width, height };
}

export class SingleFrameSkin implements Skin {
  readonly id = 'single-frame';
  readonly name = 'Single Frame';
  private readonly _spritePath: string;
  private readonly _rows: number;
  private readonly _cols: number;
  private readonly _frameWidth: number;
  private readonly _frameHeight: number;
  private readonly _spriteWidth: number;
  private readonly _spriteHeight: number;

  constructor(options: { spritePath?: string; rows?: number; cols?: number } = {}) {
    this._spritePath = options.spritePath ?? DEFAULT_SPRITE_PATH;

    // Load and parse sprite dimensions
    const buffer = readFileSync(this._spritePath);
    const { width, height } = parsePngHeader(buffer);
    this._spriteWidth = width;
    this._spriteHeight = height;

    if (options.rows && options.cols) {
      this._rows = options.rows;
      this._cols = options.cols;
    } else {
      // Auto-detect: assume one column (vertical strip of square-ish frames)
      this._cols = 1;
      // Estimate rows based on sprite width (frames are ~square)
      this._rows = Math.round(height / width);
      if (this._rows < 1) this._rows = 1;
    }

    this._frameWidth = Math.floor(width / this._cols);
    this._frameHeight = Math.floor(height / this._rows);
  }

  get spriteWidth(): number { return this._spriteWidth; }
  get spriteHeight(): number { return this._spriteHeight; }
  get frameWidth(): number { return this._frameWidth; }
  get frameHeight(): number { return this._frameHeight; }

  getFrameRow(expressionName: string, _cycleIndex: number): number {
    const row = ROW_MAP[expressionName];
    if (row === undefined) {
      // Default to neutral row
      return ROW_MAP['neutral'] ?? 1;
    }
    return row;
  }

  getFrameCount(_expressionName: string): number {
    // Single-frame skin has 1 frame per expression (static row)
    return 1;
  }

  getExpressionNames(): string[] {
    return Object.keys(ROW_MAP);
  }

  /** Get the full sprite buffer for canvas drawing. */
  getSpriteBuffer(): Buffer {
    return readFileSync(this._spritePath);
  }
}
