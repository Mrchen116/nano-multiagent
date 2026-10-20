import { randomUUID } from 'node:crypto';
import { Service, type Context } from '@deepseek-ai/cordis';
import type { AgentHandle } from '@deepseek-ai/dsh-agent';
import { createUserMessage, isAgentLoopRequest, ReasoningEffortId, LlmError, type GenerateOptions, type StreamChunk } from '@deepseek-ai/dsh-llm';
import { SessionId, SessionLogOffset, type SessionEvent } from '@deepseek-ai/dsh-session';
import { setApprovalPolicy } from '@deepseek-ai/dsh-user-approval';
import type {} from '@deepseek-ai/dsh-compaction';
import { deriveTurnTokenUsage } from '@deepseek-ai/dsh-token-meter/client';
import type { ApprovalReviewRequest, ApprovalReviewResult } from './types.js';
import { codexPolicy, parseCodexDecision, reviewInput, tokenCost } from './codex-context.js';
import { inspectionTools } from './codex-inspection.js';
import { codexEntries } from './sources.js';
import { ReviewAttempt, ReviewFailure, reviewFailure, whileActive, type ReviewRecovery } from './recovery.js';

declare module '@deepseek-ai/cordis' { interface Context { codexApproval: CodexApproval } }
interface Checkpoint { rows: string[]; events: SessionEvent[]; sessionId: string }
interface Reviewer {
  handle: AgentHandle; currentAttempt?: ReviewAttempt; retired: boolean; disposing?: Promise<void>;
  failure?: unknown; start: number; input: string; first: boolean;
  route: { provider: string; model: string }; limit: number; overhead: number;
}
interface Trunk { fingerprint: string; busy: boolean; reviewer?: Reviewer; checkpoint?: Checkpoint }
const outputReserve = 2048;
const prefix = (before: string[], after: string[]) => before.length <= after.length && before.every((value, i) => value === after[i]);

/** Host native Guardian sessions; leases span recovery, cache identity never owns an action. */
export class CodexApproval extends Service {
  static inject = ['agents', 'tools', 'systemPrompt', 'llm', 'approval'];
  private readonly trunks = new Map<string, Trunk>();
  private readonly owners = new Map<string, Reviewer>();
  private readonly leases = new Map<string, Set<ReviewRecovery>>();
  private readonly quarantine = new Map<string, Set<Promise<unknown>>>();
  constructor(ctx: Context) {
    super(ctx, 'codexApproval');
    ctx.on('agent/disposed', ({ agent }) => this.release(agent.id));
    ctx.effect(() => async () => {
      for (const actions of this.leases.values()) for (const action of actions) action.cancel();
      await Promise.allSettled([...this.quarantine.values()].flatMap(pending => [...pending]));
      await Promise.all([...this.owners.values()].map(reviewer => this.discard(reviewer)));
      this.trunks.clear();
    });
  }

  /** Dispatch only an exact owned, ordinary native loop request; unrelated streams stay transparent. */
  async *wrap(options: GenerateOptions, next: () => AsyncIterable<StreamChunk>): AsyncGenerator<StreamChunk> {
    if (!isAgentLoopRequest(options) || !options.sessionId || options.purpose) { yield* next(); return; }
    const owner = this.owners.get(String(options.sessionId));
    if (!owner) { yield* next(); return; }
    // Identity filtering must precede any currentAttempt access, including idle caches.
    const attempt = owner.currentAttempt;
    if (owner.retired || !attempt) throw new ReviewFailure('inactive_reviewer');
    attempt.assertActive();
    if (options.provider !== owner.route.provider || options.model !== owner.route.model || options.reasoningEffort !== 'low') throw new ReviewFailure('permanent');
    try { yield* attempt.stream(next); }
    catch (error) { if (owner.currentAttempt === attempt) owner.failure = error; throw error; }
  }

  /** Cancel released leases and prevent any in-flight action from publishing the old cache. */
  async release(sessionId: string): Promise<void> {
    const trunk = this.trunks.get(sessionId); this.trunks.delete(sessionId);
    for (const lease of this.leases.get(sessionId) ?? []) lease.cancel();
    if (trunk && !trunk.busy && trunk.reviewer) await this.discard(trunk.reviewer);
  }

  /** Review one frozen action; context rebuild shares an attempt, service recovery starts a clean full. */
  async review(request: ApprovalReviewRequest): Promise<ApprovalReviewResult> {
    const { recovery } = request;
    const parent = request.exec.agent!;
    if (this.quarantine.has(parent.id)) throw new ReviewFailure('cleanup_unavailable');
    const cwd = parent.session.header.cwd!;
    const fingerprint = JSON.stringify([request.config, request.reviewer, cwd]);
    let trunk = this.trunks.get(parent.id);
    if (!trunk || trunk.fingerprint !== fingerprint) {
      const old = trunk;
      if (old) for (const lease of this.leases.get(parent.id) ?? []) lease.cancel();
      trunk = { fingerprint, busy: false }; this.trunks.set(parent.id, trunk);
      if (old && !old.busy && old.reviewer) await this.clean(parent.id, old.reviewer, recovery);
    }
    const fork = trunk.busy;
    if (!fork) trunk.busy = true;
    const leases = this.leases.get(parent.id) ?? new Set<ReviewRecovery>(); this.leases.set(parent.id, leases); leases.add(recovery);
    let checkpoint = trunk.checkpoint;
    let reviewer = fork ? undefined : trunk.reviewer;
    let committed = false;
    try {
      const { system, evidence, serialized, limit, overhead, action } = await recovery.prepare(async signal => {
        const [system, rows, model] = await Promise.all([
          codexPolicy(request.config.approval!),
          request.sources.history(parent, request.exec.callId, request.config.mode !== 'global', { toolResults: true, fullAssistant: true }),
          this.ctx.llm.resolveModelInfo(request.reviewer.provider, request.reviewer.model, signal),
        ]);
        // This is a process-observation-preserving projection, not a restore/replay.
        const evidence = structuredClone([...codexEntries(request.sources.restoreEntries(request.inherited, false)), ...rows]);
        const schemas = inspectionTools(cwd, () => signal).map(({ name, description, parameters }) => ({ name, description, parameters }));
        const overhead = tokenCost(system) + tokenCost(JSON.stringify(schemas)) + outputReserve + 512;
        if (!model.context?.contextWindow) throw new ReviewFailure('permanent');
        const action = { name: request.exec.name, arguments: request.exec.arguments, id: request.exec.callId, schema: this.ctx.tools.schemas(parent).find(tool => tool.name === request.exec.name), cwd, rules: request.config.approval, recipient: request.messageContext };
        return { system, evidence, serialized: evidence.map(row => JSON.stringify(row)), limit: model.context.contextWindow, overhead, action };
      });
      if (checkpoint && !prefix(checkpoint.rows, serialized)) { checkpoint = undefined; if (reviewer) { await this.clean(parent.id, reviewer, recovery); reviewer = undefined; } }
      let mode = fork ? 'fork' : checkpoint ? 'delta' : 'full';
      return await recovery.run('guardian', 90_000, async attempt => {
        attempt.onQuarantine = pending => this.hold(parent.id, pending);
        if (attempt.trace.retryOrdinal) { checkpoint = undefined; reviewer = undefined; mode = fork ? 'fork-full-recovery' : 'full-recovery'; }
        for (;;) {
          attempt.assertActive();
          try {
            const history = reviewer ? reviewer.handle.agent.session.deriveMessages() : undefined;
            const seeded = history ? tokenCost(JSON.stringify(history)) : checkpoint ? tokenCost(JSON.stringify(checkpoint.events)) : 0;
            let input: string;
            if (checkpoint) {
              try { input = reviewInput(evidence.slice(checkpoint.rows.length), action, limit - overhead - seeded, false); }
              catch { throw new ReviewFailure('context'); }
              if (input.includes('reason="evidence_budget"')) throw new ReviewFailure('context');
            } else {
              // Keep 626 default recovery admission; required/action overflow is not a service failure.
              try { input = reviewInput(evidence, action, limit - overhead); }
              catch { throw new ReviewFailure('context_required'); }
            }
            if (!reviewer) reviewer = await this.create(request, system, attempt, checkpoint, limit, overhead);
            attempt.assertActive();
            const current = reviewer;
            current.currentAttempt = attempt; current.failure = undefined; current.input = input; current.first = true;
            current.start = current.handle.agent.session.snapshotEvents().length;
            Object.assign(attempt.trace, { sessionId: current.handle.agent.id, contextMode: mode });
            const agent = current.handle.agent;
            const cancel = () => agent.cancel({ kind: 'parent' });
            attempt.signal.addEventListener('abort', cancel, { once: true });
            try {
              attempt.assertActive();
              agent.followup(createUserMessage({ content: [{ type: 'text', text: input }], source: { kind: 'user' } }));
              await whileActive(agent.whenIdle(), attempt.signal);
              attempt.assertActive();
            } finally { attempt.signal.removeEventListener('abort', cancel); }
            const events = agent.session.snapshotEvents(); const added = events.slice(current.start);
            if (added.some(event => event.type === 'compaction/start')) throw new ReviewFailure('context');
            if (current.failure) throw current.failure;
            const end = added.findLast(event => event.type === 'turn/end');
            if (end?.type === 'turn/end' && end.data.reason.kind !== 'completed') throw new ReviewFailure('unavailable_unknown');
            const last = added.findLast(event => event.type === 'assistant/message');
            const text = last?.type === 'assistant/message' ? last.data.message.content.filter(block => block.type === 'text').map(block => block.text).join('') : '';
            const decision = parseCodexDecision(text);
            if (!decision) throw new ReviewFailure(text.trim() ? 'malformed' : 'empty_text');
            attempt.assertActive();
            if (this.trunks.get(parent.id) !== trunk) throw new ReviewFailure('cancelled');
            current.currentAttempt = undefined;
            if (!fork && this.trunks.get(parent.id) === trunk) {
              trunk.checkpoint = { rows: serialized, events: [...events], sessionId: agent.id }; trunk.reviewer = current; committed = true;
            }
            return { decision, usage: deriveTurnTokenUsage(added.slice(added.findIndex(event => event.type === 'turn/start'), added.findLastIndex(event => event.type === 'turn/end') + 1)), metadata: { sessionId: agent.id, contextMode: mode, risk: decision.risk, authorization: decision.authorization } };
          } catch (error) {
            if (reviewer) { const failed = reviewer; reviewer = undefined; await this.clean(parent.id, failed, recovery); }
            attempt.assertActive();
            const failure = reviewFailure(error);
            if (failure.category !== 'context' || !recovery.takeContextRebuild()) throw error;
            checkpoint = undefined; mode = fork ? 'fork-rebuild' : 'rebuild';
          }
        }
      });
    } finally {
      try { if (!committed && reviewer) await this.clean(parent.id, reviewer, recovery); }
      finally {
        if (!fork) { trunk.reviewer = committed ? reviewer : undefined; if (!committed) trunk.checkpoint = undefined; trunk.busy = false; }
        leases.delete(recovery); if (!leases.size) this.leases.delete(parent.id);
      }
    }
  }

  private hold(parent: string, pending: Promise<unknown>, releaseOnRejection = true): void {
    const pendingSet = this.quarantine.get(parent) ?? new Set<Promise<unknown>>();
    this.quarantine.set(parent, pendingSet); pendingSet.add(pending);
    const release = () => {
      pendingSet.delete(pending);
      if (!pendingSet.size && this.quarantine.get(parent) === pendingSet) this.quarantine.delete(parent);
    };
    void pending.then(release, () => { if (releaseOnRejection) release(); });
  }
  private async clean(parent: string, reviewer: Reviewer, recovery: ReviewRecovery): Promise<void> {
    const pending = this.discard(reviewer);
    try { await recovery.cleanup(pending); }
    catch (error) { this.hold(parent, pending, false); throw error; }
  }
  private discard(reviewer: Reviewer): Promise<void> {
    const attempt = reviewer.currentAttempt;
    reviewer.retired = true; reviewer.currentAttempt = undefined;
    if (!reviewer.disposing) {
      reviewer.handle.agent.cancel({ kind: 'parent' });
      reviewer.disposing = Promise.all(attempt ? [...attempt.drains] : []).then(() => reviewer.handle.dispose()).then(() => {
        if (this.owners.get(reviewer.handle.agent.id) === reviewer) this.owners.delete(reviewer.handle.agent.id);
      });
    }
    return reviewer.disposing;
  }
  private async create(request: ApprovalReviewRequest, system: string, attempt: ReviewAttempt, checkpoint: Checkpoint | undefined, limit: number, overhead: number): Promise<Reviewer> {
    const effort = ReasoningEffortId('low');
    const reviewer = { retired: false, route: request.reviewer, limit, overhead, start: checkpoint?.events.length ?? 0 } as Reviewer;
    const sessionId = SessionId(`nano-codex-${randomUUID()}`);
    try {
      const handle = await this.ctx.agents.create({ sessionId, signal: attempt.signal,
        meta: { cwd: request.exec.agent!.session.header.cwd, agentPreset: 'nano-codex-reviewer', ...(checkpoint ? { parentSession: SessionId(checkpoint.sessionId), isSeeded: true } : {}) },
        ...(checkpoint ? { seed: checkpoint.events, inheritedEventCount: SessionLogOffset(checkpoint.events.length) } : {}),
        agentOptions: { ...request.reviewer, reasoningEffort: effort, maxTokens: outputReserve },
        setup: (scope, agent) => {
          this.owners.set(sessionId, reviewer);
          setApprovalPolicy(agent.session, 'never');
          scope.tools.presentAs('native'); scope.tools.restrict({ allow: [] });
          const tools = inspectionTools(request.exec.agent!.session.header.cwd!, () => reviewer.currentAttempt?.signal ?? AbortSignal.abort());
          for (const tool of tools) scope.tools.register(tool);
          const names = new Set(tools.map(tool => tool.name));
          scope.tools.guard(exec => names.has(exec.name) ? undefined : 'Guardian permits only host-owned read-only inspection');
          scope.systemPrompt.section({ name: 'nano-guardian', order: 0, text: system, complete: true, interpolate: false });
          scope.on('system-prompt/assemble', async (_assembly, _context, next) => ({ ...await next(), contexts: [], tools: scope.tools.schemas(agent) }), { prepend: true });
          scope.on('agent/request', async (_payload, next) => {
            const current = reviewer.currentAttempt;
            if (!current || reviewer.retired) throw new ReviewFailure('inactive_reviewer');
            current.assertActive();
            if (agent.session.snapshotEvents().slice(reviewer.start).some(event => event.type === 'compaction/start') || tokenCost(JSON.stringify(agent.session.deriveMessages())) + (reviewer.first ? tokenCost(reviewer.input) : 0) + overhead > limit) {
              reviewer.failure = new ReviewFailure('context'); throw reviewer.failure;
            }
            reviewer.first = false;
            return { ...await next(), ...reviewer.route, reasoningEffort: effort, maxTokens: outputReserve };
          }, { prepend: true });
          scope.on('agent/request-error', async ({ failure }) => {
            reviewer.failure ??= new LlmError('Guardian provider failure', failure.code, failure);
            return undefined;
          }, { prepend: true });
        },
      });
      reviewer.handle = handle;
      try { attempt.assertActive(); } catch (error) { await this.discard(reviewer); throw error; }
      return reviewer;
    } catch (error) {
      if (!reviewer.handle && this.owners.get(sessionId) === reviewer) this.owners.delete(sessionId);
      throw error;
    }
  }
}
