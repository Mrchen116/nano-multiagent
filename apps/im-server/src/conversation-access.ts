import type { DatabaseSync } from 'node:sqlite';
import { all, one, type Row } from './context.js';
import { accountEnabled, agentAvailable, canAccessSpace, canActorAccess } from './identity.js';

/** Resolve account eligibility without treating personal access as company approval. */
export function qualifiedUser(db: DatabaseSync, userId: string): Row | undefined {
  const user = one(db, 'SELECT * FROM users WHERE id=?', userId);
  if (!user) return;
  if (user.username.startsWith('agent:')) {
    if (!agentAvailable(db, one(db, 'SELECT * FROM agent_profiles WHERE agent_id=?', user.username.slice(6)))) return;
  } else if (!accountEnabled(user)) return;
  return user;
}

const observerParticipants = `SELECT p.conversation_id,c.space_id conversation_space,u.id user_id,u.username,a.owner_id,a.space_id,b.owner_user_id pa_owner
  FROM conversation_participants p JOIN conversations c ON c.id=p.conversation_id JOIN users u ON u.id=p.user_id
  LEFT JOIN agent_profiles a ON u.username GLOB 'agent:*' AND a.agent_id=substr(u.username,7)
  LEFT JOIN personal_agent_bindings b ON b.agent_id=a.agent_id AND b.owner_id=a.owner_id`;

function observerOwners(participants: Row[], space: string, canRead: (id: string, space: string) => boolean): string[] {
  if (participants.length !== 2) return [];
  if (participants.every(p => p.owner_id && p.space_id === space)) return [...new Set(participants.map(p => p.owner_id))];
  if (participants.filter(p => !p.username.startsWith('agent:')).length !== 1) return [];
  return participants.filter(p => p.pa_owner && canRead(p.user_id, space)).map(p => p.pa_owner);
}

function directAgentOwners(db: DatabaseSync, conversation: Row): string[] {
  if (conversation.type !== 'direct') return [];
  const participants = all(db, `${observerParticipants} WHERE p.conversation_id=?`, conversation.id);
  return observerOwners(participants, conversation.space_id, (id, space) => canActorAccess(db, id, space));
}

/** Find chats readable by a signed-in user, including dissolved history.
 *
 * Args:
 *   db: Database holding current memberships, profiles and PA bindings.
 *   user: Authenticated account making the search request.
 * Returns:
 *   A set of chat IDs eligible before message filtering and pagination.
 */
export function readableConversationIds(db: DatabaseSync, user: Row): Set<string> {
  const agent = user.username.startsWith('agent:');
  const spaces = agent
    ? ['company:default', one(db, 'SELECT space_id FROM agent_profiles WHERE agent_id=?', user.username.slice(6))?.space_id]
        .filter(space => space && canActorAccess(db, user.id, space))
    : ['company:default', `personal:${user.owner_id}`].filter(space => canAccessSpace(user, space));
  const spaceList = JSON.stringify(spaces);
  const readable = new Set<string>(all(db, `SELECT c.id FROM conversations c
    WHERE c.space_id IN (SELECT value FROM json_each(?)) AND c.id IN (
      SELECT conversation_id FROM conversation_participants WHERE user_id=?
      UNION ALL SELECT id FROM conversations WHERE type='group' AND visibility='public')`, spaceList, user.id).map(c => c.id));
  if (agent || !spaces.length) return readable;

  // Only directs containing an owned Agent or PA can grant observation. Fetch
  // both participants so owner, pair cardinality and PA eligibility stay shared.
  const participants = all(db, `${observerParticipants} WHERE p.conversation_id IN (
    SELECT cp.conversation_id FROM conversation_participants cp JOIN conversations c ON c.id=cp.conversation_id
    WHERE c.type='direct' AND c.space_id IN (SELECT value FROM json_each(?)) AND cp.user_id IN (
      SELECT id FROM users WHERE username IN (
        SELECT 'agent:'||agent_id FROM agent_profiles WHERE owner_id=?
        UNION ALL SELECT 'agent:'||agent_id FROM personal_agent_bindings WHERE owner_user_id=?)))`, spaceList, user.id, user.id);
  const accessByActor = new Map<string, boolean>();
  const canRead = (id: string, space: string) => {
    const key = JSON.stringify([id, space]);
    if (!accessByActor.has(key)) accessByActor.set(key, canActorAccess(db, id, space));
    return accessByActor.get(key)!;
  };
  const directs = new Map<string, Row[]>();
  for (const participant of participants) {
    if (readable.has(participant.conversation_id)) continue;
    const members = directs.get(participant.conversation_id);
    if (members) members.push(participant);
    else directs.set(participant.conversation_id, [participant]);
  }
  for (const [id, members] of directs) {
    if (observerOwners(members, members[0]!.conversation_space, canRead).includes(user.id)) readable.add(id);
  }
  return readable;
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
