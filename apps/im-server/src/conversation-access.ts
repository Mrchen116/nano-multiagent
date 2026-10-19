import type { DatabaseSync } from 'node:sqlite';
import { all, one, type Row } from './context.js';
import { accountEnabled, agentAvailable, canActorAccess } from './identity.js';

/** Resolve account eligibility without treating personal access as company approval. */
export function qualifiedUser(db: DatabaseSync, userId: string): Row | undefined {
  const user = one(db, 'SELECT * FROM users WHERE id=?', userId);
  if (!user) return;
  if (user.username.startsWith('agent:')) {
    if (!agentAvailable(db, one(db, 'SELECT * FROM agent_profiles WHERE agent_id=?', user.username.slice(6)))) return;
  } else if (!accountEnabled(user)) return;
  return user;
}

/** Resolve observers for two-Agent directs and the owner of a PA in a human direct. */
function directAgentOwners(db: DatabaseSync, conversation: Row): string[] {
  if (conversation.type !== 'direct') return [];
  const participants = all(db, `SELECT u.id user_id,u.username,a.owner_id,a.space_id,b.owner_user_id pa_owner FROM conversation_participants p
    JOIN users u ON u.id=p.user_id LEFT JOIN agent_profiles a ON u.username='agent:'||a.agent_id
    LEFT JOIN personal_agent_bindings b ON b.agent_id=a.agent_id AND b.owner_id=a.owner_id
    WHERE p.conversation_id=?`, conversation.id);
  if (participants.length !== 2) return [];
  if (participants.every(p => p.owner_id && p.space_id === conversation.space_id)) return [...new Set(participants.map(p => p.owner_id))];
  if (participants.filter(p=>!p.username.startsWith('agent:')).length !== 1) return [];
  return participants.filter(p=>p.pa_owner && canActorAccess(db,p.user_id,conversation.space_id)).map(p=>p.pa_owner);
}

/** Project read and write rights from the fixed conversation and current actor. */
export function conversationAccess(db: DatabaseSync, id: string, userId: string): Row | undefined {
  const user = qualifiedUser(db, userId);
  if (!user) return;
  const c = one(db, 'SELECT * FROM conversations WHERE id=?', id);
  if (!c || !canActorAccess(db,userId,c.space_id)) return;
  const member = !!one(db, 'SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?', id, userId);
  const observer = !member && !user.username.startsWith('agent:') && directAgentOwners(db,c).includes(userId);
  if (!member && !observer && !(c.type === 'group' && c.visibility === 'public')) return;
  return {
    ...c,
    is_member: member,
    is_observer: observer,
    can_write: member && !c.dissolved_at,
    can_join: !member && c.type === 'group' && c.visibility === 'public' && !c.dissolved_at,
    can_change_visibility: c.space_id === 'company:default' && member && !c.dissolved_at && c.type === 'group' && !user.username.startsWith('agent:') && !!user.is_company_admin,
  };
}

/** Select event readers using the same current eligibility as HTTP and replay.
 *
 * Args:
 *   db: IM database containing the current ownership and membership records.
 *   id: Conversation whose persisted events are being delivered.
 *
 * Returns:
 *   Unique eligible member and owner user IDs; public-group visitors keep polling.
 */
export function conversationReaderIds(db: DatabaseSync, id: string): string[] {
  const c = one(db,'SELECT * FROM conversations WHERE id=?',id);
  if (!c) return [];
  const members = all(db,'SELECT user_id FROM conversation_participants WHERE conversation_id=?',id).map(p => p.user_id);
  return [...new Set([...members,...directAgentOwners(db,c)])].filter(userId => conversationAccess(db,id,userId));
}
