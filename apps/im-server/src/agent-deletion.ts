import { randomUUID } from 'node:crypto';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import type { AgentDeletionIntent, AgentDeletionView, AgentWorkspaceWitness } from '@nano/product-contracts';
import { all, body, fail, one, params, transaction, type ImContext, type Row } from './context.js';
import { lifecycle } from './agent-lifecycle.js';
import { canAccessSpace } from './identity.js';
import { conversationAccess, conversationReaderIds } from './conversation-access.js';

export function deletionIntent(row: Row): AgentDeletionIntent {
  return {agent_id:row.agent_id, operation_id:row.operation_id, revision:row.revision,
    ...(row.workspace_json ? {workspace:JSON.parse(row.workspace_json) as AgentWorkspaceWitness} : {})};
}

/** Return the saved operation on reconnect without exposing it to another owner. */
export function resumableAgentDeletions(ctx: ImContext, node: string, owner: string, epoch: number): AgentDeletionIntent[] {
  return all(ctx.db, "SELECT * FROM agent_deletions WHERE node_id=? AND owner_id=? AND node_epoch=? AND state IN ('waiting_node','deleting')",
    node, owner, epoch).map(deletionIntent);
}

export function requireDeletionOperation(ctx: ImContext, identity: {node_id:string;owner_id:string;node_epoch:number}, input: Row): Row {
  if (typeof input.agent_id!=='string' || typeof input.operation_id!=='string') fail(422,'invalid_agent_deletion');
  const operation = one(ctx.db, 'SELECT * FROM agent_deletions WHERE agent_id=? AND operation_id=? AND node_id=? AND owner_id=? AND node_epoch=?',
    input.agent_id, input.operation_id, identity.node_id, identity.owner_id, identity.node_epoch);
  if (!operation) fail(404, 'agent_deletion_not_found');
  return operation;
}

export function executionCleanupRevision(ctx: ImContext, conversationId: string): number {
  return one(ctx.db, 'SELECT revision FROM conversation_execution_cleanup WHERE conversation_id=?', conversationId)?.revision ?? 0;
}

/** Resolve former Work anchors using their original space and current chat permissions. */
export function rejectDeletedExecution(ctx: ImContext, user: Row, agentId: string, kind: 'session'|'message'|'agent', targetId: string): void {
  const row = one(ctx.db, "SELECT p.space_id FROM agent_deletions d JOIN agent_profiles p USING(agent_id) WHERE d.agent_id=? AND d.state='deleted'", agentId);
  if (!row) return;
  if (!canAccessSpace(user, row.space_id)) fail(404, 'agent_not_accessible');
  const link = kind === 'agent' ? row : one(ctx.db, 'SELECT * FROM deleted_agent_work_links WHERE agent_id=? AND kind=? AND target_id=?', agentId, kind, targetId);
  if (!link || link.conversation_id && !conversationAccess(ctx.db, link.conversation_id, user.id)) fail(404, 'agent_not_accessible');
  fail(410, 'agent_execution_deleted');
}

const executionFields = ['tool_calls','thinking','background_returns','reply_process','token_usage','permission_requests','awaiting_permission_at','elapsed_ms','kernel_message_id'];
const executionEvents = ['tool_call.upserted','tool_call.completed','thinking.segment','reply_process.upserted','reply_process.updated','background_return.updated','run.heartbeat','permission.request','permission.submitted','permission.resolved'];

function purgeCenterExecution(ctx: ImContext, id: string): string[] {
  const db = ctx.db, sender=`agent:${id}`;
  const targetMessages="SELECT m.id FROM messages m JOIN users u ON u.id=m.sender_user_id WHERE u.username=?";
  const affected=all(db,`SELECT DISTINCT conversation_id FROM messages WHERE id IN (${targetMessages})`,sender).map(row=>String(row.conversation_id));
  db.prepare(`INSERT OR IGNORE INTO deleted_agent_work_links
    SELECT ?,'message',id,conversation_id FROM messages WHERE id IN (${targetMessages})`).run(id,sender);
  db.prepare(`UPDATE messages SET tool_calls_json=NULL,thinking_json=NULL,background_returns_json=NULL,reply_process_json=NULL,
    token_usage_json=NULL,permission_request_json=NULL,awaiting_permission_at=NULL,elapsed_ms=NULL,kernel_message_id=NULL
    WHERE id IN (${targetMessages})`).run(sender);
  db.prepare(`DELETE FROM conversation_events WHERE message_id IN (${targetMessages})
    AND event_type IN (SELECT value FROM json_each(?))`).run(sender,JSON.stringify(executionEvents));
  const paths=executionFields.flatMap(key=>[`$.${key}`,`$.message.${key}`]);
  db.prepare(`UPDATE conversation_events SET payload_json=json_remove(payload_json,${paths.map(()=>'?').join(',')})
    WHERE message_id IN (${targetMessages})`).run(...paths,sender);
  const revision=db.prepare(`INSERT INTO conversation_execution_cleanup VALUES(?,1)
    ON CONFLICT(conversation_id) DO UPDATE SET revision=revision+1`);
  for (const conversation of affected) revision.run(conversation);
  db.prepare(`INSERT OR IGNORE INTO deleted_agent_work_links
    SELECT root_agent_id,'session',session_id,NULL FROM agent_work_sessions WHERE root_agent_id=?`).run(id);
  for (const table of ['agent_work_items','agent_work_turns']) db.prepare(
    `DELETE FROM ${table} WHERE session_id IN (SELECT session_id FROM agent_work_sessions WHERE root_agent_id=?)`).run(id);
  db.prepare('DELETE FROM agent_work_sessions WHERE root_agent_id=?').run(id);
  db.prepare('DELETE FROM agent_work_events WHERE root_agent_id=?').run(id);
  db.prepare("DELETE FROM agent_work_query_snapshots WHERE json_extract(data,'$.agent')=?").run(id);
  db.prepare('DELETE FROM agent_config_operations WHERE agent_id=?').run(id);
  db.prepare("DELETE FROM relay_tasks WHERE json_extract(payload_json,'$.agent_id')=?").run(id);
  db.prepare('DELETE FROM task_context_index WHERE agent_id=?').run(id);
  db.prepare('DELETE FROM agent_message_dispatch_log WHERE source_agent_id=?').run(id);
  db.prepare(`UPDATE channel_manifest_heads SET manifest_revision=manifest_revision+1
    WHERE node_id IN (SELECT node_id FROM agent_channels WHERE agent_id=?)`).run(id);
  db.prepare('DELETE FROM agent_channel_status WHERE channel_id IN (SELECT channel_id FROM agent_channels WHERE agent_id=?)').run(id);
  for (const table of ['agent_channels','agent_channel_removals']) db.prepare(`DELETE FROM ${table} WHERE agent_id=?`).run(id);
  db.prepare(`UPDATE agent_profiles SET is_stale=1,staled_at=datetime('now'),description='',workspace_root=NULL,
    workspace_is_default=NULL,default_model=NULL,model_fallbacks_json='[]',reasoning_effort=NULL,approval_mode=NULL,
    custom_prompt=NULL,features_json='{}',skills_json='[]',skills_selection_mode=NULL,tool_allowlist_json='[]',heartbeat_json=NULL
    WHERE agent_id=?`).run(id);
  return affected;
}

export function reportAgentDeletion(ctx: ImContext, operation: Row, input: Row): void {
  if (!['deleting','failed','deleted'].includes(input.state)) fail(422, 'invalid_agent_deletion_state');
  if (operation.state === 'deleted') return;
  if (operation.state === 'failed' && input.state !== 'deleted') return;
  const frames = transaction(ctx.db, () => {
    const conversations = input.state === 'deleted' ? purgeCenterExecution(ctx, operation.agent_id) : [];
    ctx.db.prepare('UPDATE agent_deletions SET state=?,error_detail=? WHERE operation_id=?')
      .run(input.state,typeof input.error_detail === 'string' && input.state === 'failed' ? input.error_detail.slice(0,500) : null,operation.operation_id);
    // A cleanup between the client's sync snapshot and WebSocket resume must be replayable.
    return conversations.map(id=>ctx.messaging.event(id,null,'conversation.execution_cleanup',
      {conversation_id:id,execution_cleanup_revision:executionCleanupRevision(ctx,id)},'completed',false));
  });
  for (const frame of frames) {
    ctx.gateway.broadcast(conversationReaderIds(ctx.db,frame.conversation_id),frame);
  }
}

export function registerAgentDeletionRoutes(app: FastifyInstance, ctx: ImContext): void {
  const db = ctx.db;
  const authorized = (req: FastifyRequest) => {
    const user = ctx.identity.authenticateRequest(req);
    const profile = one(db,'SELECT * FROM agent_profiles WHERE agent_id=?',params(req).agent_id);
    if (!profile || !canAccessSpace(user,profile.space_id)) fail(404,'agent_not_found');
    if (user.owner_id!==profile.owner_id || user.username.startsWith('agent:')) fail(403,'agent_owner_required');
    return profile;
  };
  const operation = (profile: Row) => one(db,'SELECT * FROM agent_deletions WHERE agent_id=?',profile.agent_id);
  const eligibility = (profile: Row) => {
    const state = lifecycle(db,profile.agent_id);
    const connection = ctx.gateway.nodes.get(profile.node_id);
    const conn = connection?.socket.readyState===1 && ctx.gateway.valid(connection) ? connection : undefined;
    const reason = profile.is_stale || one(db,'SELECT 1 FROM personal_agent_bindings WHERE agent_id=?',profile.agent_id)
      ? 'agent_deletion_unavailable'
      : state.desired !== 'disabled' || state.observed !== 'disabled' || state.applied_revision !== state.revision
        ? 'stop_not_confirmed'
        : !conn ? 'node_offline' : !conn.agent_deletion_v1 ? 'node_upgrade_required' : undefined;
    return {state,conn,reason};
  };
  const view = (profile: Row, saved = operation(profile)): AgentDeletionView => {
    const {state,reason,conn} = eligibility(profile);
    const operationState = saved?.state==='deleting' && !conn ? 'waiting_node' : saved?.state;
    return {agent_id:profile.agent_id,eligible:!reason && !saved,revision:state.revision,profile_version:profile.profile_version,
      ...(reason && !saved ? {reason} : {}),
      ...(saved ? {operation:{operation_id:saved.operation_id,state:operationState,delete_workspace:!!saved.workspace_json,
        ...(saved.error_detail ? {error_detail:saved.error_detail} : {})}} : {})};
  };
  const path = '/im/v1/agents/:agent_id/deletion';
  app.get(path, async (req,reply) => {
    reply.header('Cache-Control','private, no-store');
    const profile = authorized(req), state = view(profile);
    if (!state.eligible) return state;
    try {
      const preview = await ctx.gateway.request(profile.node_id,'agent.deletion.preview',{agent_id:profile.agent_id});
      return {...state,...(preview.workspace ? {workspace:preview.workspace} : {})};
    } catch {
      return state;
    }
  });
  app.post(path, async (req,reply) => {
    reply.header('Cache-Control','private, no-store');
    const profile = authorized(req), input = body(req);
    if (typeof input.request_id!=='string' || !input.request_id || input.request_id.length>200
      || !Number.isSafeInteger(input.expected_revision) || !Number.isSafeInteger(input.expected_profile_version)
      || input.workspace_witness!==undefined && typeof input.workspace_witness!=='string') fail(422,'invalid_agent_deletion');
    const prior = operation(profile);
    if (prior) {
      if (prior.request_id!==input.request_id || (prior.workspace_json ? JSON.parse(prior.workspace_json).witness : undefined)!==input.workspace_witness)
        fail(409,'agent_deletion_already_requested');
      return view(profile,prior);
    }
    let workspace: AgentWorkspaceWitness | undefined;
    if (input.workspace_witness!==undefined) {
      const result = await ctx.gateway.request(profile.node_id,'agent.deletion.preview',{agent_id:profile.agent_id});
      workspace = result.workspace;
      if (!workspace || workspace.witness!==input.workspace_witness) fail(409,'workspace_confirmation_changed');
    }
    const saved = transaction(db,() => {
      const current = authorized(req);
      const {state,conn,reason} = eligibility(current);
      const existing = operation(current);
      if (existing) {
        if (existing.request_id===input.request_id && existing.workspace_json===(workspace ? JSON.stringify(workspace) : null)) return existing;
        fail(409,'agent_deletion_already_requested');
      }
      if (reason || !conn) fail(409,reason ?? 'node_offline');
      if (current.node_id!==profile.node_id || state.revision!==input.expected_revision || current.profile_version!==input.expected_profile_version)
        fail(409,'agent_deletion_scope_changed');
      if (one(db,"SELECT 1 FROM agent_config_operations WHERE agent_id=? AND status IN ('pending','gateway_applied','compensating')",profile.agent_id))
        fail(409,'agent_configuration_pending');
      return db.prepare(`INSERT INTO agent_deletions(agent_id,operation_id,request_id,owner_id,node_id,node_epoch,revision,profile_version,workspace_json,state)
        VALUES(?,?,?,?,?,?,?,?,?,'waiting_node') RETURNING *`).get(profile.agent_id,randomUUID(),input.request_id,profile.owner_id,profile.node_id,conn.node_epoch,
        state.revision,current.profile_version,workspace ? JSON.stringify(workspace) : null) as Row;
    });
    ctx.gateway.trajectory.closeAgent(profile.agent_id);
    if (saved.state==='waiting_node') ctx.gateway.send(profile.node_id,{type:'agent.deletion.apply',payload:deletionIntent(saved)});
    return reply.code(202).send(view(profile,saved));
  });
  app.post(`${path}/retry`,(req,reply) => {
    const profile = authorized(req), saved = operation(profile);
    if (!saved || saved.operation_id!==body(req).operation_id) fail(404,'agent_deletion_not_found');
    if (saved.state==='deleted' || saved.state==='deleting') return view(profile,saved);
    if (!ctx.gateway.nodes.get(profile.node_id)?.agent_deletion_v1) fail(409,'node_unavailable');
    db.prepare("UPDATE agent_deletions SET state='waiting_node',error_detail=NULL WHERE operation_id=?").run(saved.operation_id);
    ctx.gateway.send(profile.node_id,{type:'agent.deletion.apply',payload:deletionIntent(saved)});
    return reply.code(202).send(view(profile,operation(profile)));
  });
}
