import type { DatabaseSync } from 'node:sqlite';
import { one, type Row } from './context.js';

/** Resolve current company qualification independently from conversation membership. */
export function qualifiedUser(db: DatabaseSync, userId: string): Row | undefined {
  const user = one(db, 'SELECT * FROM users WHERE id=?', userId);
  if (!user || !user.username.startsWith('agent:') && user.membership_status !== 'active') return;
  if (user.username.startsWith('agent:') && !one(db,
    `SELECT 1 FROM agent_profiles a JOIN users owner ON owner.owner_id=a.owner_id
     AND owner.username NOT LIKE 'agent:%' AND owner.membership_status='active'
     WHERE a.agent_id=? AND a.is_stale=0`, user.username.slice(6))) return;
  return user;
}

/** Project read and write rights from the fixed conversation and current actor. */
export function conversationAccess(db: DatabaseSync, id: string, userId: string): Row | undefined {
  const user = qualifiedUser(db, userId);
  if (!user) return;
  const c = one(db, 'SELECT * FROM conversations WHERE id=?', id);
  if (!c) return;
  const member = !!one(db, 'SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?', id, userId);
  if (!member && !(c.type === 'group' && c.visibility === 'public')) return;
  return {
    ...c,
    is_member: member,
    can_write: member && !c.dissolved_at,
    can_join: !member && c.type === 'group' && c.visibility === 'public' && !c.dissolved_at,
    can_change_visibility: member && !c.dissolved_at && c.type === 'group' && !user.username.startsWith('agent:') && !!user.is_company_admin,
  };
}
