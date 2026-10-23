import type {} from '@deepseek-ai/dsh-compaction';
import type {} from '@deepseek-ai/dsh-tool-skill';
import { randomUUID } from 'node:crypto';
import { AsyncLocalStorage } from 'node:async_hooks';
import { realpath } from 'node:fs/promises';
import { realpathSync } from 'node:fs';
import { relative, resolve, join } from 'node:path';
import { Service, type Context } from '@deepseek-ai/cordis';
import { renderSkillContent } from '@deepseek-ai/dsh-skill';
import { SessionId } from '@deepseek-ai/dsh-session';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ToolSchema } from '@deepseek-ai/dsh-llm';
import type { ToolExecution } from '@deepseek-ai/dsh-tools';
import type { Domain } from '@deepseek-ai/dsh-storage-domain';
import type { SessionBinding, AgentConfiguration } from '../index.js';
import { invalidateSkills } from '../capabilities.js';
import { KnowledgeFiles, type MemoryChange, type SkillChange } from './files.js';
import { knowledgeDomain, type KnowledgeDomain, type KnowledgeFact, type KnowledgeKind, type KnowledgeReview } from './state.js';
import { ReviewFiles } from './review-files.js';
import { reviewReadings } from './review-readings.js';
import { withKnowledgeRun } from '../trajectory-runs.js';
import { policyAsset } from '../policy/rules.js';

declare module '@deepseek-ai/cordis' { interface Context { nanoKnowledge: KnowledgeRuntime } }
interface Options { configOf(agent: Agent): AgentConfiguration | undefined; configs: Map<string, AgentConfiguration>; bindings: Map<string, SessionBinding>; notify(): void }
const storageKey = (value: string) => Buffer.from(value).toString('base64url');
interface Batch { root: string; name: string }
interface Active { controller: AbortController; task: Promise<void>; agentId: string; rootSessionId: string; kinds: KnowledgeKind[]; source: 'F3' | 'F4'; turn: number; batch?: Batch; reads: ReviewFiles }
interface ReviewContext { id: string; work: Active; allow: string[]; parent: Agent }


/** Owns accepted native review runs and durable success facts across Feature disposal. */
export class KnowledgeRuntime extends Service {
  static inject = ['subagents', 'tools', 'skills', 'agents', 'storageDomain', 'systemPrompt', 'sessionQuery'];
  private readonly state: Promise<Domain<KnowledgeDomain>>;
  private readonly active = new Map<string, Active>();
  private readonly tasks = new Set<Promise<unknown>>();
  private readonly host: Context;
  private stopping = false;
  private updateHeld = false;
  private readonly undelivered = new Set<string>();
  private readonly subscriptions = new Map<string, Set<Context>>();
  private readonly children = new WeakMap<Agent, ReviewContext>();
  private readonly pendingBatches = new Map<string, { agentId: string; batch: Batch }>();
  private readonly reviewStart = new AsyncLocalStorage<ReviewContext & { parentId: string; system: string; tools: ToolSchema[] }>();
  constructor(ctx: Context, private readonly options: Options) {
    super(ctx, 'nanoKnowledge'); this.host = ctx; this.state = ctx.storageDomain.open(knowledgeDomain);
    ctx.effect(() => async () => { await this.stop(); await (await this.state).close(); });
    ctx.on('agent/created', ({ agent }) => {
      const frozen = this.reviewStart.getStore();
      if (!frozen || agent.session.header.parentSession !== frozen.parentId) return;
      this.children.set(agent, frozen);
      // feat-349: preserve the model-visible prefix; restrict execution, not declarations.
      agent.ctx.systemPrompt.section({ name: 'nano-review-parent-prompt', order: 0, text: frozen.system, interpolate: false, complete: true });
      agent.ctx.on('system-prompt/assemble', async (_assembly, _context, next) => ({ ...await next(), tools: structuredClone(frozen.tools) }), { prepend: true });
      agent.ctx.tools.guard(exec => {
        if (frozen.work.controller.signal.aborted) return 'Knowledge review was cancelled.';
        if (!frozen.allow.includes(exec.name) || !frozen.parent.ctx.tools.get(exec.name, frozen.parent)) return `Knowledge review may only execute enabled tools: ${frozen.allow.join(', ')}.`;
        if (frozen.work.batch) {
          const args = exec.arguments as { file_path?: string; name?: string; scope?: string; action?: string };
          const target = join(frozen.work.batch.root, frozen.work.batch.name, 'SKILL.md');
          if (exec.name === 'read') {
            if (typeof args.file_path !== 'string') return 'F4 may only read its bound target.';
            try { if (realpathSync(resolve(agent.session.header.cwd!, args.file_path)) !== target) return 'F4 may only read its bound target.'; }
            catch { return 'F4 target is no longer readable.'; }
          }
          if (exec.name === 'skill') return 'Use read on the bound original SKILL.md for F4.';
          if (exec.name === 'skill_manage' && (args.action !== 'patch' || args.name !== frozen.work.batch.name)) return 'F4 may only patch its bound target.';
        }
      });
    });
    // Usage remains available when automatic Skill creation is disabled.
    ctx.on('tools/result', (exec, result) => {
      const review = exec.agent && this.children.get(exec.agent);
      if (review) { review.work.reads.observe(exec, result); return; }
      if (exec.name === 'skill' && exec.agent && !result.isError && this.config(exec.agent)) this.track(this.used(exec.agent, (exec.arguments as { name: string }).name, exec.callId));
    });
    ctx.on('session/event', (session, event) => {
      if (event.type === 'user/message' && event.data.source.kind === 'skill-invocation') {
        const agent = this.host.agents.get(session.id);
        if (agent && this.config(agent)) this.track(this.used(agent, event.data.source.name, event.data.id));
      }
      if (event.type !== 'step/start' || !session.header.parentSession) return;
      const active = this.reviewIdentity(session.id);
      if (active && session.ownEvents().filter(item => item.type === 'step/start').length > 16) this.host.agents.get(session.id)?.cancel({ kind: 'hook', reason: 'Knowledge review step limit reached' });
    });
    ctx.on('system-prompt/assemble', async (_assembly, context, next) => {
      const assembly = await next(); const agent = context.agent ?? context.scope as Agent | undefined;
      const config = agent?.session && this.config(agent);
      if (!agent || !config || !agent.session.snapshotEvents().some(event => event.type === 'compaction/end' && event.data.error === undefined)) return assembly;
      // The workspace context engine rebuilds the native catalog; old bodies stay in History.
      if (this.host.get('agentPresets')?.serviceFor(agent, 'compaction')) return assembly;
      const refs = await this.files(agent).references(agent.id, (config.skillRoots ?? []).map(root => root.path));
      const content: string[] = [];
      for (const ref of refs) {
        const skill = await this.host.skills.get(ref.name, { scope: agent, cwd: agent.session.header.cwd });
        if (skill) content.push(renderSkillContent(skill));
      }
      if (content.length) assembly.contexts.push({ name: 'nano-used-skills', text: `Previously used Skills, restored after compaction:\n${content.join('\n\n')}` });
      return assembly;
    });
  }
  /** Reviews and their asynchronous bookkeeping must finish before an update. */
  get busy(): boolean { return this.active.size > 0 || this.tasks.size > 0 || this.undelivered.size > 0; }
  /** Pause periodic curation during an update without changing Feature settings. */
  suspendUpdates(held: boolean): void { this.updateHeld = held; }
  private track(task: Promise<unknown>) {
    this.tasks.add(task); void task.catch(error => this.host.logger('nano-knowledge').warn(String(error))).finally(() => this.tasks.delete(task));
  }
  config(agent: Agent) { return this.options.configOf(agent); }
  files(agent: Agent) { return new KnowledgeFiles(agent.session.header.cwd!, this.config(agent)?.knowledge?.globalSkillRoot); }
  private root(agent: Agent) {
    let current = agent;
    while (!this.options.bindings.has(current.id) && current.session.header.parentSession) {
      const parent = this.host.agents.get(current.session.header.parentSession); if (!parent) throw new Error('Knowledge work has no live product root'); current = parent;
    }
    if (!this.options.bindings.has(current.id)) throw new Error('Knowledge work has no product binding');
    return current;
  }
  private turn(agent: Agent) {
    const event = agent.session.snapshotEvents().findLast(event => event.type === 'turn/start');
    return event?.type === 'turn/start' ? event.data.turn : 0;
  }
  private reviewIdentity(sessionId: string): string | undefined {
    const agent = this.host.agents.get(SessionId(sessionId));
    return agent && this.children.get(agent)?.id;
  }
  private checkReview(agent: Agent, kind: KnowledgeKind) {
    const review = this.children.get(agent);
    if (!review) return;
    review.work.controller.signal.throwIfAborted();
    const config = this.config(review.parent);
    if (!review.work.kinds.includes(kind) || config?.knowledge?.enabled === false || config?.features?.[kind === 'memory' ? 'memory_curation' : 'skill_creation'] === false) throw new Error('Knowledge maintenance is disabled.');
    if (review.work.batch && config?.mode === 'global') throw new Error('Global mode cannot run F4.');
  }
  async memory(exec: ToolExecution, change: MemoryChange) {
    const agent = exec.agent!;
    const review = this.children.get(agent);
    this.checkReview(agent, 'memory');
    if (review) { review.work.reads.memoryWrite(); if (review.work.reads.memoryIncomplete) throw new Error('Read both current Memory files before writing.'); }
    const result = await this.files(agent).memory(change, agent.id, exec.signal);
    await this.changed(exec, { ...result, kind: 'memory' }); return result;
  }
  async skill(exec: ToolExecution, change: SkillChange) {
    const review = this.children.get(exec.agent!);
    const source = review ? review.work.source : 'F1';
    this.checkReview(exec.agent!, 'skills');
    const result = await this.files(exec.agent!).skill(change, source, exec.signal, review ? {
      reads: review.work.reads, check: () => this.checkReview(exec.agent!, 'skills'), target: review.work.batch,
    } : undefined);
    invalidateSkills(this.config(exec.agent!)!);
    await this.changed(exec, { ...result, kind: 'skills' }); return result;
  }
  private async changed(exec: ToolExecution, result: { kind: KnowledgeKind; action: string; path: string; name?: string; scope?: string; skill_root?: string; source?: string }) {
    const agent = exec.agent!; const root = this.root(agent); const reviewId = this.reviewIdentity(agent.id);
    const fact: KnowledgeFact = { id: `${agent.id}:${exec.callId}`, agentId: this.config(agent)!.agentId, rootSessionId: root.id, sessionId: agent.id, turn: reviewId ? this.active.get(reviewId)!.turn : this.turn(root), ...result, ...(reviewId ? { reviewId } : {}) };
    this.undelivered.add(fact.id);
    await (await this.state).table('facts').put(storageKey(fact.id), fact); this.options.notify();
  }
  async usage(agentId: string) {
    const config = [...this.options.configs.values()].find(config => config.agentId === agentId);
    const binding = [...this.options.bindings.values()].find(binding => binding.agentId === agentId);
    if (!config) throw new Error('Unknown Agent');
    const workspace = config.workspace ?? binding?.cwd; if (!workspace) throw new Error('Agent has no workspace');
    const known = new Map<string, boolean>();
    return new KnowledgeFiles(workspace, config.knowledge?.globalSkillRoot).usage((config.skillRoots ?? []).map(root => root.path), async id => {
      if (!known.has(id)) {
        try { using observation = await this.host.sessionQuery.observeSession(SessionId(id)); known.set(id, observation.header.cwd === workspace); }
        catch { known.set(id, false); }
      }
      return known.get(id)!;
    });
  }
  async facts() { return [...(await this.state).table('facts').entries()].map(([, value]) => value); }
  async acknowledge(id: string) { await (await this.state).table('facts').delete(storageKey(id)); this.undelivered.delete(id); }
  async recover() {
    for (const fact of await this.facts()) this.undelivered.add(fact.id);
    const reviews = (await this.state).table('reviews');
    for (const [id, review] of reviews.entries()) if (review.status === 'running') await reviews.put(id, { ...review, status: 'interrupted' });
    return this.reviews();
  }
  async reviews() { return [...(await this.state).table('reviews').entries()].map(([, value]) => value); }
  /** A Feature owns this listener and its disposal cancels only this kind of accepted review. */
  subscribe(ctx: Context, agentId: string, kind: KnowledgeKind) {
    const key = `${agentId}:${kind}`;
    let owners = this.subscriptions.get(key); if (!owners) { owners = new Set(); this.subscriptions.set(key, owners); }
    owners.add(ctx);
    let scan = () => {};
    if (kind === 'skills') {
      scan = () => {
        if (this.updateHeld) return;
        const agent = [...this.options.bindings.values()].filter(binding => binding.agentId === agentId).map(binding => this.host.agents.get(SessionId(binding.sessionId))).find(Boolean);
        if (!agent) return;
        const files = this.files(agent);
        this.track(Promise.all([files.curate(files.skillRoot), ...(this.config(agent)?.knowledge?.globalSkillRoot ? [files.curate(this.config(agent)!.knowledge!.globalSkillRoot!)] : [])]).then(() => invalidateSkills(this.config(agent)!)));
      };
      const timer = setInterval(scan, 3600000); timer.unref(); ctx.effect(() => () => clearInterval(timer));
    }
    ctx.on('session/event', (session, event) => {
      if (event.type !== 'turn/end' || event.data.reason.kind !== 'completed' || !this.options.bindings.has(session.id)) return;
      const agent = this.host.agents.get(session.id); if (!agent || this.config(agent)?.agentId !== agentId) return;
      scan(); this.queueReview(agent);
      for (const entry of this.pendingBatches.values()) if (entry.agentId === agentId) this.queueReview(agent, entry.batch);
    });
    ctx.effect(() => async () => { owners.delete(ctx); if (!owners.size) { this.subscriptions.delete(key); await this.cancel(agentId, kind); } });
  }
  private async used(agent: Agent, name: string, callId: string) {
    if (this.children.has(agent)) return;
    const config = this.config(agent)!;
    const skill = await this.host.skills.get(name, { scope: agent, cwd: agent.session.header.cwd });
    if (!skill?.path) return;
    const location = await realpath(skill.path);
    let root: string | undefined;
    for (const candidate of config.skillRoots ?? []) {
      const path = relative(await realpath(candidate.path).catch(() => candidate.path), location);
      if (path && !path.startsWith('..') && !path.startsWith('/')) { root = candidate.path; break; }
    }
    if (!root) return;
    const result = await this.files(agent).use(root, name, agent.id, callId, skill.path);
    if (result.batch && config.mode !== 'global' && config.features?.skill_creation !== false && this.options.bindings.has(agent.id)) {
      const batch = { root: await realpath(root), name };
      this.pendingBatches.set(`${config.agentId}:${batch.root}:${name}`, { agentId: config.agentId, batch });
      this.queueReview(agent, batch);
    }
  }
  private queueReview(agent: Agent, batch?: Batch) {
    if (this.stopping || [...this.active.values()].some(work => batch
      ? work.batch?.root === batch.root && work.batch?.name === batch.name
      : !work.batch && work.rootSessionId === agent.id)) return;
    const config = this.config(agent)!; const id = randomUUID(); const controller = new AbortController();
    const files = this.files(agent);
    const reads = new ReviewFiles(agent.session.header.cwd!, [join(files.memoryRoot, 'USER.md'), join(files.memoryRoot, 'MEMORY.md')], [files.skillRoot, ...(config.knowledge?.globalSkillRoot ? [config.knowledge.globalSkillRoot] : [])]);
    const task = Promise.resolve().then(() => this.review(agent, id, controller.signal, batch)).catch(async error => {
      const state = await this.state; const record = state.table('reviews').get(id);
      if (record) await state.table('reviews').put(id, { ...record, status: controller.signal.aborted ? 'cancelled' : 'error', diagnostic: String(error).slice(0, 4096) });
      if (!controller.signal.aborted) throw error;
    }).finally(() => this.active.delete(id));
    this.active.set(id, { controller, task, agentId: config.agentId, rootSessionId: agent.id, kinds: batch ? ['skills'] : ['memory', 'skills'], source: batch ? 'F4' : 'F3', turn: this.turn(agent), reads, batch });
    this.track(task);
  }
  private async review(agent: Agent, id: string, signal: AbortSignal, batch?: Batch) {
    const config = this.config(agent)!; const work = this.active.get(id)!;
    if (config.knowledge?.enabled === false || batch && config.mode === 'global') return;
    const state = await this.state; const counters = state.table('counters'); signal.throwIfAborted();
    const enabled = (kind: KnowledgeKind) => config.features?.[kind === 'memory' ? 'memory_curation' : 'skill_creation'] !== false
      && this.subscriptions.has(`${config.agentId}:${kind}`)
      && !!agent.ctx.tools.get(kind === 'memory' ? 'memory' : 'skill_manage', agent)
      && (kind !== 'memory' || !!agent.ctx.tools.get('read', agent));
    const readings = { memory: reviewReadings(agent.session.ownEvents(), 'memory'), skills: reviewReadings(agent.session.ownEvents(), 'skills') };
    const key = (kind: KnowledgeKind) => storageKey(`${agent.id}:${kind}:iterations`);
    const due = (kind: KnowledgeKind) => {
      const interval = config.knowledge?.[kind === 'memory' ? 'memoryInterval' : 'skillInterval'] ?? 10;
      return enabled(kind) && interval > 0 && readings[kind].current - Math.max(counters.get(key(kind))?.[kind] ?? 0, readings[kind].maintained) >= interval;
    };
    work.kinds = batch ? enabled('skills') && agent.ctx.tools.get('read', agent) ? ['skills'] : [] : (['memory', 'skills'] as const).filter(due);
    if (!work.kinds.length) return;
    const kind = work.kinds.length === 2 ? 'combined' : work.kinds[0]!;
    let candidate: Awaited<ReturnType<KnowledgeFiles['batchCandidate']>>;
    let evidence: { sessionId: string; events: unknown[] }[] = [];
    const record: KnowledgeReview = { id, agentId: config.agentId, rootSessionId: agent.id, kind, source: work.source, ...(batch ? { target: batch } : {}), turn: work.turn, status: 'running', at: Date.now() };
    if (batch) {
      candidate = await this.files(agent).batchCandidate(batch.root, batch.name);
      if (!candidate) return;
      evidence = await this.batchHistory(agent, candidate.refs, candidate.reviewed);
      if (evidence.length < 2) {
        await state.table('reviews').put(id, { ...record, status: 'skipped', skipReason: 'insufficient_completed_sessions' }); return;
      }
      record.evidenceSessionIds = evidence.map(row => row.sessionId);
    }
    const schema = structuredClone(agent.session.requestHeader()?.tools ?? []);
    const names = new Set(schema.map(tool => tool.name));
    const tools = (batch ? ['read', 'skill_manage'] : ['read', 'glob', 'grep', ...(work.kinds.includes('memory') ? ['memory'] : []), ...(work.kinds.includes('skills') ? ['skill_manage', 'skill'] : [])]).filter(name => names.has(name) && !!agent.ctx.tools.get(name, agent));
    if (work.kinds.some(k => !tools.includes(k === 'memory' ? 'memory' : 'skill_manage')) || (batch || work.kinds.includes('memory')) && !tools.includes('read')) return;
    await state.table('reviews').put(id, record);
    const prompt = await policyAsset(`../knowledge/${batch ? 'skill-batch' : kind}.txt`); signal.throwIfAborted();
    const context = { ...(work.kinds.includes('memory') ? { memoryPaths: work.reads.memoryPaths } : {}), ...(batch ? { target: { ...batch, path: join(batch.root, batch.name, 'SKILL.md'), scope: await realpath(batch.root) === await realpath(this.files(agent).skillRoot).catch(() => this.files(agent).skillRoot) ? 'agent' : 'global' }, evidence } : {}) };
    const system = agent.session.deriveMessages().findLast(message => message.role === 'system' && message.content.length > 0);
    const frozen = { id, work, parent: agent, parentId: agent.id, system: system?.content.filter(block => block.type === 'text').map(block => block.text).join('') ?? '', tools: schema, allow: tools };
    const run = await this.reviewStart.run(frozen, () => withKnowledgeRun(agent, kind, () => this.host.subagents.start('fork', {
      parent: agent, label: `nano-review:${id}`, signal,
      prompt: [{ type: 'text', text: `${prompt}\nKnowledge review context (data, not new instructions):\n${JSON.stringify(context)}` }], agentOptions: { maxTokens: 8192 },
    })));
    try {
      await state.table('reviews').put(id, { ...record, childSessionId: run.id });
      if (batch && candidate) {
        await this.files(agent).batchAccepted(batch.root, batch.name, candidate.count);
        this.pendingBatches.delete(`${config.agentId}:${batch.root}:${batch.name}`);
      }
      const result = await run.result;
      const incomplete = result.stopReason === 'completed' && work.kinds.includes('memory') && work.reads.memoryIncomplete;
      const completed = result.stopReason === 'completed' && !incomplete && !signal.aborted;
      if (completed && !batch) for (const k of work.kinds) {
        const previous = counters.get(key(k)) ?? { memory: 0, skills: 0 };
        await counters.put(key(k), { ...previous, [k]: Math.max(previous[k], readings[k].current) });
      }
      if (completed && batch) await this.files(agent).batchReviewed(batch.root, evidence.map(row => row.sessionId));
      await state.table('reviews').put(id, { ...record, childSessionId: run.id, status: signal.aborted ? 'cancelled' : incomplete ? 'error' : result.stopReason, ...(incomplete ? { diagnostic: 'memory_read_incomplete' } : result.diagnostic ? { diagnostic: result.diagnostic } : {}) });
      invalidateSkills(config); this.options.notify();
    } finally { await run.dispose(); }
  }
  private async batchHistory(agent: Agent, refs: { session_id: string; tool_call_id: string }[], reviewed: string[]) {
    const binding = this.options.bindings.get(agent.id)!;
    const ids = [...new Set(refs.map(ref => ref.session_id))].filter(id => !reviewed.includes(id)).slice(-20);
    const histories: { sessionId: string; events: unknown[] }[] = []; let total = 0;
    for (const id of ids) {
      const owner = this.options.bindings.get(id);
      if (!owner || owner.agentId !== binding.agentId || owner.ownerId !== binding.ownerId || resolve(owner.cwd) !== resolve(binding.cwd)) continue;
      const live = this.host.agents.get(SessionId(id));
      if (live && (live.status !== 'idle' || live.inbox.nextTurn.length || live.inbox.nextStep.length)) continue;
      try {
        using observation = await this.host.sessionQuery.observeSession(SessionId(id));
        if (resolve(observation.header.cwd ?? '') !== resolve(binding.cwd)) continue;
        const own = observation.events.slice(observation.inheritedEventCount);
        const pending: Record<string, unknown[]> = { 'next-turn': [], 'next-step': [] };
        for (const event of own) if (event.type === 'agent/inbox/spliced') pending[event.data.target]!.splice(event.data.start, event.data.removedCount ?? 0, ...event.data.inserted);
        if (Object.values(pending).some(items => items.length)) continue;
        const last = own.findLast(e => e.type === 'turn/start' || e.type === 'turn/end');
        if (last?.type !== 'turn/end' || last.data.reason.kind !== 'completed') continue;
        const keys = new Set(refs.filter(ref => ref.session_id === id).map(ref => ref.tool_call_id));
        let start = 0; const selected: unknown[] = []; let size = 0;
        for (let i = 0; i < own.length; i++) {
          const event = own[i]!;
          if (event.type === 'turn/start') start = i;
          if (event.type !== 'turn/end' || event.data.reason.kind !== 'completed') continue;
          // Evidence is the completed conversation, not repeated schemas or streamed copies.
          const turn = own.slice(start, i + 1).filter(e => ['turn/start', 'turn/end', 'assistant/message', 'tool/call', 'tool/result'].includes(e.type)
            || e.type === 'user/message' && !['runtime-context', 'skill-catalog', 'system'].includes(e.data.source.kind))
            .map(e => e.type === 'assistant/message' ? { ...e, data: { ...e.data, stream: undefined } } : e);
          const used = turn.some(e => e.type === 'user/message' && e.data.source.kind === 'skill-invocation' && keys.has(e.data.id)
            || e.type === 'tool/result' && keys.has(e.data.message.toolCallId) && !e.data.message.isError);
          if (!used) continue;
          const bytes = JSON.stringify(turn).length;
          if (size + bytes > 20000 || total + size + bytes > 100000) continue;
          selected.push(...turn); size += bytes;
        }
        if (selected.length) { histories.push({ sessionId: id, events: selected }); total += size; }
      } catch { /* One unreadable history does not invalidate other eligible sessions. */ }
    }
    return histories;
  }
  async cancel(agentId: string, kind: KnowledgeKind) {
    const active = [...this.active.values()].filter(value => value.agentId === agentId && value.kinds.includes(kind));
    for (const work of active) work.controller.abort();
    await Promise.allSettled(active.map(value => value.task));
  }
  async stop() {
    this.stopping = true; for (const work of this.active.values()) work.controller.abort();
    await Promise.allSettled([...this.tasks, ...[...this.active.values()].map(work => work.task)]);
  }
}
