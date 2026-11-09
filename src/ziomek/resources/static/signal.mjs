// The rule that decides what a page asks for is kept apart from the page, so it can be read as a value.
const PARTS = ["room", "record"];

export function what_to_ask_for(signal) {
  return PARTS.includes(signal?.kind) ? [signal.kind] : [];
}

// A page that connects has nothing on screen yet, so the first picture is both parts.
export function what_to_ask_on_connection() {
  return [...PARTS];
}
