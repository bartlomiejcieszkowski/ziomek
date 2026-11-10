// A number that keeps moving after it was read is shown as the value plus the time since reading, so the page does not have to ask again for something that only moved.
export function moving(value, seconds_since_reading) {
  return value + seconds_since_reading;
}
