/**
 * Keyword gating — detect and strip voice command keywords.
 *
 * Used by continuous listening and gamepad voice capture to filter
 * transcriptions before injecting them into the LLM message flow.
 */

export interface KeywordResult {
  matched: boolean;
  keyword?: string;
  cleaned: string;
}

/**
 * Check if text starts with any of the configured keywords (case-insensitive).
 * Returns the first matching keyword or null.
 */
export function matchKeyword(
  text: string,
  keywords: string[],
): string | null {
  if (!text || !keywords.length) return null;

  const lower = text.toLowerCase().trim();

  for (const keyword of keywords) {
    const kw = keyword.toLowerCase();
    if (lower === kw || lower.startsWith(kw + " ") || lower.startsWith(kw + ",")) {
      return keyword;
    }
  }

  return null;
}

/**
 * Strip the leading keyword from text and clean up trailing punctuation/whitespace.
 *
 * @param text — the full transcription
 * @param keywords — list of valid keywords
 * @returns cleaned text with keyword removed, or original text if no match
 */
export function stripKeyword(
  text: string,
  keywords: string[],
): string {
  const matched = matchKeyword(text, keywords);
  if (!matched) return text;

  // Find the position of the keyword in the original text (case-insensitive)
  const lower = text.toLowerCase();
  const kwLower = matched.toLowerCase();
  const idx = lower.indexOf(kwLower);
  if (idx === -1) return text;

  // Get everything after the keyword
  let cleaned = text.slice(idx + matched.length);

  // Strip leading comma, whitespace, and common separators
  cleaned = cleaned.replace(/^[,\s]+/, "").trim();

  return cleaned;
}

/**
 * Full keyword gate: check if text matches, and return structured result.
 */
export function gateKeyword(
  text: string,
  keywords: string[],
): KeywordResult {
  const matched = matchKeyword(text, keywords);
  if (!matched) {
    return { matched: false, cleaned: text };
  }

  return {
    matched: true,
    keyword: matched,
    cleaned: stripKeyword(text, keywords),
  };
}
