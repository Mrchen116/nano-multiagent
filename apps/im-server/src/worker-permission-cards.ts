import { isDeepStrictEqual } from 'node:util';
import type { ChatMessage, ChatPermission, ChatStreamReceipt, WorkerPermissionRequest } from '@nano/product-contracts';
import type { ChatConnection } from './chat-streaming.js';
import { all, fail, one, transaction, type ImContext } from './context.js';
import { agentAvailable, ownerAccount } from './identity.js';
import { requireLifecycle } from './agent-lifecycle.js';

const outcomeLabels: Record<string, string> = {
  allow_once: '已允许本次操作', deny: '已拒绝', cancelled: '已取消', unavailable: '审批不可用', timed_out: '已超时',
};

/** Stores a single external call's decision in the authenticated owner's native private chat. */
export class WorkerPermissionCards {
  constructor(private readonly ctx: ImContext) {}

  private destination(agentId: string, nodeId: string, epoch: number, create: boolean) {
    const {db, messaging} = this.ctx;
    const profile = one(db, 'SELECT * FROM agent_profiles WHERE agent_id=? AND node_id=?', agentId, nodeId);
    if (!profile || !agentAvailable(db, profile)) fail(409, 'worker_agent_unavailable');
    const binding = one(db, 'SELECT * FROM personal_agent_bindings WHERE agent_id=?', agentId);
    if (binding && (binding.status !== 'active' || binding.owner_id !== profile.owner_id || binding.node_id !== nodeId || binding.node_epoch !== epoch))
      fail(409, 'personal_binding_not_authorized');
    if (!binding && profile.work_mode !== 'global') fail(409, 'global_worker_required');
    const owner = binding?.owner_user_id ?? ownerAccount(db, profile.owner_id)?.id;
    if (!owner) fail(409, 'worker_owner_unavailable');
    const target = `user:${owner}`;
    const cid = binding?.conversation_id ?? (create ? messaging.resolveTarget(agentId, target) : messaging.resolveTarget(agentId, target, false));
    const sender = messaging.agentUser(agentId).id;
    if (!cid || !one(db, `SELECT 1 FROM conversations c WHERE id=? AND type='direct' AND external_source IS NULL AND space_id=?
      AND (SELECT COUNT(*) FROM conversation_participants WHERE conversation_id=c.id)=2
      AND (SELECT COUNT(*) FROM conversation_participants WHERE conversation_id=c.id AND user_id IN (?,?))=2`,
      cid, profile.space_id, sender, owner)) fail(409, 'worker_owner_chat_unavailable');
    return {cid, owner, sender};
  }

  /** Publish once across transport retries and return the original card identity. */
  create(c: ChatConnection, p: WorkerPermissionRequest): ChatStreamReceipt {
    const {db, messaging} = this.ctx;
    const request = p.permission_request;
    const result = transaction(db, () => {
      const {cid, sender} = this.destination(p.agent_id, c.node_id, c.node_epoch, true);
      const previous = one(db, 'SELECT message_id FROM worker_permission_cards WHERE agent_id=? AND request_id=?', p.agent_id, request.request_id);
      if (previous) {
        const message = messaging.message(previous.message_id);
        const card = message.permission_requests[0];
        if (message.conversation_id !== cid || !card || card.node_epoch !== c.node_epoch ||
          card.session_id !== p.session_id || card.run_id !== p.run_id || card.call_id !== request.call_id ||
          card.tool_name !== request.tool_name || card.question !== request.question || card.expires_at !== p.expires_at ||
          !isDeepStrictEqual(card.worker, p.worker) || !isDeepStrictEqual(card.tool_input, request.tool_input))
          fail(409, 'worker_request_identity_conflict');
        requireLifecycle(db, p.agent_id, message.lifecycle_revision);
        return {message};
      }
      if (p.expires_at <= Date.now()) fail(409, 'worker_request_expired');
      const message = messaging.records.insert(cid, sender, 'agent', request.question, [], null, 'completed', {publish:false});
      const card: ChatPermission = {
        request_id:request.request_id, call_id:request.call_id, tool_name:request.tool_name, question:request.question,
        tool_input:request.tool_input, worker:p.worker, expires_at:p.expires_at, status:'pending',
        options:[{id:'allow_once', label:'Allow once', description:''}, {id:'deny', label:'Deny', description:''}],
        conversation_id:cid, message_id:message.id, agent_id:p.agent_id, session_id:p.session_id, run_id:p.run_id,
        node_id:c.node_id, node_epoch:c.node_epoch, lifecycle_revision:message.lifecycle_revision,
      };
      messaging.records.permissions(message.id, [card], true);
      db.prepare('INSERT INTO worker_permission_cards VALUES(?,?,?,?)').run(p.agent_id, request.request_id, message.id, p.expires_at);
      const frame = messaging.records.chatEvent(cid, message.id, {type:'permission.request', data:{...card, permission_request:card}}, 'completed', false);
      return {message, frame};
    });
    if (result.frame) {
      messaging.publishMessages([result.message], {deferDelivery:true});
      messaging.publishCommitted(result.frame);
    }
    return {kind:p.kind, run_id:p.run_id, message_id:result.message.id, conversation_id:result.message.conversation_id};
  }

  /** Check the live binding and original private card each time an answer is submitted. */
  authorize(message: ChatMessage, card: ChatPermission, userId: string): void {
    const original = one(this.ctx.db, 'SELECT message_id FROM worker_permission_cards WHERE agent_id=? AND request_id=?', card.agent_id, card.request_id);
    if (!original || original.message_id !== message.id || card.message_id !== message.id || card.conversation_id !== message.conversation_id)
      fail(409, 'worker_request_identity_conflict');
    const {owner, cid} = this.destination(card.agent_id!, card.node_id!, card.node_epoch!, false);
    if (userId !== owner || cid !== message.conversation_id) fail(403, 'worker_owner_required');
    if (Number(card.expires_at) <= Date.now()) {
      this.finish(message, 'timed_out');
      fail(409, 'worker_request_expired');
    }
  }

  /** Freeze terminal content and retract both live controls and the persisted wait. */
  finish(message: ChatMessage, decision: string): void {
    const card = message.permission_requests[0];
    if (!card || card.status === 'resolved') return;
    if (!Object.hasOwn(outcomeLabels, decision)) fail(400, 'invalid_worker_outcome');
    if (decision === 'allow_once' && (card.status !== 'submitted' || card.decision !== decision)) fail(409, 'worker_owner_decision_required');
    const {db, messaging} = this.ctx;
    const frames = transaction(db, () => {
      Object.assign(card, {status:'resolved', decision});
      const text = `${card.question}\n\n${outcomeLabels[decision]}`;
      messaging.records.permissions(message.id, [card], false);
      db.prepare('UPDATE messages SET content=? WHERE id=?').run(text, message.id);
      db.prepare('UPDATE worker_permission_cards SET pending_until=NULL WHERE message_id=?').run(message.id);
      return [
        messaging.records.chatEvent(message.conversation_id, message.id, {type:'permission.resolved', data:{...card, permission_request:card}}, 'completed', false),
        messaging.records.chatEvent(message.conversation_id, message.id, {type:'message.completed', data:messaging.message(message.id)}, 'completed', false),
      ];
    });
    for (const frame of frames) messaging.publishCommitted(frame);
  }

  /** Close abandoned cards even after the original node or center process restarted. */
  expire(): void {
    for (const row of all(this.ctx.db, 'SELECT message_id FROM worker_permission_cards WHERE pending_until<=?', Date.now()))
      this.finish(this.ctx.messaging.message(row.message_id), 'timed_out');
  }
}
