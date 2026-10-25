import { randomUUID } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent, AgentHandle } from '@deepseek-ai/dsh-agent';
import { SessionController } from '@deepseek-ai/dsh-api-session-controller';
import { buildForkSeed, SessionId, SessionLogOffset, SessionSeq } from '@deepseek-ai/dsh-session';
import { SessionQueryError } from '@deepseek-ai/dsh-session-query';
import type { SessionBinding } from './index.js';
declare module '@deepseek-ai/cordis' { interface Context { nanoSessions: OwnedSessions } }

/** Hold the public disposal capability for every product root, including forks. */
export class OwnedSessions {
  private readonly handles = new Map<string, AgentHandle>();
  private readonly pending = new Map<string, Promise<Agent>>();
  constructor(private readonly ctx: Context, private readonly bindings: Map<string, SessionBinding>, private readonly assertEnabled: (agentId: string) => void) {}

  /** Create or resume one trusted root, coalescing Schedule and product admission. */
  resolve(sessionId: string, create = false): Promise<Agent> {
    const binding = this.bindings.get(sessionId);
    if (!binding) return Promise.reject(new Error('Session has no trusted product binding'));
    this.assertEnabled(binding.agentId);
    const pending = this.pending.get(sessionId);
    if (pending) return pending;
    const task = this.activate(binding, create).finally(() => this.pending.delete(sessionId));
    this.pending.set(sessionId, task);
    return task;
  }

  private async activate(binding: SessionBinding, create: boolean): Promise<Agent> {
    const live = this.handles.get(binding.sessionId);
    if (live) return live.agent;
    const sessionId = SessionId(binding.sessionId), preset = `nano:${binding.agentId}:${binding.revision}`;
    let exists = true;
    try {
      using observation = await this.ctx.sessionQuery.observeSession(sessionId);
      if (observation.header.origin === 'subagent' || observation.header.cwd !== binding.cwd || observation.header.agentPreset !== preset)
        throw new Error('Session binding conflicts with persisted identity');
    } catch (error) {
      if (!create || !(error instanceof SessionQueryError) || error.code !== 'SESSION_QUERY_SESSION_NOT_FOUND') throw error;
      exists = false;
    }
    this.assertEnabled(binding.agentId);
    const setup = async (ctx: Context) => { await this.ctx.agentPresets.mount(ctx, preset); this.assertEnabled(binding.agentId); };
    await mkdir(binding.cwd, {recursive: true});
    const handle = exists
      ? await this.ctx.agents.resume({resumeSessionId: sessionId, setup})
      : await this.ctx.agents.create({sessionId, meta: {cwd: binding.cwd, agentPreset: preset}, setup});
    this.handles.set(sessionId, handle);
    return handle.agent;
  }

  /** Fork through DSH's seed builder while retaining Nano's root ownership. */
  async fork(request: {sessionId: SessionId; atSeq?: number}): Promise<{sessionId: SessionId}> {
    const binding = this.bindings.get(request.sessionId);
    if (!binding || request.atSeq === undefined) throw new Error('Fork requires a bound source and exact cut');
    this.assertEnabled(binding.agentId);
    const sessionId = SessionId(`session-${randomUUID()}`);
    using source = await this.ctx.sessionQuery.observeSession(request.sessionId);
    const boundary = SessionSeq(request.atSeq);
    const seed = buildForkSeed(source.events, boundary);
    const preset = source.header.agentPreset!;
    this.bindings.set(sessionId, {...binding, sessionId});
    const task = this.ctx.agents.create({sessionId, seed, inheritedEventCount: SessionLogOffset(boundary + 1),
      meta: {cwd: binding.cwd, parentSession: request.sessionId, isSeeded: true, agentPreset: preset},
      setup: async ctx => { await this.ctx.agentPresets.mount(ctx, preset); this.assertEnabled(binding.agentId); },
    }).then(handle => { this.handles.set(sessionId, handle); return handle.agent; });
    this.pending.set(sessionId, task);
    try { await task; return {sessionId}; }
    finally { this.pending.delete(sessionId); }
  }

  /** Wait for already admitted creation; the caller closes admission before this. */
  async settle(agentId: string): Promise<void> {
    await Promise.allSettled([...this.pending].filter(([id]) => this.bindings.get(id)?.agentId === agentId).map(([, task]) => task));
  }

  /** Dispose roots after native descendant admission has been drained. */
  async disposeAgent(agentId: string): Promise<void> {
    await this.settle(agentId);
    await Promise.all([...this.handles].filter(([id]) => this.bindings.get(id)?.agentId === agentId).map(async ([id, handle]) => {
      await handle.dispose();
      this.handles.delete(id);
    }));
  }
}

/** Native Schedule resolves through the same product owner as explicit inputs. */
export class OwnedSessionController extends SessionController {
  static inject = [...SessionController.inject, 'nanoSessions'];
  private readonly owner: OwnedSessions;
  constructor(ctx: Context, config: ConstructorParameters<typeof SessionController>[1]) { super(ctx, config); this.owner = ctx.nanoSessions; }
  override async resolveAgent(id: SessionId): ReturnType<SessionController['resolveAgent']> { return {agent: await this.owner.resolve(id)}; }
}
