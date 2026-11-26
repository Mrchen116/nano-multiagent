import { randomUUID } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent, AgentHandle, AgentOptions } from '@deepseek-ai/dsh-agent';
import { SessionController } from '@deepseek-ai/dsh-api-session-controller';
import { ReasoningEffortId } from '@deepseek-ai/dsh-llm';
import { buildForkSeed, SessionId, SessionLogOffset, SessionSeq, type Session, type SessionHeader } from '@deepseek-ai/dsh-session';
import { SessionPersistenceNotFoundError } from '@deepseek-ai/dsh-session-persistence';
import { SessionQueryError } from '@deepseek-ai/dsh-session-query';
import { foldSubagentDescriptor } from '@deepseek-ai/dsh-subagent';
import { RemoteError } from '@deepseek-ai/dsh-typert-protocol';
import type {} from '@deepseek-ai/dsh-working-directory';
import type { SessionBinding } from './index.js';
import type { ModelRoute } from './model-policy.js';
declare module '@deepseek-ai/cordis' { interface Context { nanoSessions: OwnedSessions } }

function toAgentOptions(route?: ModelRoute): AgentOptions | undefined {
  if (!route) return undefined;
  return {
    provider: route.provider,
    model: route.model,
    ...(route.reasoningEffort ? { reasoningEffort: ReasoningEffortId(route.reasoningEffort) } : {}),
    ...(route.maxTokens !== undefined ? { maxTokens: route.maxTokens } : {}),
  };
}

/** Own product roots and verify native child lineage without bypassing SubagentManager residency. */
export class OwnedSessions {
  private readonly handles = new Map<string, AgentHandle>();
  private readonly pending = new Map<string, Promise<Agent>>();
  private readonly owners = new Map<string, string>();
  constructor(private readonly ctx: Context, private readonly bindings: Map<string, SessionBinding>, private readonly assertEnabled: (agentId: string) => void,
    private readonly markWritable: (binding: SessionBinding) => Promise<unknown>,
    private readonly beforeResume: (binding: SessionBinding, session: Session) => Promise<void>,
    private readonly routeOf: (binding: SessionBinding) => ModelRoute | undefined = () => undefined) {}

  isBound(sessionId: string): boolean { return this.bindings.has(sessionId); }

  /** Create or resume one trusted root, coalescing Schedule and product admission. */
  resolve(sessionId: string, create = false): Promise<Agent> {
    const binding = this.bindings.get(sessionId);
    if (!binding) return Promise.reject(new Error('Session has no trusted product binding'));
    this.assertEnabled(binding.agentId);
    const pending = this.pending.get(sessionId);
    if (pending) return pending;
    return this.admit(sessionId, binding, () => this.activate(binding, create));
  }

  /**
   * Verify an existing native child's lineage under its trusted product root and ensure the root is active.
   *
   * Args:
   *   sessionId: Existing root or native descendant identity; never creates or directly resumes a child outside SubagentManager.
   *   expectedAgentId: Optional product owner to verify before any activation.
   *
   * Returns:
   *   The live Agent (always present for roots; present for children when already resident) and its product root binding.
   */
  async resolveManaged(sessionId: string, expectedAgentId?: string): Promise<{agent: Agent | undefined; root: SessionBinding}> {
    const binding = this.bindings.get(sessionId);
    if (binding) {
      if (expectedAgentId !== undefined && binding.agentId !== expectedAgentId)
        throw new Error('Managed Session belongs to another product Agent');
      this.assertEnabled(binding.agentId);
      const live = this.ctx.agents.get(SessionId(sessionId));
      if (live) this.assertRootHeader(binding, live.session.header);
      return {agent: live ?? await this.resolve(sessionId), root: binding};
    }
    const headers: SessionHeader[] = [], seen = new Set<string>();
    let id = sessionId, childId: string | undefined, root: SessionBinding;
    while (true) {
      if (seen.has(id)) throw new Error('Managed Session lineage contains a cycle');
      seen.add(id);
      using observation = await this.ctx.sessionQuery.observeSession(SessionId(id));
      const header = observation.header, currentBinding = this.bindings.get(id);
      if (header.id !== id) throw new Error('Managed Session identity conflicts with persisted header');
      // Parent catalog facts must be native and child-owned, not a product index.
      if (childId) {
        if (!observation.projections?.values.subagentCatalog?.some(child => child.id === childId))
          throw new Error('Managed Session is absent from its native parent catalog');
        if (headers.at(-1)!.delegationDepth !== (header.delegationDepth ?? 0) + 1)
          throw new Error('Native child delegation depth conflicts with its parent');
      }
      if (currentBinding) {
        if (header.origin === 'subagent' || header.cwd !== currentBinding.cwd || header.agentPreset !== `nano:${currentBinding.agentId}:${currentBinding.revision}`)
          throw new Error('Session binding conflicts with persisted identity');
        root = currentBinding;
        break;
      }
      if (header.origin !== 'subagent' || !header.parentSession) throw new Error('Session has no trusted native child lineage');
      const descriptor = foldSubagentDescriptor(observation.events.slice(observation.inheritedEventCount));
      // A terminal one-shot has no durable composition for a safe cold resume.
      if (!this.ctx.agents.get(SessionId(id)) && descriptor?.mode !== 'continuable')
        throw new Error('Native child has no resumable continuation descriptor');
      headers.push(header);
      childId = id;
      id = header.parentSession;
    }
    if (expectedAgentId !== undefined && root.agentId !== expectedAgentId) throw new Error('Managed Session belongs to another product Agent');
    const preset = `nano:${root.agentId}:${root.revision}`;
    if (headers.some(header => header.agentPreset !== preset || header.cwd !== root.cwd))
      throw new Error('Native child conflicts with its trusted root identity');
    this.assertEnabled(root.agentId);
    const live = this.ctx.agents.get(SessionId(sessionId));
    if (live) return {agent: live, root};
    await this.resolve(root.sessionId);
    this.assertEnabled(root.agentId);
    return {agent: this.ctx.agents.get(SessionId(sessionId)), root};
  }

  private admit(sessionId: string, root: SessionBinding, activate: () => Promise<Agent>): Promise<Agent> {
    const pending = this.pending.get(sessionId);
    if (pending) return pending;
    this.owners.set(sessionId, root.agentId);
    const task = activate().finally(() => {
      this.pending.delete(sessionId);
      if (!this.handles.has(sessionId)) this.owners.delete(sessionId);
    });
    this.pending.set(sessionId, task);
    return task;
  }

  /** Inspect a trusted root at the Node's durable cut without restoring an Agent. */
  async recoveryProbe(sessionId: string, afterSeq: number, localWork: boolean) {
    const binding = this.bindings.get(sessionId);
    if (!binding) throw new Error('Session has no trusted product binding');
    this.assertEnabled(binding.agentId);
    const id = SessionId(sessionId);
    const live = this.ctx.sessions.get(id);
    if (live) return {live: true, unseen: live.seq - 1 > afterSeq};
    if (localWork) return {live: false, unseen: true};
    const handle = await this.ctx.sessionPersistence.open(id, 'read').catch(error => {
      if (!(error instanceof SessionPersistenceNotFoundError)) throw error;
    });
    if (!handle) return {live: false, unseen: false};
    try {
      this.assertRootHeader(binding, handle.header);
      const start = SessionLogOffset(Math.max(afterSeq + 1, handle.inheritedEventCount));
      return {live: false, unseen: (await handle.read(start, 1)).events.length > 0};
    } finally { await handle.close(); }
  }

  private assertRootHeader(binding: SessionBinding, header: SessionHeader): void {
    if (header.id !== binding.sessionId || header.origin === 'subagent' || header.cwd !== binding.cwd ||
      header.agentPreset !== `nano:${binding.agentId}:${binding.revision}`)
      throw new Error('Session binding conflicts with persisted identity');
  }

  private async activate(binding: SessionBinding, create: boolean): Promise<Agent> {
    const live = this.handles.get(binding.sessionId);
    if (live) return live.agent;
    const sessionId = SessionId(binding.sessionId), preset = `nano:${binding.agentId}:${binding.revision}`;
    const stored = await this.ctx.sessionPersistence.stat(sessionId);
    if (!stored && !create) throw new SessionQueryError(`session "${sessionId}" not found`, 'SESSION_QUERY_SESSION_NOT_FOUND');
    if (stored) this.assertRootHeader(binding, stored.header);
    this.assertEnabled(binding.agentId);
    const setup = async (ctx: Context, agent: Agent) => {
      if (stored) {
        this.assertRootHeader(binding, agent.session.header);
        // DSH has already loaded this log and has not yet published the Agent.
        await this.beforeResume(binding, agent.session);
      } else {
        const wd = this.ctx.get('workingDirectory');
        if (wd) {
          await wd.set(agent, binding.cwd, new AbortController().signal);
          for (const msg of [...agent.inbox.nextTurn, ...agent.inbox.nextStep]) {
            if ((msg.source as { kind?: string }).kind === 'working-directory') agent.inbox.remove(msg.id);
          }
        }
      }
      await this.ctx.agentPresets.mount(ctx, preset);
      this.assertEnabled(binding.agentId);
      return {commit: () => this.assertEnabled(binding.agentId)};
    };
    await mkdir(binding.cwd, {recursive: true});
    // A writable root can accept native work before Node sees its first event.
    await this.markWritable(binding);
    this.assertEnabled(binding.agentId);
    const agentOptions = toAgentOptions(this.routeOf(binding));
    const handle = stored
      ? await this.ctx.agents.resume({resumeSessionId: sessionId, ...(agentOptions ? {agentOptions} : {}), setup})
      : await this.ctx.agents.create({sessionId, meta: {cwd: binding.cwd, agentPreset: preset}, ...(agentOptions ? {agentOptions} : {}), setup});
    this.handles.set(sessionId, handle);
    return handle.agent;
  }

  /** Fork through DSH's seed builder while retaining Nano's root ownership without parentSession coupling. */
  async fork(request: {sessionId: SessionId; atSeq?: number}): Promise<{sessionId: SessionId}> {
    const binding = this.bindings.get(request.sessionId);
    if (!binding || request.atSeq === undefined) throw new Error('Fork requires a bound source and exact cut');
    this.assertEnabled(binding.agentId);
    const sessionId = SessionId(`session-${randomUUID()}`);
    using source = await this.ctx.sessionQuery.observeSession(request.sessionId);
    const boundary = SessionSeq(request.atSeq);
    const seed = buildForkSeed(source.events, boundary);
    const preset = source.header.agentPreset!;
    const liveSource = this.ctx.agents.get(request.sessionId);
    const configuredRoute = this.routeOf(binding);
    const currentSelection = liveSource?.model.current();
    const agentOptions: AgentOptions | undefined = currentSelection
      ? {
          provider: currentSelection.provider,
          model: currentSelection.model,
          ...(currentSelection.reasoningEffort ? {reasoningEffort: currentSelection.reasoningEffort} : {}),
          ...(configuredRoute?.maxTokens !== undefined ? {maxTokens: configuredRoute.maxTokens} : {}),
        }
      : toAgentOptions(configuredRoute);
    this.bindings.set(sessionId, {...binding, sessionId});
    this.owners.set(sessionId, binding.agentId);
    const task = this.ctx.agents.create({sessionId, seed, inheritedEventCount: SessionLogOffset(boundary + 1),
      meta: {cwd: binding.cwd, isSeeded: true, agentPreset: preset},
      ...(agentOptions ? {agentOptions} : {}),
      setup: async ctx => { await this.ctx.agentPresets.mount(ctx, preset); this.assertEnabled(binding.agentId); return {commit: () => this.assertEnabled(binding.agentId)}; },
    }).then(handle => { this.handles.set(sessionId, handle); return handle.agent; });
    this.pending.set(sessionId, task);
    try { await task; return {sessionId}; }
    finally {
      this.pending.delete(sessionId);
      if (!this.handles.has(sessionId)) this.owners.delete(sessionId);
    }
  }

  /** Wait for already admitted creation; the caller closes admission before this. */
  async settle(agentId: string): Promise<void> {
    await Promise.allSettled([...this.pending].filter(([id]) => this.owners.get(id) === agentId).map(([, task]) => task));
  }

  /** Dispose all retained handles by their real root owner after admission drains. */
  async disposeAgent(agentId: string): Promise<void> {
    await this.settle(agentId);
    await Promise.all([...this.handles].filter(([id]) => this.owners.get(id) === agentId).map(async ([id, handle]) => {
      await handle.dispose();
      this.handles.delete(id);
      this.owners.delete(id);
    }));
  }
}

/** Native Schedule resolves through the same product owner as explicit inputs; subagents stay owned by SubagentManager. */
export class OwnedSessionController extends SessionController {
  static inject = [...SessionController.inject, 'nanoSessions'];
  private readonly owner: OwnedSessions;
  constructor(ctx: Context, config: ConstructorParameters<typeof SessionController>[1]) { super(ctx, config); this.owner = ctx.nanoSessions; }
  override async resolveAgent(id: SessionId): ReturnType<SessionController['resolveAgent']> {
    if (this.owner.isBound(id)) return {agent: await this.owner.resolve(id)};
    const {agent} = await this.owner.resolveManaged(id);
    if (agent) return {agent};
    return {error: new RemoteError('session/agent-busy', `session "${id}" is owned by subagent routing`, {reason: 'use subagent delivery for this child session'})};
  }
}
