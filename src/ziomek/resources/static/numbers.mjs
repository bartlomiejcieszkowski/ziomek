// CSS values are read as numbers in one place, so a page that measures a room does not write the same rule again.
export function read_number(value) {
  return parseFloat(value) || 0;
}
