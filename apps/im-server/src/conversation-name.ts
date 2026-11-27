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
  if (conversation.title_is_custom) return conversation.title;
  if (conversation.external_source) {
    const agentId = typeof conversation.config_agent_id === 'string' ? conversation.config_agent_id : '';
    const agentMember = agentId ? members.find(member => member.username === `agent:${agentId}`) : undefined;
    const displayName = typeof agentMember?.display_name === 'string' ? agentMember.display_name.trim() : '';
    if (agentId && displayName && displayName !== agentId && typeof conversation.title === 'string') {
      const idPrefix = `${agentId} · `;
      if (conversation.title.startsWith(idPrefix)) {
        return `${displayName} · ${conversation.title.slice(idPrefix.length)}`;
      }
    }
    return conversation.title;
  }
  if (conversation.type !== 'direct') return conversation.title;
  return members.filter(member => member.id !== readerId).map(member => member.display_name).join(' ↔ ') || conversation.title;
}
