/** Shared parsing and name resolution for user_id mention tags. */

export type TextSegment = { kind: "text"; text: string };
export type MentionSegment = { kind: "mention"; type: "user"; target_id: string };
export type Segment = TextSegment | MentionSegment;

// Shared regex source for mention tags — exported so remark-mention.ts can
// build its own variants (global / non-global) from the same authoritative
// pattern and avoid format-drift between the two parsers.
export const MENTION_TAG_RE_SOURCE =
  /<mention\s+type="(user)"\s+target_id="([^"]+)"\s*\/>/;

// Matches the single user mention format used by every chat participant.
// Attribute order (type before target_id) matches what both the frontend picker
// and the agent prompt example produce.
const MENTION_TAG_RE = new RegExp(MENTION_TAG_RE_SOURCE.source, "g");

/**
 * Split message content into text and mention segments.
 *
 * Args:
 *   content: Raw message content string, may contain inline mention tags.
 *
 * Returns:
 *   Array of Segment objects in order. TextSegments have non-empty text.
 *   MentionSegments carry the type and target_id from the tag.
 *   Old-style @display_name text is not parsed — returned as plain text.
 */
export function parseMentions(content: string): Segment[] {
  if (!content) return [];

  const segments: Segment[] = [];
  let last = 0;
  let match: RegExpExecArray | null;

  // Reset lastIndex for global re-use safety.
  MENTION_TAG_RE.lastIndex = 0;

  while ((match = MENTION_TAG_RE.exec(content)) !== null) {
    if (match.index > last) {
      segments.push({ kind: "text", text: content.slice(last, match.index) });
    }
    const mentionType = match[1] as "user";
    const targetId = match[2];
    segments.push({ kind: "mention", type: mentionType, target_id: targetId });
    last = match.index + match[0].length;
  }

  if (last < content.length) {
    segments.push({ kind: "text", text: content.slice(last) });
  }

  return segments;
}

/** Resolve mention names consistently across rich text and plain previews. */
export function mentionDisplayName(targetId: string, names: ReadonlyMap<string, string>): string {
  return names.get(targetId) || "unknown";
}

/** Build the same current participant dictionary used by message bubbles. */
export function mentionNameMap(participants: readonly { id: string; user_id?: string | null; display_name?: string | null }[] = []): Map<string, string> {
  return new Map(participants.map((person) => [person.user_id || person.id, person.display_name || person.user_id || person.id]));
}

/** Plain-text surfaces cannot render chips, but must never show wire tags. */
export function mentionPlainText(content: string, names: ReadonlyMap<string, string>): string {
  return parseMentions(content).map((segment) => segment.kind === "text"
    ? segment.text
    : `@${mentionDisplayName(segment.target_id, names)}`).join("");
}
