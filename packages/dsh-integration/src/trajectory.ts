import { randomUUID } from 'node:crypto';
import type { Context } from '@deepseek-ai/cordis';
import { SessionId } from '@deepseek-ai/dsh-session';
import type { SessionController } from '@deepseek-ai/dsh-api-session-controller';
import type { SessionAddress, SessionFollowRequest, SessionProjectionValues } from '@deepseek-ai/dsh-api-session-controller/types';
import { TRAJECTORY_VERSION, type TrajectoryScope } from '@nano/product-contracts';
import type { AgentConfiguration, SessionBinding } from './index.js';
import type { RpcPeer } from './rpc.js';
import { TrajectoryStream } from './trajectory-stream.js';
import { withoutInlineImages } from './trajectory-attachments.js';

interface Observer {
  scope: TrajectoryScope;
  address: SessionAddress;
  controller: AbortController;
  streams: Map<string, TrajectoryStream>;
  cursor: number;
}
type Request = { observerId: string; method: string; params?: { args?: { request?: Record<string, any> } }; streamId?: string; attachmentAuthorized?: boolean };

/** Owns the native read boundary; callers cannot acquire an Agent through this service. */
export class NativeTrajectory {
  private readonly observers = new Map<string, Observer>();

  constructor(private readonly ctx: Context, private readonly options: {
    controller: Promise<SessionController>;
    bindings: Map<string, SessionBinding>;
    configurations: Map<string, AgentConfiguration>;
  }) {}

  /** Register the private carrier operations with the existing runtime peer. */
  register(peer: RpcPeer): void {
    peer.handle('trajectory.prepare', value => this.prepare(value as TrajectoryScope));
    peer.handle('trajectory.call', value => this.call(value as Request));
    peer.handle('trajectory.open', value => this.open(value as Request));
    peer.handle('trajectory.next', value => {
      const request = value as Request;
      return this.stream(request).next();
    });
    peer.handle('trajectory.abort', value => {
      const request = value as Request, observer = this.observer(request.observerId);
      observer.streams.get(request.streamId!)?.close();
      observer.streams.delete(request.streamId!);
      return {};
    });
    peer.handle('trajectory.close', value => { this.close((value as Request).observerId); return {}; });
    this.ctx.effect(() => () => this.dispose());
  }

  /** Check the trusted global binding and the persisted native parent chain. */
  async prepare(scope: TrajectoryScope) {
    const binding = this.options.bindings.get(scope.rootSessionId);
    const config = binding && this.options.configurations.get(`nano:${binding.agentId}:${binding.revision}`);
    if (!binding || binding.agentId !== scope.rootAgentId || binding.ownerId !== scope.ownerId || config?.mode !== 'global') throw new Error('trajectory_scope_not_allowed');
    const controller = new AbortController();
    using selected = await this.ctx.sessionQuery.observeSession(SessionId(scope.sessionId), { signal: controller.signal });
    let current = selected.header;
    const visited = new Set<string>();
    while (current.id !== scope.rootSessionId) {
      if (!current.parentSession || visited.has(current.id)) throw new Error('trajectory_scope_not_allowed');
      visited.add(current.id);
      using parent = await this.ctx.sessionQuery.observeSession(current.parentSession, { signal: controller.signal, projectionMode: 'none' });
      current = parent.header;
    }
    const address: SessionAddress = selected.header.origin === 'subagent' && selected.header.parentSession
      ? { kind: 'subagent', parentSessionId: selected.header.parentSession, childSessionId: selected.header.id, mode: 'unknown' }
      : { kind: 'session', sessionId: selected.header.id };
    this.close(scope.observerId);
    this.observers.set(scope.observerId, { scope, address, controller, streams: new Map(), cursor: -1 });
    return { version: TRAJECTORY_VERSION };
  }

  /** Read one official DTO under a fixed session identity. */
  async call(request: Request): Promise<unknown> {
    const observer = this.observer(request.observerId), signal = observer.controller.signal;
    const controller = await this.options.controller;
    const args = this.arguments(observer, request);
    let value: unknown;
    if (request.method === 'session/list') {
      using cut = await this.ctx.sessionQuery.observeSession(SessionId(observer.scope.sessionId), { signal });
      const agent = this.ctx.agents.get(cut.header.id);
      value = { items: [{ sessionId: cut.header.id, agentAvailable: Boolean(agent), running: agent?.status === 'running', blank: cut.cursor < 0,
        updatedAt: cut.header.createdAt, cwd: cut.header.cwd, origin: cut.header.origin, parentSessionId: cut.header.parentSession,
        projections: { kind: 'sequenced', asOfSeq: cut.cursor, values: cut.projections?.values ?? {} } }] };
    } else if (request.method === 'session/projections') {
      value = await controller.projections({ sessionId: SessionId(observer.scope.sessionId) }, signal);
    } else if (request.method === 'session/page') {
      if (!Number.isInteger(args.throughSeq) || args.throughSeq > observer.cursor) throw new Error('trajectory_invalid_history_cut');
      value = await controller.page({ ...this.window(args), address: observer.address, throughSeq: args.throughSeq, beforeSeq: args.beforeSeq }, signal);
    } else if (request.method === 'trajectory/attachment-source') {
      const sources = [];
      let sessionId = observer.scope.sessionId;
      // Native child histories may inherit an attachment from their authorized parent.
      while (true) {
        sources.push(...await this.ctx.nanoTrajectoryAttachments.read(sessionId, String(args.attachmentId)));
        if (sessionId === observer.scope.rootSessionId) break;
        using parent = await this.ctx.sessionQuery.observeSession(SessionId(sessionId), { signal, projectionMode: 'none' });
        if (!parent.header.parentSession) break;
        sessionId = parent.header.parentSession;
      }
      value = { sources };
    } else if (request.method === 'session/attachment') {
      if (!request.attachmentAuthorized) throw new Error('无法验证附件访问权限');
      value = await controller.attachment({ sessionId: SessionId(observer.scope.sessionId), attachmentId: args.attachmentId });
    } else throw new Error('trajectory_read_only_method_required');
    signal.throwIfAborted();
    return { ok: true, value: request.method === 'session/attachment' ? value : withoutInlineImages(value) };
  }

  /** Open one official native stream; reads use bounded, explicitly pulled batches. */
  async open(request: Request) {
    const observer = this.observer(request.observerId), args = this.arguments(observer, request);
    if (!['session/follow', 'session/control'].includes(request.method)) throw new Error('trajectory_read_only_method_required');
    const streamId = randomUUID();
    const stream = new TrajectoryStream(signal => request.method === 'session/follow'
      ? this.follow(observer, { ...this.window(args), address: observer.address, assistantStream: true }, signal)
      : this.control(observer, signal));
    observer.streams.set(streamId, stream);
    return { streamId };
  }

  close(id: string): void {
    const observer = this.observers.get(id);
    if (!observer) return;
    this.observers.delete(id);
    observer.controller.abort();
    for (const stream of observer.streams.values()) stream.close();
    observer.streams.clear();
  }

  dispose(): void { for (const id of this.observers.keys()) this.close(id); }

  private observer(id: string): Observer {
    const observer = this.observers.get(id);
    if (!observer) throw new Error('trajectory_observer_closed');
    return observer;
  }

  private stream(request: Request) {
    const stream = this.observer(request.observerId).streams.get(request.streamId!);
    if (!stream) throw new Error('trajectory_stream_closed');
    return stream;
  }

  private arguments(observer: Observer, request: Request) {
    const args = request.params?.args?.request ?? {};
    const target = args.sessionId ?? args.address?.sessionId ?? args.address?.childSessionId;
    if (target !== undefined && target !== observer.scope.sessionId) throw new Error('trajectory_scope_not_allowed');
    return args;
  }

  private window(args: Record<string, any>) {
    const maxMessages = args.maxMessages ?? 500;
    if (!Number.isInteger(maxMessages) || maxMessages < 1 || maxMessages > 500) throw new Error('trajectory_invalid_window');
    return { maxMessages, ...(args.turnWindow ? { turnWindow: args.turnWindow } : {}) };
  }

  private async *control(observer: Observer, signal: AbortSignal) {
    const controller = await this.options.controller;
    for await (const frame of controller.control(signal)) {
      if (frame.type === 'baseline') yield withoutInlineImages({ ...frame, value: { projections: { [observer.scope.sessionId]: frame.value.projections[SessionId(observer.scope.sessionId)] ?? { asOfSeq: -1, values: {} } } } });
      else if (frame.sessionId === observer.scope.sessionId) yield withoutInlineImages(frame);
    }
  }

  private async *follow(observer: Observer, request: SessionFollowRequest, signal: AbortSignal): AsyncIterable<unknown> {
    const controller = await this.options.controller, id = SessionId(observer.scope.sessionId);
    let changed = false, wake: (() => void) | undefined;
    const generation = new AbortController();
    const changedGeneration = () => { changed = true; generation.abort(); wake?.(); };
    // Subscribe before taking the cut so normal product activation cannot fall into a gap.
    const created = this.ctx.on('session/created', session => { if (session.id === id) changedGeneration(); }, { global: true });
    const disposed = this.ctx.on('session/disposed', session => { if (session.id === id) changedGeneration(); }, { global: true });
    const onAbort = () => wake?.();
    signal.addEventListener('abort', onAbort, { once: true });
    try {
      const live = this.ctx.sessions.get(id);
      if (live) {
        const iterator = controller.follow(request, AbortSignal.any([signal, generation.signal]))[Symbol.asyncIterator]();
        try {
          const first = await iterator.next();
          if (this.ctx.sessions.get(id) !== live || changed) throw new Error('generation_changed');
          if (first.done) return;
          if (first.value.type === 'snapshot') observer.cursor = first.value.cursor;
          yield withoutInlineImages(first.value);
          while (!signal.aborted) {
            if (changed) throw new Error('generation_changed');
            const next = await iterator.next();
            if (changed) throw new Error('generation_changed');
            if (next.done) return;
            if (next.value.type === 'event') observer.cursor = next.value.event.seq;
            yield withoutInlineImages(next.value);
          }
        } finally { await iterator.return?.(); }
      } else {
        using cut = await this.ctx.sessionQuery.observeSession(id, { signal });
        if (changed || this.ctx.sessions.get(id)) throw new Error('generation_changed');
        const page = await controller.page({ ...this.window(request), address: observer.address, throughSeq: cut.cursor }, signal);
        if (changed || this.ctx.sessions.get(id)) throw new Error('generation_changed');
        observer.cursor = cut.cursor;
        yield withoutInlineImages({ type: 'snapshot', header: cut.header, cursor: cut.cursor, ...page,
          projections: { asOfSeq: cut.cursor, values: (cut.projections?.values ?? {}) as SessionProjectionValues }, assistantStream: { revision: 0 } });
        if (!changed && !signal.aborted) await new Promise<void>(resolve => { wake = resolve; });
        if (changed && !signal.aborted) throw new Error('generation_changed');
      }
    } finally { created(); disposed(); signal.removeEventListener('abort', onAbort); }
  }
}
