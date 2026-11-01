import { randomUUID } from 'node:crypto';
import type { DatabaseSync } from 'node:sqlite';
import type { ChatActor, ChatAttachment, ChatEvent, ChatMessage, ChatPermission, ChatProcessItem, ChatStreamFact, ChatThinking, ChatToolCall, InteractionSnapshot, MessageInteractive } from '@nano/product-contracts';
import { lifecycle } from './agent-lifecycle.js';
import { fail, now, transaction } from './context.js';

/** Fixed SQLite columns are distinct from the public JSON projection. */
export interface MessageRecord {
  id:string; conversation_id:string; sender_user_id:string; sender_type:string; lifecycle_revision:number|null;
  content:string; attachments_json:string; delivery_status:string; created_at:string; caller_idempotency_key:string|null;
  caller_payload_json:string|null; sender_display_name:string|null; sender_source_id:string|null; timezone:string|null;
  tool_calls_json:string|null; thinking_json:string|null; background_returns_json:string|null; reply_process_json:string|null;
  permission_request_json:string|null; token_usage_json:string|null; system_notice_json:string|null; interaction_reply_json:string|null;
  elapsed_ms:number|null; kernel_message_id:string|null; awaiting_permission_at:string|null;
}
interface MessageDelegation {agent_id:string;authorized_by:string;display_name:string;representation_operation_id:string|null}
interface MessageAgent {agent_id:string}
interface MessageAuthorName {display_name:string}
export interface PublicationRecord {dispatch_request_key:string;source_agent_id:string;target_kind:string;target_id:string;conversation_id:string;message_id:string;created_at:string}
interface MessageUser {id:string; username:string; display_name:string; is_stale?:number}
export interface MessageMetadata {
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

/** Own message SQL/JSON and projection; authorization and relay policy belong to callers. */
export class MessageRecords {
  /** Bind persistence to the existing interaction owner and event delivery hooks. */
  constructor(private readonly db:DatabaseSync,private readonly ports:Ports) {}
  /** Read the fixed storage row; return undefined when the identity is absent. */
  find(id:string):MessageRecord|undefined {return this.db.prepare('SELECT * FROM messages WHERE id=?').get(id) as unknown as MessageRecord|undefined;}
  /** Read a scoped send attempt without comparing or normalizing its immutable payload. */
  attempt(cid:string,key:string):MessageRecord|undefined {return this.db.prepare('SELECT * FROM messages WHERE conversation_id=? AND caller_idempotency_key=?').get(cid,key) as unknown as MessageRecord|undefined;}
  /** Project the stored author while preserving personal-Agent attribution. */
  actor(u:MessageUser):ChatActor {return {type:u.username.startsWith('agent:')?'agent':'user',id:u.username.startsWith('agent:')?u.username.slice(6):u.id,display_name:u.display_name,user_id:u.id,is_stale:u.is_stale?true:null,...(u.username.startsWith('agent:')&&this.db.prepare('SELECT 1 FROM personal_agent_bindings WHERE agent_id=?').get(u.username.slice(6))?{role:'personal' as const}:{})};}
  /** Persist original event data, then invoke the existing publish/wake policy.
   * Args:
   *   publish: False suppresses immediate broadcast; the durable event remains replayable.
   */
  event(id:string,messageId:string|null,type:string,data:object,status='completed',publish=true):MessageEventFrame {
    const at=now(),payload={created_at:at,delivery_status:status,conversation_id:id,...(messageId?{message_id:messageId}:{}),...data};
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
  /** Consume a delta identity once and append only while running.
   * Returns:
   *   False for a duplicate or terminal message; no event should be published.
   */
  appendDelta(m:StreamMessageIdentity,text:string,key?:string):boolean {
    if(key&&!this.db.prepare('INSERT OR IGNORE INTO message_delta_idempotency VALUES(?,?)').run(m.id,key).changes)return false;
    if(m.delivery_status!=='running')return false;
    this.db.prepare('UPDATE messages SET content=content||? WHERE id=?').run(text,m.id);return true;
  }
  /** Store the producer's final text/statistics and release its permission wait. */
  complete(m:ChatMessage,p:Extract<ChatStreamFact,{kind:'message_completed'}>):void {
    this.db.prepare('UPDATE messages SET content=?,delivery_status=?,token_usage_json=?,elapsed_ms=?,kernel_message_id=?,awaiting_permission_at=NULL WHERE id=?').run(p.final_content??m.content,p.delivery_status??'completed',p.token_usage?JSON.stringify(p.token_usage):null,p.elapsed_ms??null,p.kernel_message_id??null,m.id);
  }
  /** Apply the existing provisional-message deletion semantics. */
  discard(id:string):void {this.db.prepare('DELETE FROM messages WHERE id=?').run(id);}
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
  /** Project public message data and non-enumerable internal details from stored columns.
   * Raises:
   *   Error: HTTP 404 if the message does not exist.
   */
  message(id:string):ChatMessage {
    const m=this.find(id);if(!m)fail(404,'message not found');
    const u=this.db.prepare('SELECT * FROM users WHERE id=?').get(m.sender_user_id) as unknown as MessageUser;
    const delegation=this.db.prepare('SELECT * FROM pa_delegated_messages WHERE message_id=?').get(id) as unknown as MessageDelegation|undefined;
    const updateWait=this.ports.messageWait?.(id),permissions:ChatPermission[]=JSON.parse(m.permission_request_json??'[]');
    // Retain the established wire property order as well as the original stored JSON values.
    const result:ChatMessage={
      id:m.id,conversation_id:m.conversation_id,sender_user_id:m.sender_user_id,sender_type:m.sender_type,
      lifecycle_revision:m.lifecycle_revision,content:m.content,delivery_status:m.delivery_status,created_at:m.created_at,
      timezone:m.timezone,elapsed_ms:m.elapsed_ms,kernel_message_id:m.kernel_message_id,
      sender:{...this.actor(u),type:m.sender_type,display_name:m.sender_display_name??u.display_name},
      ...(updateWait!==undefined?{update_wait:updateWait}:{}),
      ...(delegation?.representation_operation_id?{pa_agent_id:delegation.agent_id}:delegation?{delegation:{agent_id:delegation.agent_id,authorized_by:delegation.authorized_by,display_name:delegation.display_name,label:`${(this.db.prepare('SELECT display_name FROM users WHERE id=?').get(delegation.authorized_by) as MessageAuthorName|undefined)?.display_name??delegation.display_name}的 PA`}}:{}),
      attachments:JSON.parse(m.attachments_json??'[]'),
      tool_calls:(JSON.parse(m.tool_calls_json??'[]') as ChatToolCall[]).map(call=>withHumanApproval(call,permissions)),
      thinking:JSON.parse(m.thinking_json??'[]'),background_returns:JSON.parse(m.background_returns_json??'[]'),
      reply_process:JSON.parse(m.reply_process_json??'[]'),permission_requests:permissions,
      token_usage:JSON.parse(m.token_usage_json??'null'),system_notice:JSON.parse(m.system_notice_json??'null'),interaction_reply:JSON.parse(m.interaction_reply_json??'null'),
    };
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
    if ((extra.interactive || extra.personal_source) && !this.db.isTransaction)
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
    this.db
      .prepare("UPDATE conversations SET last_message_preview=?,last_message_at=? WHERE id=?")
      .run(content.trim().slice(0, 120) || attachments[0]?.file_name || "", at, cId);
    this.db
      .prepare(
        "UPDATE conversation_participants SET unread_count=unread_count+1 WHERE conversation_id=? AND user_id!=?",
      )
      .run(cId, sender);
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
    const m = this.message(id);
    this.chatEvent(cId, id, {type:"message.created", data:{...m,message_id:id}}, status, extra.publish !== false);
    return m;
  }
}
