import type { DatabaseSync } from 'node:sqlite';
import { one, type Row } from './context.js';
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

/** Project read and write rights from the fixed conversation and current actor. */
export function conversationAccess(db: DatabaseSync, id: string, userId: string): Row | undefined {
  const user = qualifiedUser(db, userId);
  if (!user) return;
  const c = one(db, 'SELECT * FROM conversations WHERE id=?', id);
  if (!c || !canActorAccess(db,userId,c.space_id)) return;
  const member = !!one(db, 'SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?', id, userId);
  if (!member && !(c.type === 'group' && c.visibility === 'public')) return;
  return {
    ...c,
    is_member: member,
    can_write: member && !c.dissolved_at,
    can_join: !member && c.type === 'group' && c.visibility === 'public' && !c.dissolved_at,
    can_change_visibility: c.space_id === 'company:default' && member && !c.dissolved_at && c.type === 'group' && !user.username.startsWith('agent:') && !!user.is_company_admin,
  };
}
