import {rejectDeletedExecution} from './agent-deletion.js';
import { agentAvailable, canAccessSpace, bearer } from "./identity.js";
import { randomBytes, randomUUID } from 'node:crypto';
import type { FastifyInstance } from 'fastify';
import type WebSocket from 'ws';
import { TRAJECTORY_MAX_BYTES, encodeTrajectoryValue, TrajectoryValueDecoder, type TrajectoryRequest, type TrajectoryScope } from '@nano/product-contracts';
import { one, body, params, fail, type ImContext, type Row } from './context.js';
import type { Connection } from './gateway.js';

interface Observer {
  scope: TrajectoryScope;
  browser?: WebSocket;
  browserTicket?: string;
  readyFrame?: Row;
  userId: string;
  sessionId: string;
  device: Connection;
  node?: WebSocket;
  ready: boolean;
  ticket: string;
  timer: NodeJS.Timeout;
  expiresAt: number;
  attachments: Map<string, TrajectoryRequest>;
  reader: TrajectoryValueDecoder;
}

/** Routes ephemeral native reads without storing their payload or joining device ACK work. */
export class TrajectoryObservers {
  private readonly observers = new Map<string, Observer>();
  private readonly tickets = new Map<string, Observer>();
  private readonly pending = new Map<string, Observer>();
  constructor(private readonly ctx: ImContext) {}

  /** Begin an authorized read connection while the browser is still loading. */
  prepare(auth: Row, agentId: string, sessionId: string): { ticket: string; expires_in: number; expires_at: number } {
    const observer = this.create(auth, agentId, sessionId);
    try {
      const ticket = this.ctx.identity.issueTicket(auth.session_id);
      observer.browserTicket = ticket;
      this.pending.set(ticket, observer);
      return { ticket, expires_in: 15, expires_at: observer.expiresAt };
    } catch (error) { this.close(observer.scope.observerId); throw error; }
  }

  browser(socket: WebSocket, ticket: string, agentId: string, sessionId: string): void {
    const auth = this.ctx.identity.consumeTicket(ticket);
    const pending = this.pending.get(ticket);
    if (!auth) { if (pending) this.close(pending.scope.observerId, 1008); socket.close(1008); return; }
    try {
      if (pending && (pending.scope.rootAgentId !== agentId || pending.scope.sessionId !== sessionId
        || pending.userId !== auth.user_id || pending.sessionId !== auth.session_id || !this.valid(pending))) {
        this.close(pending.scope.observerId, 1008);
        throw new Error('该执行不可访问');
      }
      const observer = pending ?? this.create(auth, agentId, sessionId);
      if (pending) { this.pending.delete(ticket); observer.browserTicket = undefined; }
      this.attach(observer, socket);
    } catch (error) {
      if (socket.readyState === 1) socket.send(JSON.stringify({ type: 'failed', message: error instanceof Error ? error.message : '该执行不可访问' }));
      socket.close(1008);
    }
  }

  private create(auth: Row, agentId: string, sessionId: string): Observer {
    rejectDeletedExecution(this.ctx,this.ctx.identity.user(auth.user_id) ?? {},agentId,'session',sessionId);
    const profile = one(this.ctx.db, "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0 AND work_mode='global'", agentId);
    if (!profile || one(this.ctx.db,'SELECT 1 FROM agent_deletions WHERE agent_id=?',agentId) || !agentAvailable(this.ctx.db, profile) || !canAccessSpace(this.ctx.identity.user(auth.user_id), profile.space_id)) throw new Error('该执行不可访问');
    const personal=one(this.ctx.db,"SELECT owner_user_id FROM personal_agent_bindings WHERE agent_id=?",agentId);
    if(personal && personal.owner_user_id!==auth.user_id)throw new Error("该执行不可访问");
    const selected = this.ctx.gateway.work.session(agentId, sessionId);
    if (selected.scope === 'worker') throw new Error('该执行没有原生 DSH 轨迹');
    let root = selected;
    while (root.parent_session_id) root = this.ctx.gateway.work.session(agentId, root.parent_session_id);
    if (root.scope !== 'global_main') throw new Error('该执行不可访问');
    const device = this.ctx.gateway.nodes.get(selected.node_id);
    if (!device || device.socket.readyState !== 1 || !this.ctx.gateway.valid(device)) throw new Error('节点离线，原生轨迹暂不可读取');
    const id = randomUUID(), pairing = randomBytes(32).toString('base64url');
    const expiresAt = Date.now() + 15_000;
    const observer: Observer = { scope: { observerId: id, rootAgentId: agentId, rootSessionId: root.session_id, sessionId, ownerId: profile.owner_id,
      nodeId: device.node_id, nodeEpoch: device.node_epoch }, userId: auth.user_id, sessionId: auth.session_id,
      device, ready: false, ticket: pairing, expiresAt, attachments: new Map(), reader: new TrajectoryValueDecoder(), timer: setTimeout(() => this.close(id, 1013, '观察连接超时'), Math.max(0, expiresAt - Date.now())) };
    this.observers.set(id, observer); this.tickets.set(pairing, observer);
    if (!this.ctx.gateway.send(device.node_id, { type: 'trajectory.prepare', payload: { scope: observer.scope, ticket: pairing } })) {
      this.close(id, 1013, '节点离线'); throw new Error('节点离线，原生轨迹暂不可读取');
    }
    return observer;
  }

  private attach(observer: Observer, socket: WebSocket): void {
    const id = observer.scope.observerId;
    observer.browser = socket;
    this.waitForReady(observer);
    socket.once('close', () => this.close(id));
    socket.on('error', () => this.close(id));
    socket.on('message', raw => {
      if (!this.valid(observer)) { this.close(id, 1008, '访问资格已失效'); return; }
      const size = Array.isArray(raw) ? raw.reduce((total, part) => total + part.byteLength, 0) : raw.byteLength;
      if (size > TRAJECTORY_MAX_BYTES) { this.close(id, 1009, '轨迹请求过大'); return; }
      try {
        const input = JSON.parse(raw.toString()) as TrajectoryRequest;
        if (!observer.ready || !observer.node || !['call', 'open', 'next', 'abort'].includes(input.type)
          || typeof input.requestId !== 'string' || input.requestId.length > 128) throw new Error('invalid observer request');
        if (['call', 'open'].includes(input.type) && !['trajectory/runs', 'session/list', 'session/page', 'session/projections', 'session/attachment', 'session/control', 'session/follow'].includes(input.method ?? '')) {
          this.write(observer, socket, { type: 'error', requestId: input.requestId, code: 'read_only', message: '只允许读取原生轨迹' }); return;
        }
        if (input.type === 'call' && input.method === 'session/attachment') {
          observer.attachments.set(input.requestId, input);
          this.write(observer, observer.node, { type: 'call', requestId: input.requestId, method: 'trajectory/attachment-source', params: input.params }); return;
        }
        // Select transport fields explicitly: the browser cannot assert attachment authorization.
        this.write(observer, observer.node, { type: input.type, requestId: input.requestId, method: input.method, params: input.params, streamId: input.streamId,
          ...(input.type === 'open' && input.initialBatch === true ? { initialBatch: true } : {}) });
      } catch { this.close(id, 1003, '轨迹请求无效'); }
    });
    if (observer.readyFrame) this.write(observer, socket, observer.readyFrame);
  }

  node(socket: WebSocket, ticket: string): void {
    const observer = this.tickets.get(ticket);
    this.tickets.delete(ticket);
    if (!observer || !this.valid(observer) || observer.node) { socket.close(1008); return; }
    observer.node = socket;
    this.waitForReady(observer);
    socket.on('message', raw => {
      const size = Array.isArray(raw) ? raw.reduce((total, part) => total + part.byteLength, 0) : raw.byteLength;
      if (!this.valid(observer)) { this.close(observer.scope.observerId, 1008, '访问资格已失效'); return; }
      if (size > TRAJECTORY_MAX_BYTES) { this.close(observer.scope.observerId, 1009, '轨迹响应过大'); return; }
      try {
        const part = JSON.parse(raw.toString()) as Row;
        if (part.observerId !== observer.scope.observerId) throw new Error('observer mismatch');
        const frame = observer.reader.push(part) as Row | undefined;
        if (!frame) return;
        const attachment = observer.attachments.get(frame.requestId);
        if (attachment) {
          observer.attachments.delete(frame.requestId);
          if (frame.type === 'result') {
            const sources: Row[] = frame.value?.value?.sources ?? [];
            if (sources.some(source => this.attachmentAllowed(observer, source))) {
              this.write(observer, socket, { type: 'call', requestId: attachment.requestId, method: 'session/attachment', params: attachment.params, attachmentAuthorized: true });
            } else if (observer.browser) this.write(observer, observer.browser, { type: 'error', requestId: attachment.requestId, code: 'attachment_forbidden', message: '无法验证附件访问权限' });
            return;
          }
        }
        if (frame.type === 'ready') {
          observer.ready = true; observer.readyFrame = frame;
          if (observer.browser) clearTimeout(observer.timer);
        }
        if (observer.browser) this.write(observer, observer.browser, frame);
      } catch { this.close(observer.scope.observerId, 1003, '轨迹响应无效'); }
    });
    socket.on('error', () => this.close(observer.scope.observerId, 1011, '更新已中断'));
    socket.once('close', () => this.close(observer.scope.observerId, 1011, '更新已中断'));
  }

  private waitForReady(observer: Observer): void {
    if (!observer.browser || !observer.node) return;
    clearTimeout(observer.timer);
    // Pairing only establishes transport; the runtime must still finish its read preparation.
    // Once ready, quiet readers and slow history transfers have no fixed lifetime.
    if (!observer.ready) observer.timer = setTimeout(() => {
      this.close(observer.scope.observerId, 1013, '轨迹读取超时，请重新读取');
    }, 30_000);
  }

  valid(observer: Observer): boolean {
    const profile = one(this.ctx.db, "SELECT * FROM agent_profiles WHERE agent_id=?", observer.scope.rootAgentId);
    if (!profile || one(this.ctx.db,'SELECT 1 FROM agent_deletions WHERE agent_id=?',observer.scope.rootAgentId) || !agentAvailable(this.ctx.db, profile) || profile.owner_id !== observer.scope.ownerId || !canAccessSpace(this.ctx.identity.user(observer.userId), profile.space_id)) return false;
    const personal=one(this.ctx.db,"SELECT owner_user_id FROM personal_agent_bindings WHERE agent_id=?",observer.scope.rootAgentId);
    if(personal && personal.owner_user_id!==observer.userId)return false;
    return this.ctx.gateway.nodes.get(observer.device.node_id) === observer.device && observer.device.socket.readyState === 1
      && this.ctx.gateway.valid(observer.device) && this.ctx.gateway.browserValid(observer);
  }

  check(): void { for (const observer of this.observers.values()) if (!this.valid(observer)) this.close(observer.scope.observerId, 1008, '访问资格已失效'); }
  closeAgent(id: string): void { for (const observer of this.observers.values()) if (observer.scope.rootAgentId === id) this.close(observer.scope.observerId, 1008, '执行记录正在清理'); }
  closeUser(id: string): void { for (const observer of this.observers.values()) if (observer.userId === id) this.close(observer.scope.observerId, 1008, '访问资格已失效'); }
  closeSession(id: string): void { for (const observer of this.observers.values()) if (observer.sessionId === id) this.close(observer.scope.observerId, 1008, '访问资格已失效'); }
  closeDevice(device: Connection): void { for (const observer of this.observers.values()) if (observer.device === device) this.close(observer.scope.observerId, 1011, '节点连接已中断'); }
  shutdown(): void { for (const id of this.observers.keys()) this.close(id, 1001, '服务已停止'); }

  private async write(observer: Observer, socket: WebSocket, frame: unknown): Promise<void> {
    try {
      for (const part of encodeTrajectoryValue(frame)) {
        if (!this.observers.has(observer.scope.observerId) || !this.valid(observer)) return;
        const text = JSON.stringify(part), size = Buffer.byteLength(text);
        if (size > TRAJECTORY_MAX_BYTES || socket.bufferedAmount + size > TRAJECTORY_MAX_BYTES) { this.close(observer.scope.observerId, 1009, '轨迹读取积压'); return; }
        if (socket.readyState !== 1) return;
        await new Promise<void>((resolve, reject) => socket.send(text, error => error ? reject(error) : resolve()));
      }
    } catch { this.close(observer.scope.observerId, 1011, '更新已中断'); }
  }

  private attachmentAllowed(observer: Observer, source: Row): boolean {
    return this.sourceAllowedForUser(observer.userId, source);
  }

  /** Authorize a Desktop local-IPC trajectory read at the Agent/space/PA level without requiring center WorkSync rows. */
  authorizeLocal(auth: { user_id: string; session_id: string }, agentId: string, sessionId: string) {
    const user = this.ctx.identity.user(auth.user_id);
    rejectDeletedExecution(this.ctx, user ?? {}, agentId, 'session', sessionId);
    const profile = one(this.ctx.db, "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0 AND work_mode='global'", agentId);
    if (!profile || one(this.ctx.db, 'SELECT 1 FROM agent_deletions WHERE agent_id=?', agentId) || !agentAvailable(this.ctx.db, profile) || !canAccessSpace(user, profile.space_id)) {
      fail(404, '该执行不可访问');
    }
    const personal = one(this.ctx.db, 'SELECT owner_user_id FROM personal_agent_bindings WHERE agent_id=?', agentId);
    if (personal && personal.owner_user_id !== auth.user_id) {
      fail(404, '该执行不可访问');
    }
    const binding = one(
      this.ctx.db,
      'SELECT b.node_id, b.owner_id, b.node_epoch FROM node_binding_state b JOIN nodes n ON n.node_id=b.node_id AND n.owner_id=b.owner_id WHERE b.node_id=? AND b.owner_id=?',
      profile.node_id,
      profile.owner_id,
    );
    if (!binding) fail(404, '该执行不可访问');
    return {
      authorized: true as const,
      node_id: String(binding.node_id),
      owner_id: String(binding.owner_id),
      node_epoch: Number(binding.node_epoch),
      auth_session_id: auth.session_id,
    };
  }

  /** Authorize a local workspace file open/reveal for any active local Agent (`global` or `single_thread`) owned by the caller. */
  authorizeWorkspaceOpen(userId: string, agentId: string): { authorized: true; owner_id: string } {
    const user = this.ctx.identity.user(userId);
    rejectDeletedExecution(this.ctx, user ?? {}, agentId, 'agent', agentId);
    const profile = one(this.ctx.db, 'SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0', agentId);
    if (!profile || one(this.ctx.db, 'SELECT 1 FROM agent_deletions WHERE agent_id=?', agentId) || !agentAvailable(this.ctx.db, profile) || !canAccessSpace(user, profile.space_id)) {
      fail(403, '无权访问该助手的工作区');
    }
    const personal = one(this.ctx.db, 'SELECT owner_user_id FROM personal_agent_bindings WHERE agent_id=?', agentId);
    if (personal && personal.owner_user_id !== userId) {
      fail(403, '无权访问该助手的工作区');
    }
    const callerOwnerId = String(user?.owner_id ?? userId);
    if (String(profile.owner_id) !== callerOwnerId) {
      fail(403, '仅该电脑归属者可直接打开本机工作区文件');
    }
    return { authorized: true, owner_id: String(profile.owner_id) };
  }

  /** Verify whether a viewer can read trajectory attachment sources originating from workspace or chat messages. */
  authorizeAttachmentSources(userId: string, agentId: string, sources: unknown): { allowed: boolean } {
    if (!Array.isArray(sources) || sources.length === 0) return { allowed: false };
    const user = this.ctx.identity.user(userId);
    const profile = one(this.ctx.db, "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0 AND work_mode='global'", agentId);
    if (!profile || one(this.ctx.db, 'SELECT 1 FROM agent_deletions WHERE agent_id=?', agentId) || !agentAvailable(this.ctx.db, profile) || !canAccessSpace(user, profile.space_id)) {
      return { allowed: false };
    }
    const personal = one(this.ctx.db, 'SELECT owner_user_id FROM personal_agent_bindings WHERE agent_id=?', agentId);
    if (personal && personal.owner_user_id !== userId) return { allowed: false };
    const allowed = sources.some(source => Boolean(source && typeof source === 'object' && this.sourceAllowedForUser(userId, source as Row)));
    return { allowed };
  }

  private sourceAllowedForUser(userId: string, source: Row): boolean {
    if (source.kind === 'workspace') return true;
    if (source.kind !== 'chat' || typeof source.url !== 'string') return false;
    try {
      this.ctx.messaging.access({ id: userId }, source.conversationId);
      const url = new URL(source.url, this.ctx.publicUrl);
      if (url.origin !== new URL(this.ctx.publicUrl).origin) return false;
      const match = /^\/im\/v1\/conversations\/([^/]+)\/(?:images|attachments)\/([^/]+)$/.exec(url.pathname);
      if (!match || decodeURIComponent(match[1]!) !== source.conversationId) return false;
      const message = one(this.ctx.db, 'SELECT attachments_json FROM messages WHERE id=? AND conversation_id=?', source.messageId, source.conversationId);
      return Boolean(message && JSON.parse(message.attachments_json).some((attachment: Row) => new URL(attachment.url, this.ctx.publicUrl).pathname === url.pathname)
        && one(this.ctx.db, 'SELECT 1 FROM message_images WHERE conversation_id=? AND image_id=?', source.conversationId, decodeURIComponent(match[2]!)));
    } catch { return false; }
  }

  private close(id: string, code = 1000, reason = ''): void {
    const observer = this.observers.get(id);
    if (!observer) return;
    this.observers.delete(id); this.tickets.delete(observer.ticket); clearTimeout(observer.timer);
    if (observer.browserTicket) { this.pending.delete(observer.browserTicket); this.ctx.identity.consumeTicket(observer.browserTicket); }
    observer.reader.clear();
    observer.browser?.close(code, reason); observer.node?.close(code, reason);
    if (this.ctx.gateway.nodes.get(observer.device.node_id) === observer.device)
      this.ctx.gateway.send(observer.device.node_id, { type: 'trajectory.close', payload: { observer_id: id } });
  }
}

export function registerTrajectorySockets(app: FastifyInstance, ctx: ImContext): void {
  app.post('/im/v1/agents/:agent_id/trajectory/prepare', (request) => {
    const user = ctx.identity.authenticateRequest(request);
    const session = ctx.identity.accessSession(bearer(request));
    const sessionId = body(request).session_id;
    if (typeof sessionId !== 'string' || !sessionId) fail(422, 'session_id required');
    rejectDeletedExecution(ctx,user,params(request).agent_id,'session',sessionId);
    ctx.identity.rateLimit('ws-ticket:' + session.sid, 10, 60);
    try { return ctx.gateway.trajectory.prepare({ user_id: user.id, session_id: session.sid }, params(request).agent_id, sessionId); }
    catch { fail(404, '该执行不可访问或节点离线'); }
  });
  app.post('/im/v1/agents/:agent_id/trajectory/authorize', (request) => {
    const user = ctx.identity.authenticateRequest(request);
    const session = ctx.identity.accessSession(bearer(request));
    const sessionId = body(request).session_id;
    if (typeof sessionId !== 'string' || !sessionId) fail(422, 'session_id required');
    return ctx.gateway.trajectory.authorizeLocal({ user_id: user.id, session_id: session.sid }, params(request).agent_id, sessionId);
  });
  app.post('/im/v1/agents/:agent_id/trajectory/authorize-attachment', (request) => {
    const user = ctx.identity.authenticateRequest(request);
    return ctx.gateway.trajectory.authorizeAttachmentSources(user.id, params(request).agent_id, body(request).sources);
  });
  app.post('/im/v1/agents/:agent_id/workspace/authorize', (request) => {
    const user = ctx.identity.authenticateRequest(request);
    return ctx.gateway.trajectory.authorizeWorkspaceOpen(user.id, params(request).agent_id);
  });
  app.get('/im/ws/agent-trajectory', { websocket: true }, (socket, request) => {
    const allowed = [new URL(ctx.publicUrl).origin, ...(process.env.IM_BROWSER_ORIGINS ?? '').split(',').map(value => value.trim())];
    if (!allowed.includes(request.headers.origin ?? '')) { socket.close(1008); return; }
    const query = request.query as Row;
    ctx.gateway.trajectory.browser(socket, query.ticket ?? '', query.agent_id ?? '', query.session_id ?? '');
  });
  app.get('/im/ws/node-trajectory', { websocket: true }, (socket, request) => {
    ctx.gateway.trajectory.node(socket, (request.query as Row).ticket ?? '');
  });
}
