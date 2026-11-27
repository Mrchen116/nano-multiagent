import type { DatabaseSync } from 'node:sqlite';
import { all, one, type Row } from './context.js';
import {
  accountEnabled,
  agentAvailable,
  canAccessSpace,
  canActorAccess,
  canCollaborateWithAgent,
  canOwnerObservePersonalAgentDirect,
  currentActorCanAccess,
} from './identity.js';
import { canAgentAccessConversation, groupHasPrivateAgent, groupHasProjectAgent } from './collaboration.js';

/** Resolve account eligibility without treating personal access as company approval. */
export function qualifiedUser(db: DatabaseSync, userId: string): Row | undefined {
  const user = one(db, 'SELECT * FROM users WHERE id=?', userId);
  if (!user) return;
  if (user.username.startsWith('agent:')) {
    if (!agentAvailable(db, one(db, 'SELECT * FROM agent_profiles WHERE agent_id=?', user.username.slice(6)))) return;
  } else if (!accountEnabled(user)) return;
  return user;
}

const observerParticipants = `SELECT p.conversation_id,c.space_id conversation_space,u.id user_id,u.username,
    a.agent_id,a.owner_id,a.space_id,a.collaboration_scope,a.is_stale,b.owner_user_id pa_owner
  FROM conversation_participants p JOIN conversations c ON c.id=p.conversation_id JOIN users u ON u.id=p.user_id
  LEFT JOIN agent_profiles a ON u.username GLOB 'agent:*' AND a.agent_id=substr(u.username,7)
  LEFT JOIN personal_agent_bindings b ON b.agent_id=a.agent_id AND b.owner_id=a.owner_id`;

function observerOwners(db: DatabaseSync, participants: Row[], space: string): string[] {
  if (participants.length !== 2) return [];
  if (participants.every(p => p.owner_id && (p.space_id === space || space === `personal:${p.owner_id}`))) {
    return [...new Set(participants.map(p => p.owner_id))];
  }
  if (participants.filter(p => !p.username.startsWith('agent:')).length !== 1) return [];
  return participants
    .filter(p => p.pa_owner && agentAvailable(db, p) && (p.space_id === space || (space === 'company:default' && canOwnerObservePersonalAgentDirect(db, p))))
    .map(p => p.pa_owner);
}

function directAgentOwners(db: DatabaseSync, conversation: Row): string[] {
  if (conversation.type !== 'direct') return [];
  const participants = all(db, `${observerParticipants} WHERE p.conversation_id=?`, conversation.id);
  return observerOwners(db, participants, conversation.space_id);
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
  const agentProfile = agent ? one(db, 'SELECT * FROM agent_profiles WHERE agent_id=?', user.username.slice(6)) : undefined;
  if (agent) {
    if (!agentProfile || !agentAvailable(db, agentProfile)) return new Set();
    if (['owner_only', 'project'].includes(agentProfile.collaboration_scope ?? 'team')) {
      const joined = all(db, `SELECT c.* FROM conversations c
        JOIN conversation_participants p ON p.conversation_id=c.id
        WHERE p.user_id=?`, user.id)
        .filter(c => canAgentAccessConversation(db, agentProfile, c))
        .map(c => c.id);
      return new Set<string>(joined);
    }
  }
  const spaces = agent
    ? [...new Set(['company:default', agentProfile?.space_id, `personal:${agentProfile?.owner_id}`])]
        .filter((space): space is string => !!space && canActorAccess(db, user.id, space))
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
  const directs = new Map<string, Row[]>();
  for (const participant of participants) {
    if (readable.has(participant.conversation_id)) continue;
    const members = directs.get(participant.conversation_id);
    if (members) members.push(participant);
    else directs.set(participant.conversation_id, [participant]);
  }
  for (const [id, members] of directs) {
    if (observerOwners(db, members, members[0]!.conversation_space).includes(user.id)) readable.add(id);
  }
  return readable;
}

/** Project read and write rights from the fixed conversation and current actor. */
export function conversationAccess(db: DatabaseSync, id: string, userId: string): Row | undefined {
  const conversation = one(db, 'SELECT * FROM conversations WHERE id=?', id);
  return conversation && conversationRowAccess(db,conversation,userId);
}

/** Evaluate access using the conversation row read for this operation. */
export function conversationRowAccess(db: DatabaseSync, c: Row, userId: string): Row | undefined {
  const user = one(db, 'SELECT * FROM users WHERE id=?', userId);
  if (!user) return;
  const isAgent = user.username.startsWith('agent:');
  const member = !!one(db, 'SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?', c.id, userId);
  if (isAgent) {
    const profile = one(db, 'SELECT * FROM agent_profiles WHERE agent_id=?', user.username.slice(6));
    if (!canAgentAccessConversation(db, profile, c)) return;
    if (!member && !(c.type === 'group' && c.visibility === 'public' && (profile!.collaboration_scope ?? 'team') === 'team')) return;
    return {
      ...c,
      is_member: member,
      is_observer: false,
      can_write: member && !c.dissolved_at,
      write_blocked_reason: null,
      can_join: !member && c.type === 'group' && c.visibility === 'public' && !c.dissolved_at && (profile!.collaboration_scope ?? 'team') === 'team',
      can_change_visibility: false,
    };
  }
  if (!currentActorCanAccess(db,user,c.space_id)) return;
  const observer = !member && directAgentOwners(db,c).includes(userId);
  if (!member && !observer && !(c.type === 'group' && c.visibility === 'public')) return;
  let canWrite = member && !c.dissolved_at;
  let writeBlockedReason: string | null = null;
  if (canWrite && c.type === 'direct' && !c.external_source) {
    const peer = one(db, `SELECT ap.* FROM conversation_participants cp
      JOIN users u ON u.id=cp.user_id
      JOIN agent_profiles ap ON u.username='agent:'||ap.agent_id
      WHERE cp.conversation_id=? AND cp.user_id!=? LIMIT 1`, c.id, userId);
    if (peer && peer.owner_id !== user.owner_id) {
      const peerScope = peer.collaboration_scope ?? 'team';
      if (peerScope === 'owner_only') {
        canWrite = false;
        writeBlockedReason = 'agent_private';
      } else if (peerScope === 'project' && !canCollaborateWithAgent(db, user, peer)) {
        canWrite = false;
        writeBlockedReason = 'agent_project_restricted';
      }
    }
  }
  return {
    ...c,
    is_member: member,
    is_observer: observer,
    can_write: canWrite,
    write_blocked_reason: writeBlockedReason,
    can_join: !member && c.type === 'group' && c.visibility === 'public' && !c.dissolved_at,
    can_change_visibility: c.space_id === 'company:default' && member && !c.dissolved_at && c.type === 'group' && !!user.is_company_admin && !groupHasPrivateAgent(db, c.id) && !groupHasProjectAgent(db, c.id),
  };
}

/** Select event readers using the same current eligibility as HTTP and replay.
 *
 * Args:
 *   db: IM database containing the current ownership and membership records.
 *   id: Conversation whose persisted events are being delivered.
 *   candidates: Ready browser identities for this event, when known.
 *
 * Returns:
 *   Unique eligible member and owner user IDs; public-group visitors keep polling.
 */
export function conversationReaderIds(db: DatabaseSync, id: string, candidates?: ReadonlySet<string>): string[] {
  const c = one(db,'SELECT * FROM conversations WHERE id=?',id);
  if (!c) return [];
  const members = all(db, `SELECT u.id,u.username,u.owner_id,u.membership_status,u.personal_space_enabled
    FROM conversation_participants p JOIN users u ON u.id=p.user_id WHERE p.conversation_id=?`, id);
  const readers = new Set<string>();
  for (const member of members) {
    if (candidates && !candidates.has(member.id)) continue;
    if (member.username.startsWith('agent:')) {
      const profile = one(db, 'SELECT * FROM agent_profiles WHERE agent_id=?', member.username.slice(6));
      if (canAgentAccessConversation(db, profile, c)) readers.add(member.id);
    } else if (currentActorCanAccess(db,member,c.space_id)) {
      readers.add(member.id);
    }
  }
  for (const uid of directAgentOwners(db,c)) {
    if (readers.has(uid) || (candidates && !candidates.has(uid))) continue;
    const owner = one(db,'SELECT username,owner_id,membership_status,personal_space_enabled FROM users WHERE id=?',uid);
    if (owner && !owner.username.startsWith('agent:') && canAccessSpace(owner,c.space_id)) readers.add(uid);
  }
  return [...readers];
}
