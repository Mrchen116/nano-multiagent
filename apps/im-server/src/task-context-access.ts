import { randomUUID } from 'node:crypto';
import type { DatabaseSync } from 'node:sqlite';
import type { ChatMessage } from '@nano/product-contracts';
import { all, now, one, type Row } from './context.js';
import { conversationAccess } from './conversation-access.js';
import { agentAvailable } from './identity.js';

interface TaskSource {agent_id:string;conversation_id:string}
interface Scope {agentIds?:readonly string[];conversationIds?:readonly string[]}
const withdrawal = '任务处理资格已撤销；此通知不授予读取原聊天或继续原任务的权限。';

/** Resolve the PA's existing owner/Agent access union without granting historical membership.
 * Args:
 *   db: Center authority database.
 *   binding: Current personal binding.
 *   conversationId: Original source, not a caller-selected replacement destination.
 *   mode: Reading a source and writing to it remain separate permissions.
 * Returns:
 *   One currently authorized route, or undefined if both routes have lost access.
 */
export function personalSourceAccess(db:DatabaseSync,binding:Row,conversationId:string,mode:'read'|'write'='read'):Row|undefined {
  const owner=conversationAccess(db,conversationId,binding.owner_user_id);
  const agentUser=one(db,"SELECT id FROM users WHERE username='agent:'||?",binding.agent_id);
  const agent=agentUser&&conversationAccess(db,conversationId,agentUser.id);
  const participated=one(db,'SELECT 1 FROM conversation_participation_history WHERE conversation_id=? AND user_id=?',conversationId,binding.owner_user_id);
  return [owner&&participated?owner:undefined,agent].find(access=>access&&(mode==='read'||access.can_write));
}

/** Check pending Task handling, not permission to retain already consumed chat history.
 * Args:
 *   db: Current authoritative membership, binding, policy and lifecycle state.
 *   agentId: Recipient Agent identity.
 *   conversationId: Fixed original source.
 * Returns:
 *   Whether a full unconsumed Task original can enter the next model step.
 */
export function taskContextEligible(db:DatabaseSync,agentId:string,conversationId:string):boolean {
  const profile=one(db,'SELECT * FROM agent_profiles WHERE agent_id=?',agentId);
  if(!agentAvailable(db,profile)||one(db,'SELECT desired FROM agent_lifecycle WHERE agent_id=?',agentId)?.desired!=='enabled')return false;
  const conversation=one(db,'SELECT dissolved_at FROM conversations WHERE id=?',conversationId);
  if(!conversation||conversation.dissolved_at)return false;
  const binding=one(db,'SELECT * FROM personal_agent_bindings WHERE agent_id=?',agentId);
  if(binding) {
    const node=one(db,'SELECT * FROM node_binding_state WHERE node_id=?',binding.node_id);
    const policy=one(db,'SELECT excluded_json FROM pa_policies WHERE binding_id=?',binding.binding_id);
    return binding.status==='active'&&binding.owner_id===profile!.owner_id&&binding.node_id===profile!.node_id
      &&node?.owner_id===binding.owner_id&&node?.node_epoch===binding.node_epoch&&!!policy
      &&!JSON.parse(policy.excluded_json).includes(conversationId)&&!!personalSourceAccess(db,binding,conversationId);
  }
  const actor=one(db,"SELECT id FROM users WHERE username='agent:'||?",agentId);
  return !!actor&&!!conversationAccess(db,conversationId,actor.id)?.can_write;
}

/** Keep a prior withdrawal terminal even when access is later restored.
 * Args:
 *   db: Current authority, including revocations committed after a fixed sync cut.
 *   entry: The original full index reference being revalidated.
 * Returns:
 *   Whether the original may still be consumed; consumed history is never modified.
 */
export function taskContextEntryAllowed(db:DatabaseSync,entry:Row):boolean {
  return taskContextEligible(db,entry.agent_id,entry.conversation_id)
    &&!one(db,"SELECT 1 FROM task_context_index WHERE agent_id=? AND conversation_id=? AND projection_kind='revoked' AND seq>? LIMIT 1",entry.agent_id,entry.conversation_id,entry.seq);
}

/** Capture only currently eligible Task sources before an authoritative mutation.
 * Args:
 *   db: The database inside the caller's mutation transaction.
 *   scope: Optional affected identities or conversations; omitted means all indexed sources.
 * Returns:
 *   Eligible source identities with an unwithdrawn full reference, never message bodies.
 * Raises:
 *   Error: If called outside the authority mutation transaction.
 */
export function captureTaskContextAccess(db:DatabaseSync,scope:Scope={}):TaskSource[] {
  if(!db.isTransaction)throw new Error('Task revocation capture must share the authority transaction');
  const filters:string[]=[],values:string[]=[];
  for(const [column,ids] of [['agent_id',scope.agentIds],['conversation_id',scope.conversationIds]] as const)if(ids) {
    if(!ids.length)return [];
    filters.push(`i.${column} IN (${ids.map(()=>'?').join(',')})`);values.push(...ids);
  }
  return all(db,`SELECT DISTINCT i.agent_id,i.conversation_id FROM task_context_index i WHERE i.projection_kind='full'
    ${filters.length?'AND '+filters.join(' AND '):''}
    AND NOT EXISTS (SELECT 1 FROM task_context_index r WHERE r.agent_id=i.agent_id AND r.conversation_id=i.conversation_id AND r.projection_kind='revoked' AND r.seq>i.seq)`,...values)
    .filter(row=>taskContextEligible(db,row.agent_id,row.conversation_id)) as TaskSource[];
}

/** Project the new minimal original without reading an inaccessible/deleted conversation.
 * Args:
 *   db: Center database retaining only structured withdrawal facts.
 *   messageId: Identity shared with the visible system message when its chat still exists.
 * Returns:
 *   The same minimal message after restart or a Direct hard-delete, if it exists.
 */
export function taskContextRevocation(db:DatabaseSync,messageId:string):ChatMessage|undefined {
  const fact=one(db,'SELECT * FROM task_context_revocations WHERE message_id=?',messageId);
  if(!fact)return;
  return {id:fact.message_id,conversation_id:fact.conversation_id,sender_user_id:fact.sender_user_id,sender_type:'system',lifecycle_revision:null,
    content:withdrawal,delivery_status:'completed',created_at:fact.created_at,timezone:null,elapsed_ms:null,kernel_message_id:null,
    sender:{type:'system',id:fact.actor_id,user_id:fact.sender_user_id,display_name:'',is_stale:null},
    attachments:[],tool_calls:[],thinking:[],background_returns:[],reply_process:[],permission_requests:[],token_usage:null,interaction_reply:null,
    system_notice:{kind:'task_graph',change_kinds:['access_revoked'],attention_actor_ids:[],actor:{type:fact.actor_type,id:fact.actor_id},event_time:fact.created_at}};
}

/** Persist actual access losses in the same transaction as their authority change.
 * Args:
 *   db: Database with the caller's transaction already open.
 *   before: Eligible sources captured before the mutation, not all historical sources.
 *   actorUserId: Persisted authenticated operator, also used by the visible chat original.
 *   actorType: Operator provenance; withdrawal never confers human tool authorization.
 * Returns:
 *   Minimal originals whose chats still exist, for optional post-commit publication.
 * Raises:
 *   Error: If called outside the authority mutation transaction.
 */
export function revokeLostTaskContextAccess(db:DatabaseSync,before:readonly TaskSource[],actorUserId:string,actorType='user'):ChatMessage[] {
  if(!db.isTransaction)throw new Error('Task revocation must share the authority transaction');
  const lost=before.filter(source=>!taskContextEligible(db,source.agent_id,source.conversation_id));
  const messages:ChatMessage[]=[];
  for(const conversationId of new Set(lost.map(source=>source.conversation_id))) {
    const id=randomUUID().replaceAll('-',''),at=now();
    db.prepare('INSERT INTO task_context_revocations VALUES(?,?,?,?,?,?)').run(id,conversationId,actorUserId,actorType,actorUserId,at);
    const message=taskContextRevocation(db,id)!;
    const conversation=one(db,'SELECT type,dissolved_at FROM conversations WHERE id=?',conversationId);
    if(conversation) {
      // This is a new restricted business original, not an archive of the withdrawn Task body.
      db.prepare("INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,attachments_json,delivery_status,created_at,system_notice_json) VALUES(?,?,?,'system',?,'[]','completed',?,?)")
        .run(id,conversationId,actorUserId,withdrawal,at,JSON.stringify(message.system_notice));
      db.prepare('UPDATE conversations SET last_message_preview=?,last_message_at=? WHERE id=?').run(withdrawal,at,conversationId);
      db.prepare('UPDATE conversation_participants SET unread_count=unread_count+1 WHERE conversation_id=? AND user_id!=?').run(conversationId,actorUserId);
      db.prepare("INSERT INTO conversation_events(conversation_id,message_id,event_type,delivery_status,payload_json,created_at) VALUES(?,?,'message.created','completed',?,?)")
        .run(conversationId,id,JSON.stringify({...message,message_id:id}),at);
      messages.push(message);
    }
    for(const source of lost.filter(source=>source.conversation_id===conversationId)) {
      db.prepare("INSERT INTO task_context_index(agent_id,message_id,conversation_id,projection_kind) VALUES(?,?,?,'revoked')").run(source.agent_id,id,conversationId);
      // Existing relay rows reference live chats; the index is the durable fallback after hard deletion.
      const profile=one(db,'SELECT node_id FROM agent_profiles WHERE agent_id=?',source.agent_id);
      if(!conversation||conversation.dissolved_at||!profile?.node_id)continue;
      const relayId=randomUUID().replaceAll('-',''),key=id+':'+source.agent_id;
      const payload={agent_id:source.agent_id,conversation_id:conversationId,relay_task_id:relayId,idempotency_key:key,
        lifecycle_revision:one(db,'SELECT revision FROM agent_lifecycle WHERE agent_id=?',source.agent_id)!.revision,
        message,sender:message.sender,participants:[],metadata:{conversation_type:conversation.type,mentioned_agent_ids:[source.agent_id],participant_agent_ids:[source.agent_id],
          task_context:true,context_only:true,node_epoch:one(db,'SELECT node_epoch FROM node_binding_state WHERE node_id=?',profile.node_id)?.node_epoch??0}};
      db.prepare("INSERT INTO relay_tasks(relay_task_id,message_id,conversation_id,target_node_id,payload_json,idempotency_key,status,created_at,updated_at) VALUES(?,?,?,?,?,?,'queued',?,?)")
        .run(relayId,id,conversationId,profile.node_id,JSON.stringify(payload),key,at,at);
    }
  }
  return messages;
}
