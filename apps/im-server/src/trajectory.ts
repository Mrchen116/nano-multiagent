import { agentAvailable, canAccessSpace } from "./identity.js";
import { randomBytes, randomUUID } from 'node:crypto';
import type { FastifyInstance } from 'fastify';
import type WebSocket from 'ws';
import { TRAJECTORY_MAX_BYTES, type TrajectoryRequest, type TrajectoryScope } from '@nano/product-contracts';
import { one, type ImContext, type Row } from './context.js';
import type { Connection } from './gateway.js';

interface Observer {
  scope: TrajectoryScope;
  browser: WebSocket;
  userId: string;
  sessionId: string;
  device: Connection;
  node?: WebSocket;
  ready: boolean;
  ticket: string;
  timer: NodeJS.Timeout;
  attachments: Map<string, TrajectoryRequest>;
}

/** Routes ephemeral native reads without storing their payload or joining device ACK work. */
export class TrajectoryObservers {
  private readonly observers = new Map<string, Observer>();
  private readonly tickets = new Map<string, Observer>();
  constructor(private readonly ctx: ImContext) {}

  browser(socket: WebSocket, ticket: string, agentId: string, sessionId: string): void {
    const auth = this.ctx.identity.consumeTicket(ticket);
    if (!auth) { socket.close(1008); return; }
    try {
      const profile = one(this.ctx.db, "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0 AND work_mode='global'", agentId);
      if (!profile || !agentAvailable(this.ctx.db, profile) || !canAccessSpace(this.ctx.identity.user(auth.user_id), profile.space_id)) throw new Error('该执行不可访问');
      const selected = this.ctx.gateway.work.session(agentId, sessionId);
      let root = selected;
      while (root.parent_session_id) root = this.ctx.gateway.work.session(agentId, root.parent_session_id);
      if (root.scope !== 'global_main') throw new Error('该执行不可访问');
      const device = this.ctx.gateway.nodes.get(selected.node_id);
      if (!device || device.socket.readyState !== 1 || !this.ctx.gateway.valid(device)) throw new Error('节点离线，原生轨迹暂不可读取');
      const id = randomUUID(), pairing = randomBytes(32).toString('base64url');
      const observer: Observer = { scope: { observerId: id, rootAgentId: agentId, rootSessionId: root.session_id, sessionId, ownerId: profile.owner_id,
        nodeId: device.node_id, nodeEpoch: device.node_epoch }, browser: socket, userId: auth.user_id, sessionId: auth.session_id,
        device, ready: false, ticket: pairing, attachments: new Map(), timer: setTimeout(() => this.close(id, 1013, '观察连接超时'), 60_000) };
      this.observers.set(id, observer); this.tickets.set(pairing, observer);
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
          this.write(observer, observer.node, { type: input.type, requestId: input.requestId, method: input.method, params: input.params, streamId: input.streamId });
        } catch { this.close(id, 1003, '轨迹请求无效'); }
      });
      if (!this.ctx.gateway.send(device.node_id, { type: 'trajectory.prepare', payload: { scope: observer.scope, ticket: pairing } })) this.close(id, 1013, '节点离线');
    } catch (error) {
      socket.send(JSON.stringify({ type: 'failed', message: error instanceof Error ? error.message : '该执行不可访问' }));
      socket.close(1008);
    }
  }

  node(socket: WebSocket, ticket: string): void {
    const observer = this.tickets.get(ticket);
    this.tickets.delete(ticket);
    if (!observer || !this.valid(observer) || observer.node) { socket.close(1008); return; }
    clearTimeout(observer.timer);
    observer.node = socket;
    socket.on('message', raw => {
      const size = Array.isArray(raw) ? raw.reduce((total, part) => total + part.byteLength, 0) : raw.byteLength;
      if (!this.valid(observer)) { this.close(observer.scope.observerId, 1008, '访问资格已失效'); return; }
      if (size > TRAJECTORY_MAX_BYTES) { this.close(observer.scope.observerId, 1009, '轨迹响应过大'); return; }
      try {
        const frame = JSON.parse(raw.toString()) as Row;
        if (frame.observerId !== observer.scope.observerId) throw new Error('observer mismatch');
        const attachment = observer.attachments.get(frame.requestId);
        if (attachment) {
          observer.attachments.delete(frame.requestId);
          if (frame.type === 'result') {
            const sources: Row[] = frame.value?.value?.sources ?? [];
            if (sources.some(source => this.attachmentAllowed(observer, source))) {
              this.write(observer, socket, { type: 'call', requestId: attachment.requestId, method: 'session/attachment', params: attachment.params, attachmentAuthorized: true });
            } else this.write(observer, observer.browser, { type: 'error', requestId: attachment.requestId, code: 'attachment_forbidden', message: '无法验证附件访问权限' });
            return;
          }
        }
        if (frame.type === 'ready') observer.ready = true;
        this.write(observer, observer.browser, frame);
      } catch { this.close(observer.scope.observerId, 1003, '轨迹响应无效'); }
    });
    socket.on('error', () => this.close(observer.scope.observerId, 1011, '更新已中断'));
    socket.once('close', () => this.close(observer.scope.observerId, 1011, '更新已中断'));
  }

  valid(observer: Observer): boolean {
    const profile = one(this.ctx.db, "SELECT * FROM agent_profiles WHERE agent_id=?", observer.scope.rootAgentId);
    if (!profile || !agentAvailable(this.ctx.db, profile) || profile.owner_id !== observer.scope.ownerId || !canAccessSpace(this.ctx.identity.user(observer.userId), profile.space_id)) return false;
    return this.ctx.gateway.nodes.get(observer.device.node_id) === observer.device && observer.device.socket.readyState === 1
      && this.ctx.gateway.valid(observer.device) && this.ctx.gateway.browserValid(observer);
  }

  check(): void { for (const observer of this.observers.values()) if (!this.valid(observer)) this.close(observer.scope.observerId, 1008, '访问资格已失效'); }
  closeUser(id: string): void { for (const observer of this.observers.values()) if (observer.userId === id) this.close(observer.scope.observerId, 1008, '访问资格已失效'); }
  closeSession(id: string): void { for (const observer of this.observers.values()) if (observer.sessionId === id) this.close(observer.scope.observerId, 1008, '访问资格已失效'); }
  closeDevice(device: Connection): void { for (const observer of this.observers.values()) if (observer.device === device) this.close(observer.scope.observerId, 1011, '节点连接已中断'); }
  shutdown(): void { for (const id of this.observers.keys()) this.close(id, 1001, '服务已停止'); }

  private write(observer: Observer, socket: WebSocket, frame: unknown): void {
    const text = JSON.stringify(frame), size = Buffer.byteLength(text);
    if (size > TRAJECTORY_MAX_BYTES || socket.bufferedAmount + size > TRAJECTORY_MAX_BYTES) { this.close(observer.scope.observerId, 1009, '轨迹读取积压'); return; }
    if (socket.readyState === 1) socket.send(text);
  }

  private attachmentAllowed(observer: Observer, source: Row): boolean {
    if (source.kind === 'workspace') return true;
    if (source.kind !== 'chat' || typeof source.url !== 'string') return false;
    try {
      this.ctx.messaging.access({ id: observer.userId }, source.conversationId);
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
    observer.browser.close(code, reason); observer.node?.close(code, reason);
    if (this.ctx.gateway.nodes.get(observer.device.node_id) === observer.device)
      this.ctx.gateway.send(observer.device.node_id, { type: 'trajectory.close', payload: { observer_id: id } });
  }
}

export function registerTrajectorySockets(app: FastifyInstance, ctx: ImContext): void {
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
