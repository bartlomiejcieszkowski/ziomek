// The size a skin is drawn at is decided in one place, so a page that draws a picture does not write the same rule again.
export function fit_scale(fit, frameWidth, frameHeight, boxWidth, boxHeight) {
  const byWidth = boxWidth / frameWidth;
  const byHeight = boxHeight / frameHeight;
  if (fit === "fill") return [byWidth, byHeight];
  if (fit === "cover") {
    const scale = Math.max(byWidth, byHeight);
    return [scale, scale];
  }
  if (fit === "none") return [1, 1];
  if (fit === "scale-down") {
    const scale = Math.min(1, Math.min(byWidth, byHeight));
    return [scale, scale];
  }
  const scale = Math.min(byWidth, byHeight);
  return [scale, scale];
}
