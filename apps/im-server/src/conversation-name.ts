import type { Row } from './context.js';

/** Project a chat name for its reader without changing identity or access.
 *
 * Args:
 *   conversation: Stored title and its provenance.
 *   members: Current participants in stable display order.
 *   readerId: Actual reader, which may differ from a PA's access-granting owner.
 * Returns:
 *   The peer's name for a participant, both names for an observer, or the
 *   original group, custom or external-channel title.
 */
export function conversationName(conversation: Row, members: Row[], readerId: string): string {
  if (conversation.type !== 'direct' || conversation.title_is_custom || conversation.external_source) return conversation.title;
  return members.filter(member => member.id !== readerId).map(member => member.display_name).join(' ↔ ') || conversation.title;
}
