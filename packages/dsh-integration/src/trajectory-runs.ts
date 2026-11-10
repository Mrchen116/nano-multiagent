import { AsyncLocalStorage } from 'node:async_hooks';
import { randomUUID } from 'node:crypto';
import { Service, type Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { carrierKeyOf } from '@deepseek-ai/dsh-scope';
import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import type { SubagentRun } from '@deepseek-ai/dsh-subagent';
import type { TrajectoryRun } from '@nano/product-contracts';
import { z } from 'zod';

interface RunDomain extends DomainSpec { tables: { runs: DomainTableSpec<string, TrajectoryRun> } }
export const trajectoryRunsDomain: RunDomain = defineDomain({ name: 'nano_trajectory_runs', version: 1, layout: 'per-record', tables: {
  runs: domainTable(z.object({
    runId: z.string(), parentSessionId: z.string(), sessionId: z.string(), provider: z.string(), label: z.string().optional(),
    kind: z.enum(['tool', 'memory', 'skills', 'combined', 'dreaming', 'unknown']), delegation: z.enum(['foreground', 'background', 'unknown']),
    launchSeq: z.number().optional(), callId: z.string().optional(), startSeq: z.number().optional(), endSeq: z.number().optional(),
    startedAt: z.number(), endedAt: z.number().optional(), stopReason: z.string().optional(),
    state: z.enum(['running', 'completed', 'failed', 'cancelled', 'unknown']),
  })),
} });
interface Launch { toolName?: string; parentSessionId: string; kind: TrajectoryRun['kind']; delegation: TrajectoryRun['delegation']; launchSeq?: () => number | undefined; callId?: string; label?: string }
const launchContext = new AsyncLocalStorage<Launch>();

/** Observe host-owned maintenance without publishing a model-managed child.
 *
 * Args:
 *   ctx: Host context with the trajectory service injected.
 *   agent: Live parent whose last accepted event anchors the launch.
 *   kind: Maintenance purpose supplied by its owner, never decoded from labels.
 *   label: Display label for the maintenance execution.
 *   start: Native provider operation owned by the maintenance subsystem.
 * Returns:
 *   Native run with its settled result recorded in the trajectory index.
 */
export async function withKnowledgeRun(ctx: Context, agent: Agent, kind: 'memory' | 'skills' | 'combined', label: string, start: () => Promise<SubagentRun>): Promise<SubagentRun> {
  const launchSeq = agent.session.seq - 1;
  const run = await start();
  return ctx.nanoTrajectoryRuns.knowledge(agent, kind, label, launchSeq, run);
}

declare module '@deepseek-ai/cordis' { interface Context { nanoTrajectoryRuns: TrajectoryRuns } }

/** Persist lifecycle observations separately from the immutable native session log. */
export class TrajectoryRuns extends Service {
  private readonly domain;
  private writes = Promise.resolve();
  private readonly pending = new Map<string, Promise<void>>();
  private readonly runsBySession: Promise<Map<string, Set<string>>>;
  private readonly bounds = new WeakMap<Agent, number>();
  private readonly tails = new Map<string, number>();
  private readonly active = new Map<string, TrajectoryRun>();
  private readonly pendingDefaults = new Map<string, string>();

  constructor(ctx: Context) {
    super(ctx, 'nanoTrajectoryRuns');
    this.domain = ctx.storageDomain.open(trajectoryRunsDomain);
    this.runsBySession = this.domain.then(domain => {
      const index = new Map<string, Set<string>>();
      for (const [, run] of domain.table('runs').entries()) this.indexRun(index, run);
      return index;
    });
    ctx.effect(() => async () => { try { await this.writes; } finally { await (await this.domain).close(); } });
    ctx.on('agent/created', ({ agent }) => {
      if (!agent.session.header.parentSession) return;
      // Creation precedes descriptor/prompt writes, including for cold resumed epochs.
      this.bounds.set(agent, agent.session.seq);
      this.tails.set(agent.id, agent.session.seq - 1);
    }, { prepend: true });
    ctx.on('session/event', (session, event) => {
      if (session.header.parentSession) this.tails.set(session.id, event.seq);
      if (event.type !== 'subagent/descriptor') return;
      const runId = this.pendingDefaults.get(session.id);
      const run = runId && this.active.get(runId);
      if (!run) return;
      const resolved: TrajectoryRun = { ...run, delegation: event.data.mode === 'continuable' ? 'background' : 'foreground' };
      this.pendingDefaults.delete(session.id);
      this.active.set(resolved.runId, resolved);
      this.persist(resolved);
    });
    ctx.on('tools/execute', (exec, next) => {
      if (!exec.agent) return next();
      const args = exec.arguments as { description?: unknown; run_in_background?: unknown } | null;
      const agent = exec.agent, callId = exec.rootCallId ?? exec.callId, through = agent.session.seq - 1;
      let resolved = false, launchSeq: number | undefined;
      const resolveLaunchSeq = () => {
        if (!resolved) {
          launchSeq = agent.session.snapshotEvents().findLast(event => event.seq <= through && event.type === 'tool/call' && event.data.callId === callId)?.seq;
          resolved = true;
        }
        return launchSeq;
      };
      return launchContext.run({ parentSessionId: exec.agent.id, kind: 'tool', toolName: exec.name, callId: exec.rootCallId ?? exec.callId,
        launchSeq: resolveLaunchSeq,
        ...(typeof args?.description === 'string' ? { label: args.description } : {}),
        delegation: typeof args?.run_in_background === 'boolean' ? args.run_in_background ? 'background' : 'foreground'
          : ['send_message', 'send_user_message'].includes(exec.name) ? 'background' : 'unknown',
      }, next);
    }, { prepend: true });
    const self = this;
    ctx.on('subagent/start', function (info) {
      const parent = carrierKeyOf(this) as Agent | undefined;
      if (!parent?.id) return;
      const child = ctx.agents.get(info.id);
      const source = launchContext.getStore();
      const launch = source?.parentSessionId === parent.id ? source : undefined;
      const launchSeq = launch?.launchSeq?.();
      const descriptor = child?.session.ownEvents().find(event => event.type === 'subagent/descriptor');
      const label = launch?.label ?? (descriptor?.type === 'subagent/descriptor' ? descriptor.data.label : undefined);
      const startSeq = child && self.bounds.get(child);
      // Native omitted defaults follow the actual child mode, including configured tool instances.
      const delegation = launch?.delegation === 'unknown' && ['subagent', 'subagent_fork'].includes(launch.toolName ?? '') && descriptor?.type === 'subagent/descriptor'
        ? descriptor.data.mode === 'continuable' ? 'background' : 'foreground' : launch?.delegation ?? 'unknown';
      const run: TrajectoryRun = { runId: info.runId, parentSessionId: parent.id, sessionId: info.id, provider: info.provider,
        ...(label ? { label } : {}), kind: launch?.kind ?? 'unknown', delegation,
        ...(launchSeq !== undefined ? { launchSeq } : {}), ...(launch?.callId ? { callId: launch.callId } : {}),
        ...(startSeq !== undefined ? { startSeq } : {}), startedAt: Date.now(), state: 'running' };
      self.active.set(info.runId, run);
      // One-shot start can precede its descriptor; resolve omitted defaults when that fact arrives.
      if (delegation === 'unknown' && ['subagent', 'subagent_fork'].includes(launch?.toolName ?? '')) self.pendingDefaults.set(info.id, info.runId);
      self.persist(run);
    });
    ctx.on('subagent/end', function (info) {
      const parent = carrierKeyOf(this) as Agent | undefined;
      const run = self.active.get(info.runId);
      if (!run || run.parentSessionId !== parent?.id) return;
      const endSeq = self.tails.get(info.id);
      self.active.delete(info.runId);
      self.pendingDefaults.delete(info.id);
      self.persist({ ...run, ...(endSeq !== undefined && (run.startSeq === undefined || endSeq >= run.startSeq) ? { endSeq } : {}),
        endedAt: Date.now(), stopReason: info.stopReason,
        state: info.stopReason === 'completed' ? 'completed' : info.stopReason === 'aborted' ? 'cancelled' : 'failed' });
    });
  }

  /** Record one host-owned fork while retaining its native execution and disposal.
   *
   * Args:
   *   parent: Product Agent whose history the maintenance inherits.
   *   kind: Explicit maintenance purpose.
   *   label: Human-readable execution label.
   *   launchSeq: Parent event anchoring the accepted launch.
   *   run: Published native provider run held by the maintenance owner.
   * Returns:
   *   The same execution capability with an observed result promise.
   */
  knowledge(parent: Agent, kind: 'memory' | 'skills' | 'combined', label: string, launchSeq: number, run: SubagentRun): SubagentRun {
    const startSeq = run.localAgent && this.bounds.get(run.localAgent);
    const record: TrajectoryRun = { runId: randomUUID(), parentSessionId: parent.id, sessionId: run.id, provider: 'fork',
      kind, label, delegation: 'background', launchSeq, ...(startSeq !== undefined ? { startSeq } : {}), startedAt: Date.now(), state: 'running' };
    this.active.set(record.runId, record); this.persist(record);
    const finish = (stopReason: string) => {
      const endSeq = this.tails.get(run.id);
      this.active.delete(record.runId);
      this.persist({ ...record, ...(endSeq !== undefined && (startSeq === undefined || endSeq >= startSeq) ? { endSeq } : {}),
        endedAt: Date.now(), stopReason, state: stopReason === 'completed' ? 'completed' : stopReason === 'aborted' ? 'cancelled' : 'failed' });
    };
    return { ...run, result: run.result.then(result => { finish(result.stopReason); return result; }, error => { finish('error'); throw error; }) };
  }

  /** Register an empty-context host maintenance handle without a subagent catalog entry. */
  async startMaintenance(parent: Agent, child: Agent, runId: string, label: string): Promise<void> {
    const record: TrajectoryRun = { runId, parentSessionId: parent.id, sessionId: child.id, provider: 'native', kind: 'dreaming',
      label, delegation: 'background', launchSeq: parent.session.seq - 1, startSeq: child.session.seq, startedAt: Date.now(), state: 'running' };
    this.active.set(runId, record); this.persist(record); await this.writes;
  }
  /** Record actual host application state, independently of the model's final prose. */
  async finishMaintenance(runId: string, state: 'completed' | 'failed' | 'cancelled'): Promise<void> {
    const record = this.active.get(runId) ?? (await this.domain).table('runs').get(runId);
    if (!record) return;
    this.active.delete(runId);
    this.persist({ ...record, state, stopReason: state, endedAt: Date.now(), endSeq: this.tails.get(record.sessionId) ?? record.endSeq });
    await this.writes;
  }

  private indexRun(index: Map<string, Set<string>>, run: TrajectoryRun): void {
    for (const sessionId of [run.sessionId, run.parentSessionId]) {
      let ids = index.get(sessionId);
      if (!ids) { ids = new Set(); index.set(sessionId, ids); }
      ids.add(run.runId);
    }
  }

  private persist(run: TrajectoryRun): void {
    const task = this.writes = this.writes.then(async () => {
      const index = await this.runsBySession;
      await (await this.domain).table('runs').put(run.runId, run);
      this.indexRun(index, run);
    });
    this.pending.set(run.sessionId, task);
    const settled = () => { if (this.pending.get(run.sessionId) === task) this.pending.delete(run.sessionId); };
    void task.then(settled, settled); // Reads still report a failed durable write barrier.
  }

  /** Discard target run indexes after that target's accepted writes settle. */
  async forget(ids: ReadonlySet<string>): Promise<void> {
    await Promise.allSettled([...ids].map(id => this.pending.get(id)));
    const index = await this.runsBySession;
    const table = (await this.domain).table('runs');
    for (const id of ids) {
      this.tails.delete(id);
      this.pendingDefaults.delete(id);
      for (const runId of index.get(id) ?? []) {
        const run = table.get(runId);
        if (run && ids.has(run.sessionId)) {
          this.active.delete(runId);
          index.get(run.parentSessionId)?.delete(runId);
          index.get(run.sessionId)?.delete(runId);
        }
      }
    }
  }

  /** Read directly related runs after accepted observations have been saved.
   *
   * Args:
   *   sessionId: Identity already authorized by the fixed trajectory observer.
   * Returns:
   *   Own and directly launched epochs in start order; orphaned starts are unknown.
   * Raises:
   *   Storage errors if the durable observation barrier could not be completed.
   */
  async read(sessionId: string): Promise<TrajectoryRun[]> {
    const table = (await this.domain).table('runs');
    // Lifecycle callbacks may enqueue an end while a start write is in flight.
    let barrier: Promise<void>;
    do { barrier = this.writes; await barrier; } while (barrier !== this.writes);
    const ids = (await this.runsBySession).get(sessionId) ?? [];
    return [...ids].map(id => table.get(id)!)
      .map(run => ({ ...run, state: run.state === 'running' && !this.active.has(run.runId) ? 'unknown' : run.state }))
      .sort((a, b) => a.startedAt - b.startedAt || a.runId.localeCompare(b.runId));
  }
}
