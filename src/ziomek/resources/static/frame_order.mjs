// The rule that decides which frame a moment shows is kept apart from the page, so it can be read as a value.

export function frame_to_show(entry, step) {
  const names = entry?.frames ?? [];
  if (names.length === 0) return null;
  if (names.length === 1) return names[0];
  if (entry.loop) return names[step % names.length];
  // A list that does not loop stays where it reached.
  return names[Math.min(step, names.length - 1)];
}
