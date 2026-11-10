// The rules that decide what a moment draws are kept apart from the page, so they can be read as values.

export function frame_to_show(entry, step) {
  const names = entry?.frames ?? [];
  if (names.length === 0) return null;
  if (names.length === 1) return names[0];
  if (entry.loop) return names[step % names.length];
  // A list that does not loop stays where it reached.
  return names[Math.min(step, names.length - 1)];
}

// A participant is drawn from the mapping the page already has. Where nothing is stated for what they
// show, the frame that was answered for them is what draws them, and when neither exists nothing draws.
export function frame_for_view(mapping, expression, answered, step) {
  const entry = mapping?.[expression];
  if (!entry) return answered ?? null;
  return frame_to_show(entry, step);
}

// A moment belongs to what a participant shows. It is kept while they show the same thing, and a change
// of what they show starts it again at the first entry, so no frame from the middle of another list is
// shown.
export function moment_to_use(shown, current, reached) {
  if (shown !== current) return 0;
  return reached ?? 0;
}

// The time between frames comes from what the skin states. A skin that states none is drawn at the time
// the page keeps; one that shows a single frame has no time between frames, so nothing is due.
export function interval_to_wait(entry, page_default) {
  if ((entry?.frames ?? []).length < 2) return null;
  return entry.interval_ms ?? page_default;
}
