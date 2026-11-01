import { randomUUID } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent, AgentHandle } from '@deepseek-ai/dsh-agent';
import { SessionController } from '@deepseek-ai/dsh-api-session-controller';
import { buildForkSeed, SessionId, SessionLogOffset, SessionSeq, type SessionHeader } from '@deepseek-ai/dsh-session';
import { SessionQueryError } from '@deepseek-ai/dsh-session-query';
import { applyChildComposition, foldSubagentDescriptor, type ContinuableSubagentDescriptorData } from '@deepseek-ai/dsh-subagent';
import type { SessionBinding } from './index.js';
declare module '@deepseek-ai/cordis' { interface Context { nanoSessions: OwnedSessions } }

interface ManagedChild { header: SessionHeader; descriptor?: ContinuableSubagentDescriptorData }

/** Own product roots and explicitly recovered native children without rebinding them. */
export class OwnedSessions {
  private readonly handles = new Map<string, AgentHandle>();
  private readonly pending = new Map<string, Promise<Agent>>();
  private readonly owners = new Map<string, string>();
  constructor(private readonly ctx: Context, private readonly bindings: Map<string, SessionBinding>, private readonly assertEnabled: (agentId: string) => void) {}

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
   * Recover an existing native child only through its trusted product root.
   *
   * Args:
   *   sessionId: Existing root or native descendant identity; never creates a child.
   *   expectedAgentId: Optional product owner to verify before any activation.
   *
   * Returns:
   *   The original Agent and its product root binding, without binding the child.
   *
   * Throws:
   *   Error: Lineage, persisted composition or enabled lifecycle cannot be proven.
   */
  async resolveManaged(sessionId: string, expectedAgentId?: string): Promise<{agent: Agent; root: SessionBinding}> {
    const children: ManagedChild[] = [], seen = new Set<string>();
    let id = sessionId, childId: string | undefined, root: SessionBinding;
    while (true) {
      if (seen.has(id)) throw new Error('Managed Session lineage contains a cycle');
      seen.add(id);
      using observation = await this.ctx.sessionQuery.observeSession(SessionId(id));
      const header = observation.header, binding = this.bindings.get(id);
      if (header.id !== id) throw new Error('Managed Session identity conflicts with persisted header');
      // Parent catalog facts must be native and child-owned, not a product index.
      if (childId) {
        if (!observation.projections?.values.subagentCatalog?.some(child => child.id === childId))
          throw new Error('Managed Session is absent from its native parent catalog');
        if (children.at(-1)!.header.delegationDepth !== (header.delegationDepth ?? 0) + 1)
          throw new Error('Native child delegation depth conflicts with its parent');
      }
      if (binding) {
        if (header.origin === 'subagent' || header.cwd !== binding.cwd || header.agentPreset !== `nano:${binding.agentId}:${binding.revision}`)
          throw new Error('Session binding conflicts with persisted identity');
        root = binding;
        break;
      }
      if (header.origin !== 'subagent' || !header.parentSession) throw new Error('Session has no trusted native child lineage');
      const descriptor = foldSubagentDescriptor(observation.events.slice(observation.inheritedEventCount));
      // A terminal one-shot has no durable composition for a safe cold resume.
      if (!this.ctx.agents.get(SessionId(id)) && descriptor?.mode !== 'continuable')
        throw new Error('Native child has no resumable continuation descriptor');
      children.push({header, descriptor: descriptor?.mode === 'continuable' ? descriptor : undefined});
      childId = id;
      id = header.parentSession;
    }
    if (expectedAgentId !== undefined && root.agentId !== expectedAgentId) throw new Error('Managed Session belongs to another product Agent');
    const preset = `nano:${root.agentId}:${root.revision}`;
    if (children.some(child => child.header.agentPreset !== preset || child.header.cwd !== root.cwd))
      throw new Error('Native child conflicts with its trusted root identity');
    this.assertEnabled(root.agentId);
    const live = this.ctx.agents.get(SessionId(sessionId));
    if (live) return {agent: live, root};
    let agent = await this.resolve(root.sessionId);
    for (const child of children.reverse()) {
      this.assertEnabled(root.agentId);
      const parent = agent;
      agent = await this.admit(child.header.id, root, () => this.activateChild(root, child, parent));
    }
    this.assertEnabled(root.agentId);
    return {agent, root};
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

  private async activateChild(root: SessionBinding, child: ManagedChild, parentAgent: Agent): Promise<Agent> {
    const live = this.ctx.agents.get(child.header.id);
    if (live) return live;
    const descriptor = child.descriptor;
    if (!descriptor) throw new Error('Native child has no resumable continuation descriptor');
    this.assertEnabled(root.agentId);
    const handle = await this.ctx.agents.resume({resumeSessionId: child.header.id, parentAgent,
      agentOptions: {provider: descriptor.agentProvider, model: descriptor.agentModel, reasoningEffort: descriptor.agentReasoningEffort, subagentDepth: child.header.delegationDepth},
      setup: ctx => {
        this.assertEnabled(root.agentId);
        applyChildComposition(ctx, parentAgent, descriptor);
        return {commit: () => this.assertEnabled(root.agentId)};
      },
    });
    this.handles.set(child.header.id, handle);
    return handle.agent;
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
    const setup = async (ctx: Context) => {
      await this.ctx.agentPresets.mount(ctx, preset);
      this.assertEnabled(binding.agentId);
      return {commit: () => this.assertEnabled(binding.agentId)};
    };
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
    this.owners.set(sessionId, binding.agentId);
    const task = this.ctx.agents.create({sessionId, seed, inheritedEventCount: SessionLogOffset(boundary + 1),
      meta: {cwd: binding.cwd, parentSession: request.sessionId, isSeeded: true, agentPreset: preset},
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

/** Native Schedule resolves through the same product owner as explicit inputs. */
export class OwnedSessionController extends SessionController {
  static inject = [...SessionController.inject, 'nanoSessions'];
  private readonly owner: OwnedSessions;
  constructor(ctx: Context, config: ConstructorParameters<typeof SessionController>[1]) { super(ctx, config); this.owner = ctx.nanoSessions; }
  override async resolveAgent(id: SessionId): ReturnType<SessionController['resolveAgent']> { return {agent: (await this.owner.resolveManaged(id)).agent}; }
}
