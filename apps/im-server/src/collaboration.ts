import type { DatabaseSync } from 'node:sqlite';
import { classifyChatDelivery, type ChatMessage } from '@nano/product-contracts';
import { all, fail, now, one, type ImContext, type Row } from './context.js';
import { agentAvailable, canCollaborateWithAgent, ownerAccount } from './identity.js';
import { captureTaskContextAccess, revokeLostTaskContextAccess } from './task-context-access.js';
import { discardThreadUnread } from './threads.js';

/** Target facts from the channel's authenticated original-event mirror. */
export interface ProviderFacts {
  source_time:string|null;
  mentioned_bot:boolean;
  mentioned_owner:boolean;
  replied_to_bot:boolean;
  replied_to_owner:boolean;
  context_only:boolean;
  scope_skipped:boolean;
}

/** Validate the small projection accepted from a verified Gateway. */
export function providerFacts(value:ProviderFacts|undefined):ProviderFacts|undefined {
  if(value===undefined)return;
  const flags=['mentioned_bot','mentioned_owner','replied_to_bot','replied_to_owner','context_only','scope_skipped'] as const;
  if(!value || (value.source_time!==null && (typeof value.source_time!=='string'||!Number.isFinite(Date.parse(value.source_time)))) ||
     flags.some(key=>typeof value[key]!=='boolean'))fail(422,'invalid_provider_facts');
  return {source_time:value.source_time,mentioned_bot:value.mentioned_bot,mentioned_owner:value.mentioned_owner,replied_to_bot:value.replied_to_bot,
    replied_to_owner:value.replied_to_owner,context_only:value.context_only,scope_skipped:value.scope_skipped};
}

/** Read authenticated mirror metadata independently of displayed chat timestamps. */
export function storedProviderFacts(db:DatabaseSync,messageId:string):ProviderFacts|undefined {
  const row=one(db,'SELECT facts_json FROM provider_message_facts WHERE message_id=?',messageId);
  return row?JSON.parse(row.facts_json):undefined;
}

/** Does this exact message identify its human creator as the 1:1 sender to this Agent? */
export function ownerDirect(db:DatabaseSync,agentId:string,messageId:string):boolean {
  return !!one(db,'SELECT 1 FROM owner_direct_agent_messages WHERE agent_id=? AND message_id=?',agentId,messageId);
}

/** Check whether a native IM conversation contains exclusively the given owner and that owner's non-stale Agents.
 *
 * Args:
 *   db: Center business database.
 *   conversationId: Native conversation ID to evaluate.
 *   ownerId: Owner identity (`users.owner_id` / `agent_profiles.owner_id`).
 * Returns:
 *   True when the conversation is native, non-public, has at least one participant,
 *   and every participant belongs to `ownerId`.
 */
export function isOwnerInternalConversation(db:DatabaseSync,conversationId:string,ownerId:string):boolean {
  const chat=one(db,'SELECT id,external_source,visibility FROM conversations WHERE id=?',conversationId);
  if(!chat || chat.external_source || chat.visibility==='public')return false;
  const participants=all(db,`SELECT u.id,u.username,u.owner_id AS user_owner_id,a.agent_id,a.owner_id AS agent_owner_id,a.is_stale
    FROM conversation_participants p
    JOIN users u ON u.id=p.user_id
    LEFT JOIN agent_profiles a ON u.username GLOB 'agent:*' AND a.agent_id=substr(u.username,7)
    WHERE p.conversation_id=?`,conversationId);
  if(!participants.length)return false;
  return participants.every(member=>{
    if(member.username.startsWith('agent:'))return !!member.agent_id && !member.is_stale && member.agent_owner_id===ownerId;
    if(member.username.startsWith('shadow:') || member.username==='system')return false;
    return member.user_owner_id===ownerId;
  });
}

/** Check whether an external shadow conversation is the bound human owner's 1:1 DM for this Agent. */
export function isFeishuBoundOwnerShadow(db:DatabaseSync,conversation:Row|undefined,profile:Row|undefined):boolean {
  if(!conversation || !profile || conversation.type!=='direct' || conversation.config_agent_id!==profile.agent_id)return false;
  if(conversation.external_source==='feishu') {
    return !!one(db,`SELECT 1 FROM agent_channels ch
      WHERE ch.agent_id=? AND ch.node_id=? AND ch.owner_id=? AND ch.provider='feishu' AND ch.enabled=1
        AND coalesce(json_extract(ch.provider_runtime_json,'$.owner_open_id'),'')!=''
        AND ?='feishu:'||json_extract(ch.config_json,'$.app_id')||':dm:'||json_extract(ch.provider_runtime_json,'$.owner_open_id')`,
      profile.agent_id,profile.node_id,profile.owner_id,conversation.external_chat_id);
  }
  if(conversation.external_source==='wechat') {
    return !!one(db,`SELECT 1 FROM agent_channels ch
      WHERE ch.agent_id=? AND ch.node_id=? AND ch.owner_id=? AND ch.provider='wechat' AND ch.enabled=1
        AND coalesce(json_extract(ch.config_json,'$.owner_user_id'),'')!=''
        AND ?='wechat:'||json_extract(ch.config_json,'$.bot_id')||':dm:'||json_extract(ch.config_json,'$.owner_user_id')`,
      profile.agent_id,profile.node_id,profile.owner_id,conversation.external_chat_id);
  }
  return false;
}

/** Check whether a native IM conversation contains exclusively the given owner and that owner's `owner_only` Agents.
 *
 * Args:
 *   db: Center business database.
 *   conversationId: Native conversation ID to evaluate.
 *   ownerId: Owner identity (`users.owner_id` / `agent_profiles.owner_id`).
 *   senderAgentId: Optional authenticated PA `agent_id` whose own membership does not widen exposure.
 * Returns:
 *   True when the conversation is native, non-public, has at least one participant,
 *   and every participant is either the owner, `senderAgentId`, or a non-stale `owner_only` Agent of `ownerId`.
 */
export function isPureOwnerPrivateConversation(
  db:DatabaseSync,
  conversationId:string,
  ownerId:string,
  senderAgentId?:string,
):boolean {
  const chat=one(db,'SELECT id,external_source,visibility FROM conversations WHERE id=?',conversationId);
  if(!chat || chat.external_source || chat.visibility==='public')return false;
  const participants=all(db,`SELECT u.id,u.username,u.owner_id AS user_owner_id,a.agent_id,a.owner_id AS agent_owner_id,a.collaboration_scope,a.is_stale
    FROM conversation_participants p
    JOIN users u ON u.id=p.user_id
    LEFT JOIN agent_profiles a ON u.username GLOB 'agent:*' AND a.agent_id=substr(u.username,7)
    WHERE p.conversation_id=?`,conversationId);
  if(!participants.length)return false;
  return participants.every(member=>{
    if(member.username.startsWith('agent:')) {
      return !!member.agent_id && !member.is_stale && member.agent_owner_id===ownerId
        && (member.agent_id===senderAgentId || (member.collaboration_scope ?? 'team')==='owner_only');
    }
    if(member.username.startsWith('shadow:') || member.username==='system')return false;
    return member.user_owner_id===ownerId;
  });
}

/** Check whether an Agent may read or write a conversation under its current collaboration scope and space rules. */
export function canAgentAccessConversation(db:DatabaseSync,profile:Row|undefined,conversation:Row|undefined):boolean {
  if(!profile || profile.is_stale || !agentAvailable(db,profile) || !conversation)return false;
  const scope = profile.collaboration_scope ?? 'team';
  if(scope==='owner_only') {
    return isOwnerInternalConversation(db,conversation.id,profile.owner_id) || isFeishuBoundOwnerShadow(db,conversation,profile);
  }
  const owner=ownerAccount(db,profile.owner_id);
  const spaceOk = profile.space_id===conversation.space_id
    || (conversation.space_id==='company:default' && owner?.membership_status==='active')
    || (conversation.space_id===`personal:${profile.owner_id}` && !!owner?.personal_space_enabled);
  if(!spaceOk)return false;
  if(scope==='project') {
    if(conversation.external_source)return isFeishuBoundOwnerShadow(db,conversation,profile);
    if(conversation.visibility==='public')return false;
    if(isOwnerInternalConversation(db,conversation.id,profile.owner_id))return true;
    const agentUser=one(db,'SELECT * FROM users WHERE username=?',`agent:${profile.agent_id}`);
    if(!agentUser || !one(db,'SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?',conversation.id,agentUser.id))return false;
    if(conversation.type==='group')return conversation.visibility==='private';
    if(conversation.type==='direct') {
      const peer=one(db,`SELECT u.* FROM conversation_participants cp JOIN users u ON u.id=cp.user_id
        WHERE cp.conversation_id=? AND cp.user_id!=? LIMIT 1`,conversation.id,agentUser.id);
      if(!peer)return false;
      const peerProfile=peer.username.startsWith('agent:')
        ? one(db,'SELECT * FROM agent_profiles WHERE agent_id=?',peer.username.slice(6))
        : undefined;
      const peerOwnerId=peerProfile ? peerProfile.owner_id : peer.owner_id;
      if(peerOwnerId===profile.owner_id)return peerProfile ? !peerProfile.is_stale && agentAvailable(db,peerProfile) : true;
      if(peerProfile)return canCollaborateWithAgent(db,peer,profile) && canCollaborateWithAgent(db,agentUser,peerProfile);
      return canCollaborateWithAgent(db,peer,profile);
    }
    return false;
  }
  return true;
}

/** Check whether a group conversation currently contains any `owner_only` Agent participant. */
export function groupHasPrivateAgent(db:DatabaseSync,conversationId:string):boolean {
  return !!one(db,`SELECT 1 FROM conversation_participants p
    JOIN users u ON u.id=p.user_id
    JOIN agent_profiles a ON u.username='agent:'||a.agent_id
    WHERE p.conversation_id=? AND a.is_stale=0 AND a.collaboration_scope='owner_only' LIMIT 1`,conversationId);
}

/** Check whether a group conversation currently contains any `project` Agent participant. */
export function groupHasProjectAgent(db:DatabaseSync,conversationId:string):boolean {
  return !!one(db,`SELECT 1 FROM conversation_participants p
    JOIN users u ON u.id=p.user_id
    JOIN agent_profiles a ON u.username='agent:'||a.agent_id
    WHERE p.conversation_id=? AND a.is_stale=0 AND a.collaboration_scope='project' LIMIT 1`,conversationId);
}

/** Apply the current chat boundary while preserving a provider's earlier terminal skip. */
export function chatAllowed(db:DatabaseSync,agentId:string,messageId:string):boolean {
  const profile=one(db,'SELECT * FROM agent_profiles WHERE agent_id=?',agentId);
  if(!profile || storedProviderFacts(db,messageId)?.scope_skipped)return false;
  const scope = profile.collaboration_scope ?? 'team';
  if(scope==='team')return true;
  const message=one(db,'SELECT conversation_id FROM messages WHERE id=?',messageId);
  const chat=message ? one(db,'SELECT * FROM conversations WHERE id=?',message.conversation_id) : undefined;
  return classifyChatDelivery(scope,{
    ownerDirect:ownerDirect(db,agentId,messageId),
    ownerInternal:!!message && isOwnerInternalConversation(db,message.conversation_id,profile.owner_id),
    projectAllowed:scope==='project' && !!chat && !chat.external_source && canAgentAccessConversation(db,profile,chat),
    directToAgent:false,addressedToAgent:false,addressedToOwner:false,
  })!=='skip';
}

/** A skipped recipient has no pending or fabricated delivery evidence. */
export function cancelChatRelay(db:DatabaseSync,relay:Row,agentId:string,nodeConfirmed=false):void {
  if(['completed','failed'].includes(relay.status))return;
  db.prepare("UPDATE relay_tasks SET status='cancelled',receipt_status=?,receipt_detail='collaboration_scope',updated_at=? WHERE relay_task_id=?")
    .run(nodeConfirmed?'skipped':relay.receipt_status,now(),relay.relay_task_id);
  db.prepare("DELETE FROM message_receipts WHERE message_id=? AND recipient_id=(SELECT id FROM users WHERE username=?) AND status=0")
    .run(relay.message_id,'agent:'+agentId);
  db.prepare("UPDATE messages SET delivery_status='completed' WHERE id=? AND delivery_status='pending' AND NOT EXISTS (SELECT 1 FROM relay_tasks WHERE message_id=? AND status!='cancelled')")
    .run(relay.message_id,relay.message_id);
}

/** Retire non-owner-internal chat relays atomically with the committed profile change while preserving PA owner observation. */
export function retireTeamBacklog(db:DatabaseSync,agentId:string):void {
  const profile=one(db,'SELECT * FROM agent_profiles WHERE agent_id=?',agentId);
  if(!profile)return;
  for(const relay of all(db,`SELECT r.* FROM relay_tasks r WHERE json_extract(r.payload_json,'$.agent_id')=?
    AND r.status IN ('queued','sent','accepted')
    AND NOT EXISTS (SELECT 1 FROM task_context_index t WHERE t.agent_id=? AND t.message_id=r.message_id)
    AND NOT EXISTS (SELECT 1 FROM owner_direct_agent_messages d WHERE d.agent_id=? AND d.message_id=r.message_id)`,agentId,agentId,agentId)) {
    if(isOwnerInternalConversation(db,relay.conversation_id,profile.owner_id))continue;
    cancelChatRelay(db,relay,agentId);
  }
  const binding=one(db,'SELECT binding_id FROM personal_agent_bindings WHERE agent_id=?',agentId);
  if(binding) {
    for(const ev of all(db,`SELECT e.event_id,c.* FROM pa_source_events e
      JOIN conversations c ON c.id=e.conversation_id
      WHERE e.binding_id=? AND e.kind IN ('message.created','message.completed') AND e.state IN ('pending','received')
        AND c.external_source IS NOT NULL AND c.config_agent_id=?`,binding.binding_id,agentId)) {
      if(!isFeishuBoundOwnerShadow(db,ev,profile)) {
        db.prepare("UPDATE pa_source_events SET state='scope_skipped' WHERE event_id=?").run(ev.event_id);
      }
    }
  }
}

export interface ScopeTransitionEffects {
  notices: ChatMessage[];
  membershipBroadcasts: Array<{ conversationId: string; recipients: string[] }>;
  revokedConversationIds: string[];
  discardedEvents: Array<{ conversationId: string; messageId: string; kind: 'discarded' | 'completed'; payload: Row }>;
}

function cleanupRevokedConversationsInTx(
  db: DatabaseSync,
  agentId: string,
  agentUserId: string,
  cleanupConvIds: readonly string[],
  effects: ScopeTransitionEffects,
): void {
  for (const cid of cleanupConvIds) {
    const inFlight = all(db, `SELECT * FROM messages WHERE conversation_id=? AND sender_user_id=?
      AND (delivery_status='running' OR awaiting_permission_at IS NOT NULL)`, cid, agentUserId);
    for (const msg of inFlight) {
      const permissions = JSON.parse(msg.permission_request_json ?? '[]').map((perm: Row) =>
        ['pending', 'submitted'].includes(perm.status) ? { ...perm, status: 'invalidated', reason: 'collaboration_scope_restricted' } : perm);
      const hasVisibleContent = Boolean(String(msg.content ?? '').trim()) || JSON.parse(msg.attachments_json ?? '[]').length > 0;
      if (!hasVisibleContent && msg.delivery_status === 'running') {
        if (msg.thread_root_id) {
          discardThreadUnread(db, cid, msg.thread_root_id, msg.id);
          db.prepare('DELETE FROM messages WHERE id=?').run(msg.id);
        } else {
          db.prepare('DELETE FROM messages WHERE id=?').run(msg.id);
          const latest = one(db, 'SELECT content,attachments_json,created_at FROM messages WHERE conversation_id=? AND thread_root_id IS NULL ORDER BY rowid DESC LIMIT 1', cid);
          const preview = latest ? String(latest.content ?? '').trim().slice(0, 120) || JSON.parse(latest.attachments_json ?? '[]')[0]?.file_name || '' : null;
          db.prepare('UPDATE conversations SET last_message_preview=?,last_message_at=? WHERE id=?').run(preview, latest?.created_at ?? null, cid);
        }
        effects.discardedEvents.push({
          conversationId: cid,
          messageId: msg.id,
          kind: 'discarded',
          payload: { message_id: msg.id, reason: 'collaboration_scope_restricted', ...(msg.thread_root_id ? { thread_root_message_id: msg.thread_root_id } : {}) },
        });
      } else {
        db.prepare("UPDATE messages SET delivery_status='failed',awaiting_permission_at=NULL,permission_request_json=? WHERE id=?")
          .run(JSON.stringify(permissions), msg.id);
        effects.discardedEvents.push({ conversationId: cid, messageId: msg.id, kind: 'completed', payload: { interruption_reason: 'collaboration_scope_restricted' } });
      }
    }
    for (const relay of all(db, `SELECT r.* FROM relay_tasks r WHERE r.conversation_id=?
      AND json_extract(r.payload_json,'$.agent_id')=?
      AND r.status IN ('queued','sent','accepted')
      AND NOT EXISTS (SELECT 1 FROM task_context_index t WHERE t.agent_id=? AND t.message_id=r.message_id)
      AND NOT EXISTS (SELECT 1 FROM owner_direct_agent_messages d WHERE d.agent_id=? AND d.message_id=r.message_id)`,
      cid, agentId, agentId, agentId)) {
      cancelChatRelay(db, relay, agentId);
    }
  }
}

/** Execute transactional cleanup when an Agent's collaboration scope changes (`team <-> project <-> owner_only`). */
export function applyCollaborationScopeTransitionInTx(
  db: DatabaseSync,
  agentId: string,
  previousScope: string | undefined,
  nextScope: string | undefined,
  actorUserId: string,
  beforeTaskAccess?: readonly { agent_id: string; conversation_id: string }[],
): ScopeTransitionEffects {
  const prev = previousScope ?? 'team';
  const next = nextScope ?? 'team';
  const effects: ScopeTransitionEffects = { notices: [], membershipBroadcasts: [], revokedConversationIds: [], discardedEvents: [] };
  if (prev === next) return effects;
  let profile = one(db, 'SELECT * FROM agent_profiles WHERE agent_id=?', agentId);
  const agentUser = one(db, 'SELECT * FROM users WHERE username=?', `agent:${agentId}`);
  if (!profile || !agentUser) return effects;

  if (next === 'owner_only' || (prev === 'team' && next === 'project')) {
    const before = beforeTaskAccess ?? captureTaskContextAccess(db, { agentIds: [agentId] });
    if (profile.collaboration_scope !== next) {
      db.prepare('UPDATE agent_profiles SET collaboration_scope=? WHERE agent_id=?').run(next, agentId);
      profile = one(db, 'SELECT * FROM agent_profiles WHERE agent_id=?', agentId)!;
    }
    const joined = all(db, `SELECT c.* FROM conversations c
      JOIN conversation_participants p ON p.conversation_id=c.id
      WHERE p.user_id=? AND c.dissolved_at IS NULL`, agentUser.id);
    const exitGroups = joined.filter(c => c.type === 'group' && !c.external_source && !isOwnerInternalConversation(db, c.id, profile!.owner_id)
      && (next === 'owner_only' || c.visibility === 'public'));
    const frozenDirects = joined.filter(c => c.type === 'direct' && !c.external_source && !isOwnerInternalConversation(db, c.id, profile!.owner_id)
      && (next === 'owner_only' || !canAgentAccessConversation(db, profile, c)));
    const externalShadows = all(db, `SELECT * FROM conversations WHERE external_source IS NOT NULL AND config_agent_id=?`, agentId)
      .filter(c => !isFeishuBoundOwnerShadow(db, c, profile));

    if (exitGroups.length) {
      const groupIds = exitGroups.map(c => c.id);
      const recipientsByGroup = new Map<string, string[]>();
      for (const gid of groupIds) {
        recipientsByGroup.set(gid, all(db, 'SELECT user_id FROM conversation_participants WHERE conversation_id=?', gid).map(r => r.user_id));
      }
      for (const gid of groupIds) {
        db.prepare('DELETE FROM conversation_participants WHERE conversation_id=? AND user_id=?').run(gid, agentUser.id);
        db.prepare('DELETE FROM thread_follows WHERE conversation_id=? AND user_id=?').run(gid, agentUser.id);
        effects.membershipBroadcasts.push({ conversationId: gid, recipients: recipientsByGroup.get(gid) ?? [] });
      }
    }
    if (before.length) {
      effects.notices.push(...revokeLostTaskContextAccess(db, before, actorUserId));
    }

    for (const d of frozenDirects) {
      const recipients = all(db, 'SELECT user_id FROM conversation_participants WHERE conversation_id=?', d.id).map(r => r.user_id);
      effects.membershipBroadcasts.push({ conversationId: d.id, recipients });
    }

    const cleanupConvIds = [...new Set([...exitGroups.map(c => c.id), ...frozenDirects.map(c => c.id), ...externalShadows.map(c => c.id)])];
    effects.revokedConversationIds.push(...cleanupConvIds);
    cleanupRevokedConversationsInTx(db, agentId, agentUser.id, cleanupConvIds, effects);

    if (next === 'owner_only') {
      retireTeamBacklog(db, agentId);
    }
  } else if (next === 'team' || (prev === 'owner_only' && next === 'project')) {
    if (profile.collaboration_scope !== next) {
      db.prepare('UPDATE agent_profiles SET collaboration_scope=? WHERE agent_id=?').run(next, agentId);
      profile = one(db, 'SELECT * FROM agent_profiles WHERE agent_id=?', agentId)!;
    }
    const restoredDirects = all(db, `SELECT c.* FROM conversations c
      JOIN conversation_participants p ON p.conversation_id=c.id
      WHERE p.user_id=? AND c.type='direct' AND c.external_source IS NULL AND c.dissolved_at IS NULL`, agentUser.id)
      .filter(c => !isOwnerInternalConversation(db, c.id, profile!.owner_id) && canAgentAccessConversation(db, profile, c));
    for (const d of restoredDirects) {
      const recipients = all(db, 'SELECT user_id FROM conversation_participants WHERE conversation_id=?', d.id).map(r => r.user_id);
      effects.membershipBroadcasts.push({ conversationId: d.id, recipients });
    }
  }

  return effects;
}

/** Snapshot currently accessible external 1:1 directs for `project` Agents in a private group before removing a member or dissolving the group. */
export function snapshotProjectGroupDirects(db: DatabaseSync, groupId: string): {
  projectAgentIds: string[];
  accessibleDirectsByAgent: Map<string, string[]>;
  allDirectConversationIds: string[];
} {
  const projectAgents = all(db, `SELECT ap.*, u.id AS agent_user_id FROM conversation_participants cp
    JOIN users u ON u.id=cp.user_id
    JOIN agent_profiles ap ON u.username='agent:'||ap.agent_id
    WHERE cp.conversation_id=? AND ap.is_stale=0 AND ap.collaboration_scope='project'`, groupId);
  const accessibleDirectsByAgent = new Map<string, string[]>();
  const allDirectSet = new Set<string>();
  for (const agent of projectAgents) {
    const directs = all(db, `SELECT c.* FROM conversations c
      JOIN conversation_participants p ON p.conversation_id=c.id
      WHERE p.user_id=? AND c.type='direct' AND c.external_source IS NULL AND c.dissolved_at IS NULL`, agent.agent_user_id)
      .filter(c => !isOwnerInternalConversation(db, c.id, agent.owner_id) && canAgentAccessConversation(db, agent, c));
    accessibleDirectsByAgent.set(agent.agent_id, directs.map(d => d.id));
    for (const d of directs) allDirectSet.add(d.id);
  }
  return {
    projectAgentIds: projectAgents.map(a => a.agent_id),
    accessibleDirectsByAgent,
    allDirectConversationIds: [...allDirectSet],
  };
}

/** Reconcile newly frozen 1:1 directs and exited group state for `project` Agents after a private-group participant removal or dissolution. */
export function reconcileProjectGroupLossInTx(
  db: DatabaseSync,
  groupId: string,
  snapshot: ReturnType<typeof snapshotProjectGroupDirects>,
  removedAgentId?: string,
): Map<string, ScopeTransitionEffects> {
  const byAgent = new Map<string, ScopeTransitionEffects>();
  const ensureEffects = (agentId: string): ScopeTransitionEffects => {
    let eff = byAgent.get(agentId);
    if (!eff) {
      eff = { notices: [], membershipBroadcasts: [], revokedConversationIds: [], discardedEvents: [] };
      byAgent.set(agentId, eff);
    }
    return eff;
  };
  for (const agentId of snapshot.projectAgentIds) {
    const profile = one(db, 'SELECT * FROM agent_profiles WHERE agent_id=?', agentId);
    const agentUser = one(db, 'SELECT * FROM users WHERE username=?', `agent:${agentId}`);
    if (!profile || !agentUser) continue;
    const lostDirectIds = (snapshot.accessibleDirectsByAgent.get(agentId) ?? []).filter(cid => {
      const conv = one(db, 'SELECT * FROM conversations WHERE id=?', cid);
      return !canAgentAccessConversation(db, profile, conv);
    });
    const cleanupIds = [...lostDirectIds, ...(removedAgentId === agentId ? [groupId] : [])];
    if (!cleanupIds.length) continue;
    const eff = ensureEffects(agentId);
    for (const cid of lostDirectIds) {
      const recipients = all(db, 'SELECT user_id FROM conversation_participants WHERE conversation_id=?', cid).map(r => r.user_id);
      eff.membershipBroadcasts.push({ conversationId: cid, recipients });
    }
    eff.revokedConversationIds.push(...cleanupIds);
    cleanupRevokedConversationsInTx(db, agentId, agentUser.id, cleanupIds, eff);
  }
  if (removedAgentId && !byAgent.has(removedAgentId)) {
    const agentUser = one(db, 'SELECT * FROM users WHERE username=?', `agent:${removedAgentId}`);
    if (agentUser) {
      const eff = ensureEffects(removedAgentId);
      eff.revokedConversationIds.push(groupId);
      cleanupRevokedConversationsInTx(db, removedAgentId, agentUser.id, [groupId], eff);
    }
  }
  return byAgent;
}

/** Publish post-commit notifications and node scope revocations after `applyCollaborationScopeTransitionInTx`. */
export function publishCollaborationScopeTransitionEffects(
  ctx: ImContext,
  agentId: string,
  operationId: string,
  effects: ScopeTransitionEffects,
): void {
  for (const ev of effects.discardedEvents) {
    if (ev.kind === 'discarded') {
      ctx.messaging?.event(ev.conversationId, null, 'message.discarded', ev.payload, 'completed');
    } else {
      const current = one(ctx.db, 'SELECT 1 FROM messages WHERE id=?', ev.messageId) ? ctx.messaging?.message(ev.messageId) : {};
      ctx.messaging?.event(ev.conversationId, ev.messageId, 'message.completed', { ...current, ...ev.payload }, 'failed');
    }
  }
  if (effects.notices.length) ctx.messaging?.publishMessages(effects.notices);
  for (const item of effects.membershipBroadcasts) {
    ctx.messaging?.membership(item.conversationId, item.recipients);
  }
  if (effects.revokedConversationIds.length) {
    const profile = one(ctx.db, 'SELECT node_id FROM agent_profiles WHERE agent_id=?', agentId);
    if (profile?.node_id) {
      ctx.gateway?.send(profile.node_id, {
        type: 'agent.scope.revoked',
        payload: { agent_id: agentId, conversation_ids: effects.revokedConversationIds, operation_id: operationId },
      });
    }
  }
  ctx.gateway?.trajectory?.check();
}
