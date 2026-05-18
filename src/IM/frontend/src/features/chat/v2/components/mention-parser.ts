/**
 * mention-parser.ts — shared mention tag parser for composer mirror and MessageBubble.
 *
 * bugfix-358: wire format changed from @display_name text to inline XML-like tag:
 *   <mention type="agent" target_id="ArchA"/>
 *   <mention type="user"  target_id="user-uuid"/>
 *
 * parseMentions(content) splits a message string into alternating text and mention
 * segments so callers can render each segment appropriately (plain text vs chip).
 */

export type TextSegment = { kind: "text"; text: string };
export type MentionSegment = { kind: "mention"; type: "agent" | "user"; target_id: string };
export type Segment = TextSegment | MentionSegment;

// Matches self-closing <mention type="agent"|"user" target_id="X"/> tags.
// Attribute order (type before target_id) matches what both the frontend picker
// and the agent prompt example produce.
const MENTION_TAG_RE =
  /<mention\s+type="(agent|user)"\s+target_id="([^"]+)"\s*\/>/g;

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
    const mentionType = match[1] as "agent" | "user";
    const targetId = match[2];
    segments.push({ kind: "mention", type: mentionType, target_id: targetId });
    last = match.index + match[0].length;
  }

  if (last < content.length) {
    segments.push({ kind: "text", text: content.slice(last) });
  }

  return segments;
}
