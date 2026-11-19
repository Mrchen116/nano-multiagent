import type { DatabaseSync } from 'node:sqlite';
import { classifyChatDelivery } from '@nano/product-contracts';
import { all, fail, now, one, type Row } from './context.js';

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

/** Does this exact message identify its human creator as the sender to this Agent? */
export function ownerDirect(db:DatabaseSync,agentId:string,messageId:string):boolean {
  return !!one(db,'SELECT 1 FROM owner_direct_agent_messages WHERE agent_id=? AND message_id=?',agentId,messageId);
}

/** Apply the current chat boundary while preserving a provider's earlier terminal skip. */
export function chatAllowed(db:DatabaseSync,agentId:string,messageId:string):boolean {
  const profile=one(db,'SELECT collaboration_scope FROM agent_profiles WHERE agent_id=?',agentId);
  if(!profile || storedProviderFacts(db,messageId)?.scope_skipped)return false;
  return classifyChatDelivery(profile.collaboration_scope,{ownerDirect:profile.collaboration_scope==='owner_only' && ownerDirect(db,agentId,messageId),
    directToAgent:false,addressedToAgent:false,addressedToOwner:false})!=='skip';
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

/** Retire team-only work atomically with the committed profile change. */
export function retireTeamBacklog(db:DatabaseSync,agentId:string):void {
  for(const relay of all(db,`SELECT r.* FROM relay_tasks r WHERE json_extract(r.payload_json,'$.agent_id')=?
    AND r.status IN ('queued','sent','accepted')
    AND NOT EXISTS (SELECT 1 FROM task_context_index t WHERE t.agent_id=? AND t.message_id=r.message_id)
    AND NOT EXISTS (SELECT 1 FROM owner_direct_agent_messages d WHERE d.agent_id=? AND d.message_id=r.message_id)`,agentId,agentId,agentId))cancelChatRelay(db,relay,agentId);
  db.prepare(`UPDATE pa_source_events SET state='scope_skipped' WHERE binding_id=(SELECT binding_id FROM personal_agent_bindings WHERE agent_id=?)
    AND kind IN ('message.created','message.completed') AND state IN ('pending','received')
    AND NOT EXISTS (SELECT 1 FROM owner_direct_agent_messages d WHERE d.agent_id=? AND d.message_id=pa_source_events.message_id)`).run(agentId,agentId);
}
