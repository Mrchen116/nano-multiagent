import { AsyncLocalStorage } from 'node:async_hooks';
import { Service, type Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { carrierKeyOf } from '@deepseek-ai/dsh-scope';
import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import type {} from '@deepseek-ai/dsh-subagent';
import type { TrajectoryRun } from '@nano/product-contracts';
import { z } from 'zod';

interface RunDomain extends DomainSpec { tables: { runs: DomainTableSpec<string, TrajectoryRun> } }
const runDomain: RunDomain = defineDomain({ name: 'nano_trajectory_runs', version: 1, layout: 'per-record', tables: {
  runs: domainTable(z.object({
    runId: z.string(), parentSessionId: z.string(), sessionId: z.string(), provider: z.string(), label: z.string().optional(),
    kind: z.enum(['tool', 'memory', 'skills', 'combined', 'unknown']), delegation: z.enum(['foreground', 'background', 'unknown']),
    launchSeq: z.number().optional(), callId: z.string().optional(), startSeq: z.number().optional(), endSeq: z.number().optional(),
    startedAt: z.number(), endedAt: z.number().optional(), stopReason: z.string().optional(),
    state: z.enum(['running', 'completed', 'failed', 'cancelled', 'unknown']),
  })),
} });
interface Launch { toolName?: string; parentSessionId: string; kind: TrajectoryRun['kind']; delegation: TrajectoryRun['delegation']; launchSeq?: number; callId?: string; label?: string }
const launchContext = new AsyncLocalStorage<Launch>();

/** Attach explicit maintenance provenance to the actual subagent start operation.
 *
 * Args:
 *   agent: Live parent whose last accepted event anchors the launch.
 *   kind: Maintenance purpose supplied by its owner, never decoded from labels.
 *   start: Actual native start operation to run inside this asynchronous context.
 * Returns:
 *   The unchanged start result; errors propagate to the original caller.
 */
export function withKnowledgeRun<T>(agent: Agent, kind: 'memory' | 'skills' | 'combined', start: () => T): T {
  return launchContext.run({ parentSessionId: agent.id, kind, delegation: 'background', launchSeq: agent.session.seq - 1 }, start);
}

declare module '@deepseek-ai/cordis' { interface Context { nanoTrajectoryRuns: TrajectoryRuns } }

/** Persist lifecycle observations separately from the immutable native session log. */
export class TrajectoryRuns extends Service {
  private readonly domain;
  private writes = Promise.resolve();
  private readonly bounds = new WeakMap<Agent, number>();
  private readonly tails = new Map<string, number>();
  private readonly active = new Map<string, TrajectoryRun>();
  private readonly pendingDefaults = new Map<string, string>();

  constructor(ctx: Context) {
    super(ctx, 'nanoTrajectoryRuns');
    this.domain = ctx.storageDomain.open(runDomain);
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
      const call = exec.agent.session.snapshotEvents().findLast(event => event.type === 'tool/call' && event.data.callId === (exec.rootCallId ?? exec.callId));
      return launchContext.run({ parentSessionId: exec.agent.id, kind: 'tool', toolName: exec.name, callId: exec.rootCallId ?? exec.callId,
        ...(call ? { launchSeq: call.seq } : {}),
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
      const descriptor = child?.session.ownEvents().find(event => event.type === 'subagent/descriptor');
      const label = launch?.label ?? (descriptor?.type === 'subagent/descriptor' ? descriptor.data.label : undefined);
      const startSeq = child && self.bounds.get(child);
      // Native omitted defaults follow the actual child mode, including configured tool instances.
      const delegation = launch?.delegation === 'unknown' && ['subagent', 'subagent_fork'].includes(launch.toolName ?? '') && descriptor?.type === 'subagent/descriptor'
        ? descriptor.data.mode === 'continuable' ? 'background' : 'foreground' : launch?.delegation ?? 'unknown';
      const run: TrajectoryRun = { runId: info.runId, parentSessionId: parent.id, sessionId: info.id, provider: info.provider,
        ...(label ? { label } : {}), kind: launch?.kind ?? 'unknown', delegation,
        ...(launch?.launchSeq !== undefined ? { launchSeq: launch.launchSeq } : {}), ...(launch?.callId ? { callId: launch.callId } : {}),
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

  private persist(run: TrajectoryRun): void {
    this.writes = this.writes.then(async () => { await (await this.domain).table('runs').put(run.runId, run); });
    void this.writes.catch(() => {}); // Reads report a failed durable write barrier instead of fabricated saved facts.
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
    return [...table.entries()].map(([, run]) => run)
      .filter(run => run.sessionId === sessionId || run.parentSessionId === sessionId)
      .map(run => ({ ...run, state: run.state === 'running' && !this.active.has(run.runId) ? 'unknown' : run.state }))
      .sort((a, b) => a.startedAt - b.startedAt || a.runId.localeCompare(b.runId));
  }
}
