import { randomUUID } from 'node:crypto';
import type { DatabaseSync } from 'node:sqlite';
import type { ChatActor, ChatAttachment, ChatEvent, ChatHistoryMessage, ChatMessage, ChatPermission, ChatProcessItem, ChatProcessSummary, ChatStreamFact, ChatThinking, ChatToolCall, InteractionSnapshot, MessageInteractive, TaskCardRef } from '@nano/product-contracts';
import { externalAvatarId } from './identity.js';
import { lifecycle } from './agent-lifecycle.js';
import { fail, now, transaction } from './context.js';

import { chatAllowed, type ProviderFacts } from './collaboration.js';
import { discardThreadUnread, listUnread, recordThreadDelivery, threadAddressesAgent } from './threads.js';

/** Fixed SQLite columns are distinct from the public JSON projection. */
export interface MessageRecord {
  id:string; conversation_id:string; sender_user_id:string; sender_type:string; lifecycle_revision:number|null;
  content:string; attachments_json:string; task_cards_json:string|null; delivery_status:string; created_at:string; caller_idempotency_key:string|null;
  caller_payload_json:string|null; sender_display_name:string|null; sender_source_id:string|null; timezone:string|null;
  tool_calls_json:string|null; thinking_json:string|null; background_returns_json:string|null; reply_process_json:string|null;
  permission_request_json:string|null; token_usage_json:string|null; system_notice_json:string|null; interaction_reply_json:string|null;
  reply_to_json:string|null; thread_root_id:string|null;
  elapsed_ms:number|null; kernel_message_id:string|null; awaiting_permission_at:string|null;
}
interface MessageDelegation {agent_id:string;authorized_by:string;display_name:string;representation_operation_id:string|null}
interface MessageAgent {agent_id:string}
interface MessageAuthorName {display_name:string}
export interface PublicationRecord {dispatch_request_key:string;source_agent_id:string;target_kind:string;target_id:string;conversation_id:string;message_id:string;created_at:string}
interface MessageUser {id:string; username:string; display_name:string; is_stale?:number}
export interface MessageMetadata {
  reply_to?:ChatMessage['reply_to'];
  task_cards?:TaskCardRef[];
  thread_root_id?:string;
  skipThreadDelivery?: boolean;
  trackReceipts?: boolean;
  pendingRelayAgents?: string[];
  provider_facts?: ProviderFacts;
  created_at?:string; sender_display_name?:string; sender_source_id?:string; timezone?:string|null;
  system_notice?:unknown; interactive?:unknown; interaction_reply?:InteractionSnapshot; publish?:boolean;
  personal_source?:{binding_id:string; agent_id:string; owner_user_id:string; display_name:string; operation_id?:string|null};
}
export interface MessageEventRecord {event_id:number; conversation_id:string; message_id:string|null; event_type:string; delivery_status:string; payload_json:string; created_at:string}
export interface MessageEventFrame {op:'event'; event_id:number; conversation_id:string; message_id:string|null; event_type:string; delivery_status:string; created_at:string; data:Record<string,unknown>}
export interface MessageRelayRecord {relay_task_id:string; target_node_id:string; conversation_id:string; message_id:string; payload_json:string; idempotency_key:string; status:string}
interface Ports {
  interactions:{message(id:string):MessageInteractive|undefined; record(id:string,cid:string,sender:string,input:unknown):unknown};
  agentUserId(agentId:string):string;
  messageWait?(id:string):ChatMessage['update_wait'];
  publish(frame:MessageEventFrame, enabled:boolean):void;
}
export interface StreamMessageIdentity {id:string; conversation_id:string; sender_user_id:string; sender_type:string; lifecycle_revision:number|null; delivery_status:string; sender:{id:string}}

/** Derive human badges from durable decisions, preserving all native tool content. */
export function withHumanApproval(call:ChatToolCall, permissions:ChatPermission[]):ChatToolCall {
  const decision=permissions.findLast(item=>item.call_id===call.id&&item.status==='resolved'&&item.decided_by)?.decision;
  if(decision!=='allow_once'&&decision!=='deny')return call;
  return {...call,approval:decision==='allow_once'?'user_allow':'user_deny',...(decision==='deny'?{reason:'denied'}:{})};
}

function chatActor(user: MessageUser, profile?: {binding_id?: unknown; avatar_variant?: unknown}): ChatActor {
  const agent = user.username.startsWith('agent:');
  return {
    type: agent ? 'agent' : 'user', id: agent ? user.username.slice(6) : user.id,
    user_id: user.id, display_name: user.display_name, is_stale: user.is_stale ? true : null,
    ...(profile?.binding_id ? {role:'personal'} : {}),
    ...(typeof profile?.avatar_variant === 'number' ? {avatar_variant:profile.avatar_variant} : {}),
  };
}

/** Own message SQL/JSON and projection; authorization and relay policy belong to callers. */
export class MessageRecords {
  /** Bind persistence to the existing interaction owner and event delivery hooks. */
  constructor(private readonly db:DatabaseSync,private readonly ports:Ports) {}
  /** Read the fixed storage row; return undefined when the identity is absent. */
  find(id:string):MessageRecord|undefined {return this.db.prepare('SELECT * FROM messages WHERE id=?').get(id) as unknown as MessageRecord|undefined;}
  /** Read a scoped send attempt without comparing or normalizing its immutable payload. */
  attempt(cid:string,key:string):MessageRecord|undefined {return this.db.prepare('SELECT * FROM messages WHERE conversation_id=? AND caller_idempotency_key=?').get(cid,key) as unknown as MessageRecord|undefined;}
  /** Project the stored author while preserving personal-Agent attribution. */
  actor(u:MessageUser):ChatActor {
    const profile = u.username.startsWith('agent:')
      ? this.db.prepare('SELECT a.avatar_variant,b.binding_id FROM agent_profiles a LEFT JOIN personal_agent_bindings b ON b.agent_id=a.agent_id WHERE a.agent_id=?').get(u.username.slice(6))
      : undefined;
    return chatActor(u, profile);
  }
  /** Persist original event data, then invoke the existing publish/wake policy.
   * Args:
   *   publish: False suppresses immediate broadcast; the durable event remains replayable.
   */
  event(id:string,messageId:string|null,type:string,data:object,status='completed',publish=true):MessageEventFrame {
    const topic = (data as {thread_root_message_id?:string}).thread_root_message_id
      ?? (messageId && type.startsWith('permission.') ? this.find(messageId)?.thread_root_id : undefined);
    const notify = topic && messageId && this.db.prepare("SELECT 1 FROM conversations WHERE id=? AND type='group'").get(id)
      ? this.db.prepare('SELECT user_id FROM thread_deliveries WHERE message_id=?').all(messageId).map(row=>row.user_id) : undefined;
    const at=now(),payload={...(topic ? {thread_root_message_id:topic} : {}),...(notify ? {thread_notify_user_ids:notify} : {}),created_at:at,delivery_status:status,conversation_id:id,...(messageId?{message_id:messageId}:{}),...data};
    const result=this.db.prepare('INSERT INTO conversation_events(conversation_id,message_id,event_type,delivery_status,payload_json,created_at) VALUES(?,?,?,?,?,?)').run(id,messageId,type,status,JSON.stringify(payload),at);
    const frame:MessageEventFrame={op:'event',event_id:Number(result.lastInsertRowid),conversation_id:id,message_id:messageId,event_type:type,delivery_status:status,created_at:at,data:{...payload,event_id:Number(result.lastInsertRowid)}};
    this.ports.publish(frame,publish);return frame;
  }
  /** Persist a selected chat event with its type-associated data. */
  chatEvent(cid:string,mid:string|null,event:ChatEvent,status='completed',publish=true):MessageEventFrame {return this.event(cid,mid,event.type,event.data,status,publish);}
  /** Read the event committed with an existing message for post-commit publication. */
  createdEvent(id:string):MessageEventRecord {return this.db.prepare("SELECT * FROM conversation_events WHERE message_id=? AND event_type='message.created'").get(id) as unknown as MessageEventRecord;}
  /** Read already queued deliveries; recipient eligibility is checked by RelayDelivery. */
  queuedRelays(id:string):MessageRelayRecord[] {return this.db.prepare("SELECT * FROM relay_tasks WHERE message_id=? AND status='queued'").all(id) as unknown as MessageRelayRecord[];}
  /** Read the immutable receipt used by explicit Agent publication retries. */
  publication(key:string):PublicationRecord|undefined {return this.db.prepare('SELECT * FROM agent_message_dispatch_log WHERE dispatch_request_key=?').get(key) as unknown as PublicationRecord|undefined;}
  /** Persist an explicit publication receipt inside the caller's message transaction. */
  savePublication(record:PublicationRecord):void {this.db.prepare('INSERT INTO agent_message_dispatch_log VALUES(?,?,?,?,?,?,?)').run(record.dispatch_request_key,record.source_agent_id,record.target_kind,record.target_id,record.conversation_id,record.message_id,record.created_at);}
  /** Freeze the ordinary-send fingerprint within the message transaction. */
  saveAttempt(id:string,payload:string):void {this.db.prepare('UPDATE messages SET caller_payload_json=? WHERE id=?').run(payload,id);}
  /** Preserve native background results without normalizing provider contents. */
  background(id:string,items:unknown[]):void {this.db.prepare('UPDATE messages SET background_returns_json=? WHERE id=?').run(JSON.stringify(items),id);}
  /** Keep deltas independent of the growing process history. */
  streamIdentity(id:string):StreamMessageIdentity {
    const row=this.db.prepare(`SELECT m.id,m.conversation_id,m.sender_user_id,m.sender_type,m.lifecycle_revision,m.delivery_status,u.username FROM messages m JOIN users u ON u.id=m.sender_user_id WHERE m.id=?`).get(id) as unknown as Omit<StreamMessageIdentity,'sender'> & {username:string}|undefined;
    if(!row)fail(404,'message not found');
    return {...row,sender:{id:row.username.startsWith('agent:')?row.username.slice(6):row.sender_user_id}};
  }
  /** Append to a running message inside the caller's delta event transaction.
   * Returns:
   *   False if this key already contributed to the projection.
   */
  appendDelta(messageId:string,text:string,key?:string):boolean {
    if(key&&!this.db.prepare('INSERT OR IGNORE INTO message_delta_idempotency VALUES(?,?)').run(messageId,key).changes)return false;
    this.db.prepare('UPDATE messages SET content=content||? WHERE id=?').run(text,messageId);return true;
  }
  /** Store the producer's final text/statistics and release its permission wait. */
  complete(m:ChatMessage,p:Extract<ChatStreamFact,{kind:'message_completed'}>):void {
    this.db.prepare('UPDATE messages SET content=?,delivery_status=?,token_usage_json=?,elapsed_ms=?,kernel_message_id=?,awaiting_permission_at=NULL WHERE id=?').run(p.final_content??m.content,p.delivery_status??'completed',p.token_usage?JSON.stringify(p.token_usage):null,p.elapsed_ms??null,p.kernel_message_id??null,m.id);
    if(m.thread_root_message_id) recordThreadDelivery(this.db,m.id);
  }
  /** Apply the existing provisional-message deletion semantics and roll back the projection it wrote on insert.
   * Notes:
   *   The caller owns the transaction that also stores the discard tombstone; an absent
   *   row was already discarded together with its rollback, so a replay never rolls back twice.
   */
  discard(id:string):void {
    const row=this.db.prepare('SELECT m.rowid AS row_id,m.conversation_id,m.sender_user_id,m.thread_root_id,c.type FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.id=?').get(id) as unknown as {row_id:number;conversation_id:string;sender_user_id:string;thread_root_id:string|null;type:string}|undefined;
    if(!row)return;
    if(row.thread_root_id && row.type==='group'){
      discardThreadUnread(this.db,row.conversation_id,row.thread_root_id,id);
      this.db.prepare('DELETE FROM messages WHERE id=?').run(id);
      return;
    }
    this.db.prepare('DELETE FROM messages WHERE id=?').run(id);
    // insert() writes the projection from the row it just stored, and ingress can backdate
    // created_at, so insertion order (rowid) is what "the message before this one" means.
    const latest=this.db.prepare('SELECT content,attachments_json,created_at FROM messages WHERE conversation_id=? AND thread_root_id IS NULL ORDER BY rowid DESC LIMIT 1').get(row.conversation_id) as unknown as {content:string;attachments_json:string;created_at:string}|undefined;
    // Mirror insert() so the stored preview keeps the same shape as a normal last message.
    const preview=latest?latest.content.trim().slice(0,120)||(JSON.parse(latest.attachments_json) as ChatAttachment[])[0]?.file_name||'':null;
    this.db.prepare('UPDATE conversations SET last_message_preview=?,last_message_at=? WHERE id=?').run(preview,latest?.created_at??null,row.conversation_id);
    // unread_count is not a simple counter: read marks rewrite it from a watermark, so
    // rolling back by one for everybody would erase real unread and could go negative.
    for(const p of this.db.prepare('SELECT p.user_id,p.unread_count,p.last_read_message_id,(SELECT m.rowid FROM messages m WHERE m.id=p.last_read_message_id AND m.conversation_id=p.conversation_id) AS read_row_id FROM conversation_participants p WHERE p.conversation_id=? AND p.user_id!=?').all(row.conversation_id,row.sender_user_id) as unknown as {user_id:string;unread_count:number;last_read_message_id:string|null;read_row_id:number|null}[]) {
      // A participant who already marked something as read no longer counts this message;
      // recompute from that watermark so unread that arrived later survives. Only a
      // participant without a usable watermark still holds this message's own +1.
      const watermark=p.last_read_message_id===null?null:p.last_read_message_id===id?Number(row.row_id):p.read_row_id;
      const unread=watermark===null
        ?Math.max(p.unread_count-1,0)
        :listUnread(this.db,row.conversation_id,p.user_id,watermark);
      if(unread!==p.unread_count)this.db.prepare('UPDATE conversation_participants SET unread_count=? WHERE conversation_id=? AND user_id=?').run(unread,row.conversation_id,p.user_id);
    }
  }
  /** Persist the caller's sequence-deduplicated thinking projection. */
  thinking(id:string,items:ChatThinking[]):void {this.db.prepare('UPDATE messages SET thinking_json=? WHERE id=?').run(JSON.stringify(items),id);}
  /** Persist merged native tool data and derived approval badges. */
  tools(id:string,items:ChatToolCall[]):void {this.db.prepare('UPDATE messages SET tool_calls_json=? WHERE id=?').run(JSON.stringify(items),id);}
  /** Save permission identity and its associated liveness wait together. */
  permissions(id:string,items:ChatPermission[],pending:boolean):void {this.db.prepare('UPDATE messages SET permission_request_json=?,awaiting_permission_at=? WHERE id=?').run(JSON.stringify(items),pending?now():null,id);}
  /** Save process items after the caller has reconciled stable item identities. */
  process(id:string,items:ChatProcessItem[]):void {this.db.prepare('UPDATE messages SET reply_process_json=? WHERE id=?').run(JSON.stringify(items),id);}
  /** Refresh an already active permission wait after an authorized native heartbeat. */
  heartbeat(id:string):void {this.db.prepare('UPDATE messages SET awaiting_permission_at=? WHERE id=?').run(now(),id);}
  /** Attach per-recipient receipt details to the original sender's view. */
  senderView<T extends ChatMessage>(message: T, viewerId: string): T {
    if (!message.receipts_requested || message.sender_user_id !== viewerId) return message;
    const receipts = this.db.prepare(`
      SELECT r.recipient_id, u.username, a.avatar_variant, b.binding_id, coalesce(a.display_name,u.display_name) AS display_name,
        CASE r.status WHEN 2 THEN 'read' WHEN 1 THEN 'received' ELSE 'sent' END AS status
      FROM message_receipts r JOIN users u ON u.id=r.recipient_id
      LEFT JOIN agent_profiles a ON u.username='agent:'||a.agent_id
      LEFT JOIN personal_agent_bindings b ON b.agent_id=a.agent_id
      WHERE r.message_id=? ORDER BY display_name,r.recipient_id
    `).all(message.id).map(row => {
      const recipient = chatActor({
        id:String(row.recipient_id), username:String(row.username), display_name:String(row.display_name),
      }, row);
      return {recipient_id:recipient.user_id, display_name:recipient.display_name, recipient, status:row.status as 'sent'|'received'|'read'};
    });
    return {...message, receipts};
  }
  /** Project public message data and non-enumerable internal details from stored columns.
   * Raises:
   *   Error: HTTP 404 if the message does not exist.
   */
  message(id:string):ChatMessage {
    const m=this.find(id);if(!m)fail(404,'message not found');
    return this.projectMessage(m);
  }
  /** Read one full message within its already-authorized conversation. */
  conversationMessage(conversationId:string,id:string):ChatMessage {
    const m=this.db.prepare('SELECT * FROM messages WHERE conversation_id=? AND id=?').get(conversationId,id) as unknown as MessageRecord|undefined;
    if(!m)fail(404,'message not found');
    return this.projectMessage(m);
  }
  /** Project collapsed process facts in SQLite so terminal bodies never cross into JS. */
  historySummary(conversationId:string,id:string):ChatHistoryMessage {
    const m=this.db.prepare(`
      WITH scoped AS (
        SELECT *,sender_type='agent' AND delivery_status IN ('completed','failed') AS summarized
        FROM messages WHERE conversation_id=? AND id=?
      )
      SELECT id,conversation_id,sender_user_id,sender_type,lifecycle_revision,content,attachments_json,task_cards_json,
        delivery_status,created_at,sender_display_name,sender_source_id,timezone,
        token_usage_json,system_notice_json,interaction_reply_json,reply_to_json,thread_root_id,elapsed_ms,kernel_message_id,
        awaiting_permission_at,
        CASE WHEN summarized THEN (
          SELECT json_group_array(json(CASE WHEN permission.value->>'status'='resolved' THEN
            json_object('request_id',permission.value->>'request_id','call_id',permission.value->>'call_id',
              'status','resolved','decision',permission.value->>'decision','decided_by',permission.value->>'decided_by')
            ELSE permission.value END) ORDER BY permission.key)
          FROM json_each(scoped.permission_request_json) permission
        ) ELSE permission_request_json END AS permission_request_json,
        CASE WHEN NOT summarized THEN tool_calls_json END AS tool_calls_json,
        CASE WHEN NOT summarized THEN thinking_json END AS thinking_json,
        CASE WHEN NOT summarized THEN background_returns_json END AS background_returns_json,
        CASE WHEN NOT summarized THEN reply_process_json END AS reply_process_json,
        CASE WHEN summarized THEN (
          SELECT json_group_array(json_object('id', tool.value->>'id','status',tool.value->>'status',
            'approval',tool.value->>'approval','reason',CASE WHEN tool.value->>'reason'='denied' THEN 'denied' END))
          FROM json_each(scoped.tool_calls_json) tool
        ) END AS tool_facts,
        CASE WHEN summarized THEN coalesce(json_array_length(thinking_json),0) END AS thinking_count,
        CASE WHEN summarized THEN coalesce(json_array_length(background_returns_json),0) END AS background_return_count,
        CASE WHEN summarized THEN (
          SELECT json_group_object(kind, item_count) FROM (
            SELECT item.value->>'kind' AS kind, count(*) AS item_count
            FROM json_each(scoped.reply_process_json) item
            WHERE item.value->>'kind' IN ('draft','revalidation','segment_handoff')
            GROUP BY kind
          )
        ) END AS reply_process_counts
      FROM scoped
    `).get(conversationId,id) as unknown as Omit<MessageRecord,'caller_idempotency_key'|'caller_payload_json'> & {
      tool_facts: string|null; thinking_count: number|null; background_return_count: number|null; reply_process_counts: string|null;
    } | undefined;
    if(!m)fail(404,'message not found');
    const message=this.projectMessage(m);
    if(m.tool_facts===null)return message;
    const tools=(JSON.parse(m.tool_facts) as ChatToolCall[])
      .map(call=>withHumanApproval(call,message.permission_requests));
    const summary:ChatProcessSummary={
      tool_count:tools.length,
      thinking_count:m.thinking_count!,
      background_return_count:m.background_return_count!,
      reply_process_counts:JSON.parse(m.reply_process_counts??'{}'),
      has_running_tool:tools.some(call=>call.status==='running'),
      approval_allow_count:tools.filter(call=>call.approval==='user_allow').length,
      approval_deny_count:tools.filter(call=>call.approval!=='user_allow'&&(call.approval==='user_deny'||call.reason==='denied')).length,
    };
    return {...message,process_summary:summary};
  }
  private threadSummary(id:string):Pick<ChatMessage,'thread'> {
    const count=this.db.prepare("SELECT count(*) AS count FROM messages WHERE thread_root_id=? AND coalesce(json_extract(system_notice_json,'$.kind'),'')!='thread_unfollowed'").get(id) as {count:number};
    if(!count.count)return {};
    const newest = this.db.prepare(`SELECT m.id, m.sender_user_id, coalesce(nullif(m.sender_display_name,''),u.display_name,m.sender_user_id) AS display_name,
      m.content, m.created_at, json_extract(m.attachments_json, '$[0].file_name') AS file_name
      FROM messages m LEFT JOIN users u ON u.id=m.sender_user_id
      WHERE m.thread_root_id=? AND coalesce(json_extract(m.system_notice_json,'$.kind'),'')!='thread_unfollowed' ORDER BY m.rowid DESC LIMIT 2`).all(id) as {
      id:string; sender_user_id:string; display_name:string; content:string; created_at:string; file_name:string|null;
    }[];
    const latest = newest[0]!;
    const recent_replies = newest.reverse().map(row => ({
      id:row.id, sender_user_id:row.sender_user_id, display_name:row.display_name,
      preview:(row.content.trim() || row.file_name || '').replace(/\s+/g, ' ').slice(0, 160),
    }));
    const participants = this.db.prepare(`
      SELECT m.sender_user_id, m.sender_source_id, m.conversation_id, u.username, a.avatar_variant, b.binding_id,
        COALESCE(m.sender_display_name, u.display_name, m.sender_user_id) AS display_name
      FROM messages m JOIN users u ON u.id=m.sender_user_id
      LEFT JOIN agent_profiles a ON u.username='agent:'||a.agent_id
      LEFT JOIN personal_agent_bindings b ON b.agent_id=a.agent_id
      WHERE m.thread_root_id=? AND coalesce(json_extract(m.system_notice_json,'$.kind'),'')!='thread_unfollowed'
      GROUP BY m.sender_user_id, m.sender_source_id ORDER BY max(m.rowid) DESC LIMIT 3
    `).all(id).map(row => {
      const actor = chatActor({id:String(row.sender_user_id), username:String(row.username), display_name:String(row.display_name)}, row);
      if (row.sender_source_id) actor.avatar_id = externalAvatarId(`external:${row.conversation_id}:${row.sender_source_id}`);
      return {id:actor.avatar_id ?? actor.user_id, display_name:actor.display_name, actor};
    });
    return {thread:{reply_count:count.count, latest_preview:latest.content.trim().slice(0,80), latest_at:latest.created_at, recent_replies, participants}};
  }
  private projectMessage(m:Omit<MessageRecord,'caller_idempotency_key'|'caller_payload_json'>):ChatMessage {
    const {id}=m;
    const u=this.db.prepare('SELECT * FROM users WHERE id=?').get(m.sender_user_id) as unknown as MessageUser;
    const delegation=this.db.prepare('SELECT * FROM pa_delegated_messages WHERE message_id=?').get(id) as unknown as MessageDelegation|undefined;
    const deletedWork=m.sender_type==='agent' && this.db.prepare(`SELECT 1 FROM deleted_agent_work_links w
      JOIN agent_profiles a ON a.agent_id=w.agent_id AND a.work_mode='global'
      WHERE w.agent_id=? AND w.kind='message' AND w.target_id=?`).get(u.username.slice(6),id);
    const updateWait=this.ports.messageWait?.(id),permissions:ChatPermission[]=JSON.parse(m.permission_request_json??'[]');
    // Retain the established wire property order as well as the original stored JSON values.
    const result:ChatMessage={
      id:m.id,conversation_id:m.conversation_id,sender_user_id:m.sender_user_id,sender_type:m.sender_type,
      lifecycle_revision:m.lifecycle_revision,content:m.content,delivery_status:m.delivery_status,created_at:m.created_at,
      timezone:m.timezone,elapsed_ms:m.elapsed_ms,kernel_message_id:m.kernel_message_id,
      sender:{...this.actor(u),type:m.sender_type,display_name:m.sender_display_name ?? (m.sender_source_id ? '?' : u.display_name),
        ...(m.sender_source_id ? {avatar_id:externalAvatarId(`external:${m.conversation_id}:${m.sender_source_id}`)} : {})},
      ...(deletedWork ? {work_record_deleted:true} : {}),
      ...(updateWait!==undefined?{update_wait:updateWait}:{}),
      ...(delegation?.representation_operation_id?{pa_agent_id:delegation.agent_id}:delegation?{delegation:{agent_id:delegation.agent_id,authorized_by:delegation.authorized_by,display_name:delegation.display_name,label:`${(this.db.prepare('SELECT display_name FROM users WHERE id=?').get(delegation.authorized_by) as MessageAuthorName|undefined)?.display_name??delegation.display_name}的 PA`}}:{}),
      ...(m.reply_to_json?{reply_to:JSON.parse(m.reply_to_json)}:{}),
      ...(m.thread_root_id?{thread_root_message_id:m.thread_root_id}:{}),
      ...(!m.thread_root_id ? this.threadSummary(m.id) : {}),
      attachments:JSON.parse(m.attachments_json??'[]'),
      ...(m.task_cards_json ? {task_cards:JSON.parse(m.task_cards_json)} : {}),
      tool_calls:(JSON.parse(m.tool_calls_json??'[]') as ChatToolCall[]).map(call=>withHumanApproval(call,permissions)),
      thinking:JSON.parse(m.thinking_json??'[]'),background_returns:JSON.parse(m.background_returns_json??'[]'),
      reply_process:JSON.parse(m.reply_process_json??'[]'),permission_requests:permissions,
      token_usage:JSON.parse(m.token_usage_json??'null'),system_notice:JSON.parse(m.system_notice_json??'null'),interaction_reply:JSON.parse(m.interaction_reply_json??'null'),
    };
    if (m.sender_type === 'user' && this.db.prepare('SELECT 1 FROM message_receipts WHERE message_id=?').get(id))
      result.receipts_requested = true;
    const interactive=this.ports.interactions.message(id);if(interactive)result.interactive=interactive;
    Object.defineProperties(result,{awaiting_permission_at:{value:m.awaiting_permission_at},sender_source_id:{value:m.sender_source_id}});
    return result;
  }
  /** Create or reuse a scoped message, retaining interaction/provenance transaction ordering.
   * Args:
   *   extra: Controlled metadata; publish=false defers broadcast until caller commit.
   * Returns:
   *   The existing message for a matching key, otherwise the newly stored projection.
   * Notes:
   *   The caller owns authorization and ordinary-send payload conflict checks.
   */
  insert(
    cId: string,
    sender: string,
    type: string,
    content: string,
    attachments: ChatAttachment[] = [],
    key: string | null = null,
    status = "completed",
    extra: MessageMetadata = {},
  ): ChatMessage {
    if ((extra.interactive || extra.personal_source || extra.thread_root_id) && !this.db.isTransaction)
      return transaction(this.db, () => this.insert(cId, sender, type, content, attachments, key, status, extra));
    const old=key?this.attempt(cId,key):undefined;
    if (old) return this.message(old.id);
    const id = randomUUID().replaceAll("-", "");
    const at = extra.created_at ?? now();
    const sourceAgent=type==='agent'?(this.db.prepare("SELECT agent_id FROM agent_profiles a JOIN users u ON u.username='agent:'||a.agent_id WHERE u.id=?").get(sender) as MessageAgent|undefined):undefined;
    this.db
      .prepare(
        `INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,attachments_json,delivery_status,created_at,caller_idempotency_key,sender_display_name,sender_source_id,timezone,lifecycle_revision) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)`,
      )
      .run(
        id,
        cId,
        sender,
        type,
        content,
        JSON.stringify(attachments),
        status,
        at,
        key,
        extra.sender_display_name ?? null,
        extra.sender_source_id ?? null,
        extra.timezone ?? null,
        sourceAgent?lifecycle(this.db,sourceAgent.agent_id).revision:null,
      );
    const groupedThread = extra.thread_root_id
      ? (this.db.prepare('SELECT type FROM conversations WHERE id=?').get(cId) as {type?: string} | undefined)?.type === 'group'
      : false;
    if (!extra.thread_root_id) {
      this.db
        .prepare("UPDATE conversations SET last_message_preview=?,last_message_at=? WHERE id=?")
        .run(content.trim().slice(0, 120) || attachments[0]?.file_name || (extra.task_cards?.length ? "[任务卡片]" : ""), at, cId);
    }
    if (extra.task_cards?.length) {
      this.db.prepare("UPDATE messages SET task_cards_json=? WHERE id=?").run(JSON.stringify(extra.task_cards), id);
    }
    if (!groupedThread && !extra.skipThreadDelivery) {
      this.db
        .prepare(
          "UPDATE conversation_participants SET unread_count=unread_count+1 WHERE conversation_id=? AND user_id!=?",
        )
        .run(cId, sender);
    }
    if (extra.system_notice) this.db.prepare("UPDATE messages SET system_notice_json=? WHERE id=?").run(JSON.stringify(extra.system_notice),id);
    // Controlled provenance must exist before card validation and message.created.
    if (extra.personal_source) {
      const source=extra.personal_source;
      this.db.prepare('INSERT INTO pa_delegated_messages(message_id,binding_id,agent_id,authorized_by,display_name,representation_operation_id) VALUES(?,?,?,?,?,?)')
        .run(id,source.binding_id,source.agent_id,source.owner_user_id,source.display_name,source.operation_id ?? null);
    }
    if (extra.interactive) {
      if (type !== 'agent' && !extra.personal_source?.operation_id) fail(403, 'Only Agent messages may contain interactive replies');
      this.ports.interactions.record(id, cId, extra.personal_source?.operation_id ? this.ports.agentUserId(extra.personal_source.agent_id) : sender, extra.interactive);
    }
    if (extra.interaction_reply) this.db.prepare('UPDATE messages SET interaction_reply_json=? WHERE id=?').run(JSON.stringify(extra.interaction_reply), id);
    if (extra.reply_to) this.db.prepare('UPDATE messages SET reply_to_json=? WHERE id=?').run(JSON.stringify(extra.reply_to),id);
    if (extra.thread_root_id) {
      this.db.prepare('UPDATE messages SET thread_root_id=? WHERE id=?').run(extra.thread_root_id,id);
      if (groupedThread && !extra.skipThreadDelivery) recordThreadDelivery(this.db,id);
    }
    if (extra.provider_facts) this.db.prepare('INSERT INTO provider_message_facts VALUES(?,?)').run(id,JSON.stringify(extra.provider_facts));
    if (status==='pending' && extra.pendingRelayAgents && !extra.pendingRelayAgents.some(agentId=>chatAllowed(this.db,agentId,id) && (!groupedThread || threadAddressesAgent(this.db,id,agentId)))) {
      status='completed';
      this.db.prepare("UPDATE messages SET delivery_status='completed' WHERE id=?").run(id);
    }
    if (extra.trackReceipts) this.db.prepare(`
      INSERT INTO message_receipts(message_id,recipient_id)
      SELECT ?,p.user_id FROM conversation_participants p
      JOIN conversations c ON c.id=p.conversation_id
      JOIN users u ON u.id=p.user_id
      LEFT JOIN agent_profiles a ON u.username='agent:'||a.agent_id
      WHERE c.id=? AND p.user_id<>? AND c.external_source IS NULL
        AND (a.agent_id IS NULL OR a.collaboration_scope='team' OR EXISTS (
          SELECT 1 FROM owner_direct_agent_messages d WHERE d.message_id=? AND d.agent_id=a.agent_id))
        AND (? IS NULL OR c.type<>'group' OR EXISTS (
          SELECT 1 FROM thread_follows f WHERE f.conversation_id=c.id AND f.root_message_id=? AND f.user_id=p.user_id AND f.following=1))
        AND
        (c.type='group' OR (c.type='direct' AND (a.agent_id IS NULL OR a.work_mode='global')))
    `).run(id,cId,sender,id,extra.thread_root_id ?? null,extra.thread_root_id ?? null);
    const m = this.message(id);
    // Shadow messages store under the local owner even when the provider has no display name.
    const data = {...m,message_id:id,...(extra.sender_source_id
      ? {sender_display_name:extra.sender_display_name?.trim() || extra.sender_source_id}
      : {})};
    this.chatEvent(cId, id, {type:"message.created", data}, status, extra.publish !== false);
    return m;
  }
}
