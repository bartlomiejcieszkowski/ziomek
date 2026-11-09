// The rule that decides what a page asks for is kept apart from the page, so it can be read as a value.
const PARTS = ["room", "record"];

// A message the page cannot read is read as nothing, so a message it was not written for does not stop the page.
export function read_signal(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export function what_to_ask_for(signal) {
  return PARTS.includes(signal?.kind) ? [signal.kind] : [];
}

// A page that connects has nothing on screen yet, so the first picture is both parts.
export function what_to_ask_on_connection() {
  return [...PARTS];
}
