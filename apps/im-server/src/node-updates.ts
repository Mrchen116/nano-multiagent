import { randomUUID } from 'node:crypto';
import type { FastifyInstance } from 'fastify';
import { nodeUpdateCancellable, nodeUpdateTerminal, type NodeRelease, type NodeUpdateOperation,
  type NodeUpdateReport, type NodeUpdateState, type NodeUpdateView } from '@nano/product-contracts';
import { all, body, fail, now, one, params, transaction, type ImContext, type Row } from './context.js';
import { bearer } from './identity.js';
import { installMaterials, releaseManifest } from './install.js';

type Identity = {node_id: string; owner_id: string; node_epoch: number};
const active = "('requested','downloading','installing','waiting','switching','verifying','rolling_back')";
const projection = (r: Row): NodeUpdateOperation => ({ id: r.id, request_id: r.request_id, node_id: r.node_id,
  owner_id: r.owner_id, node_epoch: r.node_epoch, target: JSON.parse(r.target_json), state: r.state,
  cancel_requested: !!r.cancel_requested, relay_gated: !!r.relay_gated, updated_at: r.updated_at,
  ...(r.error_code ? { error_code: r.error_code } : {}) });
const sameRelease = (a: NodeRelease | null, b: Row) => a?.kind === 'managed' && a.sha256 === b.sha256
  && a.source_commit === (b.source_commit ?? b.version) && a.version === b.version;

/** Owns authorization and relay handoff facts; the user's computer owns installation. */
export class NodeUpdates {
  constructor(private readonly ctx: ImContext, private readonly directory: string) {}
  private identity(nodeId: string, ownerId?: string): Identity {
    const r = one(this.ctx.db, 'SELECT b.* FROM node_binding_state b JOIN nodes n ON n.node_id=b.node_id AND n.owner_id=b.owner_id WHERE b.node_id=?', nodeId);
    if (!r || ownerId !== undefined && r.owner_id !== ownerId) fail(404, 'Computer not found');
    return r as Identity;
  }
  private latest(id: Identity): Row | undefined {
    return one(this.ctx.db, 'SELECT * FROM node_update_operations WHERE node_id=? AND owner_id=? AND node_epoch=? ORDER BY created_at DESC,rowid DESC LIMIT 1', id.node_id, id.owner_id, id.node_epoch);
  }
  private installation(id: Identity): NodeRelease | null {
    const r = one(this.ctx.db, 'SELECT release_json FROM node_installations WHERE node_id=? AND owner_id=? AND node_epoch=?', id.node_id, id.owner_id, id.node_epoch);
    return r ? JSON.parse(r.release_json) : null;
  }
  /** Persist only the authenticated connection's declared installation identity. */
  register(id: Identity, value: unknown) {
    const v = value as NodeRelease | undefined;
    const release = v && ['managed', 'source'].includes(v.kind) && typeof v.version === 'string'
      && (v.kind === 'source' || typeof v.sha256 === 'string' && /^[a-f0-9]{64}$/.test(v.sha256)
        && typeof v.source_commit === 'string' && /^[a-f0-9]{40}$/.test(v.source_commit)) ? v : null;
    this.ctx.db.prepare('INSERT INTO node_installations VALUES(?,?,?,?,?) ON CONFLICT(node_id) DO UPDATE SET owner_id=excluded.owner_id,node_epoch=excluded.node_epoch,release_json=excluded.release_json,updated_at=excluded.updated_at')
      .run(id.node_id, id.owner_id, id.node_epoch, JSON.stringify(release), now());
  }
  view(node: Row): NodeUpdateView {
    const binding = one(this.ctx.db, 'SELECT * FROM node_binding_state WHERE node_id=? AND owner_id=?', node.node_id, node.owner_id);
    const id = binding as Identity | undefined;
    const current = id ? this.installation(id) : null;
    const latest = id ? this.latest(id) : undefined;
    const operation = latest ? projection(latest) : null;
    const target = releaseManifest(this.directory);
    const installation = current?.kind === 'source' ? 'source' : current?.updater_protocol === 1 ? 'managed' : 'legacy';
    let reason: NodeUpdateView['reason'];
    if (operation && !nodeUpdateTerminal(operation.state)) reason = 'active';
    else if (operation?.relay_gated) reason = 'recovery_required';
    else if (installation !== 'managed') reason = installation;
    else if (!target) reason = 'unpublished';
    else if (!this.ctx.gateway.isOnline(node.node_id)) reason = 'offline';
    else if (sameRelease(current, target)) reason = 'current';
    else if (target.updater_protocol !== 1 || target.data_epoch !== current?.data_epoch) reason = 'incompatible';
    else reason = 'available';
    return { installation, current, target, operation, reason, available: reason === 'available',
      install_command: installMaterials(this.ctx.publicUrl, this.directory).command };
  }
  begin(nodeId: string, ownerId: string, input: Row): NodeUpdateOperation {
    const id = this.identity(nodeId, ownerId);
    if (typeof input.request_id !== 'string' || !input.request_id || input.request_id.length > 100) fail(400, 'request_id required');
    const operation = transaction(this.ctx.db, () => {
      const prior = one(this.ctx.db, 'SELECT o.* FROM node_update_operations o JOIN node_update_requests r ON r.operation_id=o.id WHERE r.node_id=? AND r.owner_id=? AND r.node_epoch=? AND r.request_id=?', nodeId, ownerId, id.node_epoch, input.request_id);
      if (prior) return projection(prior);
      const running = one(this.ctx.db, `SELECT * FROM node_update_operations WHERE node_id=? AND state IN ${active}`, nodeId);
      if (running) {
        if (running.owner_id !== ownerId || running.node_epoch !== id.node_epoch) fail(409, 'Computer identity changed');
        this.ctx.db.prepare('INSERT INTO node_update_requests VALUES(?,?,?,?,?)').run(nodeId, ownerId, id.node_epoch, input.request_id, running.id);
        return projection(running);
      }
      const node = one(this.ctx.db, 'SELECT * FROM nodes WHERE node_id=?', nodeId)!;
      const view = this.view(node);
      if (!view.available || !view.target || !view.current) fail(409, 'Computer update is not available');
      if (input.version !== view.target.version || input.sha256 !== view.target.sha256) fail(409, 'Published version changed; refresh and try again');
      const operationId = randomUUID(); const at = now();
      this.ctx.db.prepare('INSERT INTO node_update_operations(id,request_id,node_id,owner_id,node_epoch,target_json,previous_json,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,\'requested\',?,?)')
        .run(operationId, input.request_id, nodeId, ownerId, id.node_epoch, JSON.stringify(view.target), JSON.stringify(view.current), at, at);
      this.ctx.db.prepare('INSERT INTO node_update_requests VALUES(?,?,?,?,?)').run(nodeId, ownerId, id.node_epoch, input.request_id, operationId);
      return projection(this.latest(id)!);
    });
    if (!nodeUpdateTerminal(operation.state)) this.dispatch(operation);
    this.publish(operation);
    return operation;
  }
  cancel(nodeId: string, ownerId: string, operationId: string): NodeUpdateOperation {
    const id = this.identity(nodeId, ownerId);
    const result = transaction(this.ctx.db, () => {
      const op = this.operation(id, operationId);
      if (op.state === 'cancelled') return op;
      if (!nodeUpdateCancellable(op.state)) fail(409, 'Computer is already switching versions');
      this.ctx.db.prepare('UPDATE node_update_operations SET cancel_requested=1 WHERE id=?').run(op.id);
      return this.operation(id, operationId);
    });
    this.publish(result); return result;
  }
  private operation(id: Identity, operationId: string): NodeUpdateOperation {
    const op = one(this.ctx.db, 'SELECT * FROM node_update_operations WHERE id=? AND node_id=? AND owner_id=? AND node_epoch=?', operationId, id.node_id, id.owner_id, id.node_epoch);
    if (!op) fail(404, 'Update operation not found');
    return projection(op);
  }
  report(id: Identity, input: Row): NodeUpdateReport {
    const current = this.identity(id.node_id);
    if (id.owner_id !== current.owner_id || id.node_epoch !== current.node_epoch) fail(403, 'Computer identity changed');
    let replay = false;
    const operation = transaction(this.ctx.db, () => {
      const op = this.operation(id, input.operation_id);
      let state = op.state, gated = op.relay_gated;
      const action = input.action;
      if (action === 'prepare') {
        if (!['installing', 'waiting'].includes(state) || op.cancel_requested) fail(409, 'Update preparation is no longer authorized');
        state = 'waiting'; gated = true;
      } else if (action === 'resume') {
        if (state !== 'waiting') fail(409, 'Update is not waiting');
        gated = false; replay = true;
      } else if (action === 'claim_switch') {
        if (state !== 'switching' && (state !== 'waiting' || !gated || op.cancel_requested)) fail(409, 'Update switch is no longer authorized');
        state = 'switching';
      } else if (action === 'progress') {
        const transitions: Partial<Record<NodeUpdateState, NodeUpdateState[]>> = {
          requested: ['downloading'], downloading: ['installing'], installing: ['waiting'],
          switching: ['verifying', 'rolling_back'], verifying: ['rolling_back'],
        };
        if (input.state !== state && !transitions[state]?.includes(input.state)) fail(409, 'Invalid update transition');
        state = input.state;
      } else if (action === 'terminal') {
        const next = input.state as NodeUpdateState;
        if (!nodeUpdateTerminal(next)) fail(400, 'Terminal update result required');
        if (nodeUpdateTerminal(state) && state !== next && !['interrupted','recovery_required'].includes(state)) fail(409, 'Update already finished');
        if (next === 'succeeded' || next === 'rolled_back') {
          const expected = next === 'succeeded' ? op.target : JSON.parse(one(this.ctx.db, 'SELECT previous_json FROM node_update_operations WHERE id=?', op.id)!.previous_json);
          if (!this.ctx.gateway.isOnline(id.node_id) || !sameRelease(this.installation(id), expected)) fail(409, 'Expected version has not connected');
          if (next === 'succeeded' && !['switching','verifying','interrupted','recovery_required','succeeded'].includes(state)
            || next === 'rolled_back' && !['rolling_back','interrupted','recovery_required','rolled_back'].includes(state)) fail(409, 'Invalid update completion');
          gated = false; replay = true;
        } else if (next === 'cancelled' || next === 'failed') {
          if (!nodeUpdateCancellable(state) && state !== next) fail(409, 'Update already switched');
          if (gated && input.resumed !== true) fail(409, 'Computer must resume before releasing messages');
          gated = false; replay = true;
        } else if (input.resumed === true) { gated = false; replay = true; }
        state = next;
      } else if (action !== 'poll') fail(400, 'Unknown update action');
      const error = typeof input.error_code === 'string' && ['download_failed','install_failed','start_failed','rollback_failed','worker_lost','update_failed'].includes(input.error_code) ? input.error_code : op.error_code ?? null;
      this.ctx.db.prepare('UPDATE node_update_operations SET state=?,relay_gated=?,error_code=?,updated_at=? WHERE id=?')
        .run(state, +gated, error, now(), op.id);
      return this.operation(id, op.id);
    });
    if (input.action !== 'poll') this.publish(operation);
    if (replay) this.replay(id.node_id);
    return { operation, registered: { online: this.ctx.gateway.isOnline(id.node_id), release: this.installation(id) } };
  }
  /** Admission gate is bound to the current owner/epoch, never just a reused node name. */
  gate(nodeId: string): NodeUpdateOperation | undefined {
    const r = one(this.ctx.db, 'SELECT o.* FROM node_update_operations o JOIN node_binding_state b ON b.node_id=o.node_id AND b.owner_id=o.owner_id AND b.node_epoch=o.node_epoch WHERE o.node_id=? AND o.relay_gated=1 ORDER BY o.created_at DESC,o.rowid DESC LIMIT 1', nodeId);
    return r ? projection(r) : undefined;
  }
  acceptingQueue(nodeId: string): boolean { const op = this.gate(nodeId); return !!op && !nodeUpdateTerminal(op.state); }
  messageWait(messageId: string): 'updating' | 'recovery_required' | null {
    let state: 'updating' | 'recovery_required' | null = null;
    for (const task of all(this.ctx.db, "SELECT target_node_id FROM relay_tasks WHERE message_id=? AND status IN ('queued','sent','accepted')", messageId)) {
      const gate = this.gate(task.target_node_id);
      if (gate) state = nodeUpdateTerminal(gate.state) ? 'recovery_required' : state ?? 'updating';
    }
    return state;
  }
  reconnect(id: Identity) {
    const row = this.latest(id); if (!row) return;
    const op = projection(row);
    // A restored runtime has passed startup and registered with its bound identity.
    if (nodeUpdateTerminal(op.state) && op.relay_gated && this.installation(id)) {
      this.ctx.db.prepare('UPDATE node_update_operations SET relay_gated=0 WHERE id=?').run(op.id);
      this.publish({ ...op, relay_gated: false });
    } else if (nodeUpdateCancellable(op.state)) this.dispatch(op);
  }
  private dispatch(op: NodeUpdateOperation) {
    this.ctx.gateway.send(op.node_id, {type: 'node.update.request', payload: {operation_id: op.id}});
  }
  private replay(nodeId: string) {
    this.ctx.messaging.deliverRelays(all(this.ctx.db, "SELECT * FROM relay_tasks WHERE target_node_id=? AND status IN ('queued','sent','accepted')", nodeId));
  }
  private publish(op: NodeUpdateOperation) {
    this.ctx.gateway.broadcast([op.owner_id], {op: 'event', event_type: 'node.update_changed', data: {node_id: op.node_id}});
    const messages = all(this.ctx.db, "SELECT DISTINCT message_id,conversation_id FROM relay_tasks WHERE target_node_id=? AND status IN ('queued','sent','accepted')", op.node_id);
    for (const message of messages) this.ctx.messaging.event(message.conversation_id, message.message_id, 'node.update_wait_changed', {update_wait: this.messageWait(message.message_id)}, 'pending');
  }
  /** Expire a lost updater without claiming that an unverified runtime has recovered. */
  sweep() {
    for (const row of all(this.ctx.db, `SELECT * FROM node_update_operations WHERE state IN ${active} AND updated_at<?`, new Date(Date.now() - 30000).toISOString())) {
      const state = row.relay_gated ? 'recovery_required' : 'interrupted';
      this.ctx.db.prepare("UPDATE node_update_operations SET state=?,error_code='worker_lost' WHERE id=?").run(state, row.id);
      this.publish({...projection(row), state, error_code: 'worker_lost'});
    }
  }
}

export function registerNodeUpdateRoutes(app: FastifyInstance, ctx: ImContext, directory: string) {
  const updates = ctx.updates = new NodeUpdates(ctx, directory);
  app.post('/im/v1/nodes/:node_id/update', req => updates.begin(params(req).node_id, ctx.identity.authenticateRequest(req).owner_id, body(req)));
  app.post('/im/v1/nodes/:node_id/update/cancel', req => updates.cancel(params(req).node_id, ctx.identity.authenticateRequest(req).owner_id, body(req).operation_id));
  app.post('/im/v1/node-update/report', req => {
    const id = ctx.identity.authenticateRuntime(bearer(req) ?? '');
    if (!id || id.node_id !== body(req).node_id) fail(401, 'Computer authorization required');
    if (body(req).action === 'request_install') {
      const op = updates.begin(id.node_id, id.owner_id, body(req));
      return updates.report(id, {operation_id: op.id, action: 'poll'});
    }
    return updates.report(id, body(req));
  });
}
