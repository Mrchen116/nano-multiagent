import { createHash } from 'node:crypto';
import type { ModelRunProjection } from '@nano/product-contracts';
import {
  defineDomain,
  domainTable,
  type Domain,
  type DomainSpec,
  type DomainTableSpec,
} from '@deepseek-ai/dsh-storage-domain';
import { freezeMessage, MessageId, type UserMessage } from '@deepseek-ai/dsh-llm';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { SessionEvent } from '@deepseek-ai/dsh-session';
import { z } from 'zod';
import type { AgentConfiguration } from './index.js';
import type { ModelRoute } from './model-policy.js';
import { indexedInputs, inputEvidence, inputIdsForTurn } from './input-evidence.js';
import { ModelRunIndex } from './model-run-index.js';
import { RecordWrites } from './record-writes.js';

declare module '@deepseek-ai/dsh-llm' {
  interface MessageSourceMap {
    'nano-fallback': { kind: 'nano-fallback'; logicalRunId: string };
  }
}
interface Attempt {
  turn: number;
  route: ModelRoute;
  inputIds?: string[];
  error?: { message: string; code: string; status?: number };
}
export interface ModelRun {
  id: string;
  sessionId: string;
  revision: string;
  turn: number;
  inputs: string[];
  attempts: Attempt[];
  state: 'running' | 'switching' | 'completed';
  terminal?: unknown;
  pending?: { route: ModelRoute; messages: UserMessage[] };
  switched?: string;
  withdrawn?: string[];
}
interface RunDomain extends DomainSpec {
  tables: { runs: DomainTableSpec<string, ModelRun> };
}
const route = z.object({
  provider: z.string(),
  model: z.string(),
  reasoningEffort: z.string().optional(),
  maxTokens: z.number().optional(),
});
export const modelRunsDomain: RunDomain = defineDomain({
  name: 'nano_model_runs',
  version: 1,
  layout: 'per-record',
  tables: {
    runs: domainTable(
      z.object({
        id: z.string(),
        sessionId: z.string(),
        revision: z.string(),
        turn: z.number(),
        inputs: z.array(z.string()),
        attempts: z.array(
          z.object({
            turn: z.number(),
            route,
            inputIds: z.array(z.string()).optional(),
            error: z.object({ message: z.string(), code: z.string(), status: z.number().optional() }).optional(),
          }),
        ),
        state: z.enum(['running', 'switching', 'completed']),
        terminal: z.unknown().optional(),
        pending: z.object({ route, messages: z.array(z.custom<UserMessage>()) }).optional(),
        switched: z.string().optional(),
        withdrawn: z.array(z.string()).optional(),
      }),
    ),
  },
});
const key = (id: string) => Buffer.from(id).toString('base64url');
const available = (error: { code: string; status?: number }) =>
  [
    'AUTH',
    'INVALID_CREDENTIAL',
    'MISSING_CREDENTIAL',
    'RATE_LIMIT',
    'QUOTA',
    'ACCOUNT_QUOTA',
    'OVERLOADED',
    'TIMEOUT',
    'NETWORK',
    'TRANSPORT',
    'SERVER',
    'SERVER_ERROR',
    'EMPTY_RESPONSE',
  ].includes(error.code) ||
  error.status === 401 ||
  error.status === 402 ||
  error.status === 429 ||
  (error.status !== undefined && error.status >= 500 && error.status <= 599);
interface Host {
  route(agent: Agent): ModelRoute;
  select(agent: Agent, route: ModelRoute | undefined): void;
  sticky(agent: Agent, route: ModelRoute): Promise<void>;
  check(agent: Agent, run: ModelRun): Promise<{ published: boolean }>;
  notify(sessionId: string): void;
}

/** Coordinates finite native turns; the native loop owns every model and tool step. */
export class ModelFallback {
  private readonly storage: Promise<Domain<RunDomain>>;
  private readonly runs = new Map<string, ModelRun>();
  private readonly runsBySession = new Map<string, ModelRunIndex>();
  private readonly workModels = new Map<string, {byTurn: Map<number, ModelRunProjection>; hashes: Map<string, bigint>; digest: bigint}>();
  readonly ready: Promise<void>;
  private readonly agents = new Map<string, { agent: Agent; config: AgentConfiguration }>();
  private readonly attachedSessions = new Set<string>();
  private readonly tasks = new Map<string, Promise<void>>();
  private readonly epochs = new Map<string, number>();
  private readonly writes: RecordWrites<ModelRun>;
  private stopped = false;
  constructor(
    private readonly ctx: Context,
    private readonly host: Host,
  ) {
    this.storage = ctx.storageDomain.open(modelRunsDomain);
    this.writes = new RecordWrites(async (id, snapshot) => {
      await (await this.storage).table('runs').put(key(id), snapshot);
    });
    this.ready = this.storage.then(storage => {
      for (const [, record] of storage.table('runs').entries()) {
        const run = this.runs.get(record.id) ?? record;
        this.remember(run);
        this.updateWorkModel(run);
      }
    });
    ctx.on('session/event', (session, event) => {
      const item = this.agents.get(session.id);
      if (item) this.observe(item.agent, item.config, event);
    });
  }
  /** Includes continuation work that may outlive the public Agent running state. */
  get busy(): boolean {
    // Cold sidecars are historical evidence until their Session attaches.
    return this.writes.busy || this.tasks.size > 0 || [...this.attachedSessions].some(id => this.hasActive(id));
  }
  async attach(agent: Agent, config: AgentConfiguration) {
    this.agents.set(agent.id, { agent, config });
    await this.ready;
    this.attachedSessions.add(agent.id);
    const active = this.runsBySession.get(agent.id)?.latestActive(() => true);
    if (active) {
      const history = agent.session.snapshotEvents();
      const end = history.findLast(
        (event) => event.type === 'turn/end' && active.attempts.some((attempt) => attempt.turn === event.data.turn),
      );
      if (active.revision !== config.revision) this.finish(active, { kind: 'cancelled' });
      else if (active.pending) {
        const inputs = config.mode === 'global' ? indexedInputs(agent.session) : undefined;
        const evidence = active.pending.messages.map((message) => inputs?.evidence(message.id) ?? inputEvidence(history, message.id));
        const consumed = evidence.find((item) => item.turn !== undefined && item.turn !== active.attempts.at(-1)?.turn);
        if (consumed) {
          active.attempts.push({ turn: consumed.turn!, route: active.pending.route });
          active.state = 'running';
          delete active.pending;
          this.remember(active);
          this.updateWorkModel(active);
          const terminal = history.findLast((event) => event.type === 'turn/end' && event.data.turn === consumed.turn);
          if (terminal) this.observe(agent, config, terminal);
        } else if (
          evidence.some((item) => (item.terminal as { kind?: string })?.kind === 'cancelled-before-consumption')
        )
          this.finish(active, { kind: 'cancelled' });
        else {
          this.host.select(agent, active.pending.route);
          this.schedule(agent, config, active);
        }
      } else if (end) this.observe(agent, config, end);
    }
    agent.ctx.effect(() => () => {
      this.interrupt(agent);
      this.agents.delete(agent.id);
    });
  }
  list(sessionId: string) {
    return this.runsBySession.get(sessionId)?.all() ?? [];
  }

  hasActive(sessionId: string): boolean {
    return this.runsBySession.get(sessionId)?.hasActive ?? false;
  }

  private remember(run: ModelRun) {
    this.runs.set(run.id, run);
    let runs = this.runsBySession.get(run.sessionId);
    if (!runs) this.runsBySession.set(run.sessionId, runs = new ModelRunIndex());
    runs.update(run);
  }

  /** Return immutable Work metadata, excluding the retry's model input and other internal state. */
  workModel(sessionId: string, turn: number): ModelRunProjection | undefined {
    return this.workModels.get(sessionId)?.byTurn.get(turn);
  }

  /** Order-independent version of the projected model runs, stable across reload. */
  workVersion(sessionId: string): string {
    const state = this.workModels.get(sessionId);
    return `work:${state?.hashes.size ?? 0}:${state?.digest.toString(16) ?? '0'}`;
  }

  private updateWorkModel(run: ModelRun): void {
    const {id, sessionId, turn, state, attempts, terminal, switched} = run;
    const projection: ModelRunProjection = structuredClone({id, sessionId, turn, state, terminal, switched,
      attempts: attempts.map(({turn, route:{provider, model}, error}) => ({turn, route:{provider, model}, error}))});
    let index = this.workModels.get(sessionId);
    if (!index) {
      index = {byTurn:new Map(), hashes:new Map(), digest:0n};
      this.workModels.set(sessionId, index);
    }
    const hash = BigInt('0x' + createHash('sha256').update(JSON.stringify(projection)).digest('hex'));
    index.digest ^= (index.hashes.get(id) ?? 0n) ^ hash;
    index.hashes.set(id, hash);
    for (const attempt of projection.attempts) index.byTurn.set(attempt.turn, projection);
  }

  evidence(agent: Agent, inputId: string) {
    const evidence = this.nativeEvidence(agent, inputId);
    const run = this.runsBySession.get(agent.id)?.forInput(inputId);
    return run
      ? {
          ...evidence,
          turn: run.turn,
          turns: run.attempts.map((attempt) => attempt.turn),
          terminal: run.state === 'completed' ? run.terminal : undefined,
        }
      : evidence;
  }
  nativeEvidence(agent: Agent, inputId: string) {
    return this.agents.get(agent.id)?.config.mode === 'global'
      ? indexedInputs(agent.session).evidence(inputId)
      : inputEvidence(agent.session.snapshotEvents(), inputId);
  }

  interrupt(agent: Agent) {
    this.epochs.set(agent.id, (this.epochs.get(agent.id) ?? 0) + 1);
    for (const run of this.runsBySession.get(agent.id)?.active() ?? [])
      if (
        run.state === 'switching' ||
        (run.state === 'running' &&
          run.attempts.length > 1 &&
          !agent.session
            .snapshotEvents()
            .some((event) => event.type === 'step/start' && event.data.turn === run.attempts.at(-1)!.turn))
      ) {
        // A claimed recovery cannot be removed from the queue; abort only that
        // pre-step and retain all other inputs so the incoming followup can wake it.
        if (run.state === 'running') agent.cancel({ kind: 'user' }, { keepInbox: true });
        run.withdrawn = run.pending?.messages.map((message) => message.id) ?? run.attempts.at(-1)?.inputIds;
        for (const message of run.pending?.messages ?? []) agent.inbox.remove(message.id);
        this.host.select(agent, undefined);
        this.finish(run, { kind: 'cancelled' });
      }
  }
  async checkpoint() {
    await this.writes.flush();
  }
  allowed(agent: Agent, messages: UserMessage[]) {
    const runs = this.runsBySession.get(agent.id);
    return messages.filter((message) => !runs?.wasWithdrawn(message.id));
  }
  private save(run: ModelRun) {
    this.remember(run);
    this.updateWorkModel(run);
    return this.writes.put(run.id, structuredClone(run));
  }
  private finish(run: ModelRun, terminal: unknown) {
    run.state = 'completed';
    run.terminal = terminal;
    delete run.pending;
    void this.save(run).then(
      () => this.host.notify(run.sessionId),
      () => this.host.notify(run.sessionId),
    );
  }
  private observe(agent: Agent, config: AgentConfiguration, event: SessionEvent) {
    const runs = this.runsBySession.get(agent.id);
    if (event.type === 'turn/start') {
      const pending = runs?.latestActive(run => run.state === 'switching' && !!run.pending);
      if (pending) {
        pending.attempts.push({
          turn: event.data.turn,
          route: pending.pending!.route,
          inputIds: pending.pending!.messages.map((message) => message.id),
        });
        pending.state = 'running';
        delete pending.pending;
        void this.save(pending);
      } else {
        const run: ModelRun = {
          id: `${agent.id}:${event.data.turn}`,
          sessionId: agent.id,
          revision: config.revision,
          turn: event.data.turn,
          inputs: [],
          attempts: [{ turn: event.data.turn, route: this.host.route(agent) }],
          state: 'running',
        };
        void this.save(run);
      }
      return;
    }
    if (event.type !== 'turn/end') return;
    const run = runs?.forAttempt(event.data.turn);
    if (!run || run.state === 'completed') return;
    const ids = config.mode === 'global'
      ? indexedInputs(agent.session).idsForTurn(event.data.turn)
      : inputIdsForTurn(agent.session.snapshotEvents(), event.data.turn);
    const count = run.inputs.length;
    for (const id of ids)
      if (!id.startsWith('nano-fallback:') && !run.inputs.includes(id)) run.inputs.push(id);
    if (run.inputs.length !== count) this.remember(run);
    const attempt = run.attempts.at(-1)!;
    const reason = event.data.reason;
    if (reason.kind === 'error') attempt.error = reason.error;
    const candidates = this.candidates(config, run);
    const newer = [...agent.inbox.nextTurn, ...agent.inbox.nextStep].some(
      (message) => !run.inputs.includes(message.id) && message.source.kind !== 'nano-fallback',
    );
    if (
      reason.kind === 'error' &&
      available(reason.error) &&
      candidates.length &&
      !newer &&
      !this.stopped &&
      !agent.session.snapshotEvents().some(event => event.type === 'tool/call' && run.attempts.some(attempt => attempt.turn === event.data.turn))
    ) {
      run.state = 'switching';
      run.terminal = reason;
      void this.save(run);
      this.schedule(agent, config, run);
    } else if (reason.kind === 'completed' && run.attempts.length > 1) {
      this.scheduleSuccess(agent, run, attempt.route, reason);
    } else {
      this.host.select(agent, undefined);
      this.finish(run, reason);
    }
  }
  private candidates(config: AgentConfiguration, run: ModelRun) {
    return (config.modelFallbacks ?? []).filter(
      (candidate) =>
        !run.attempts.some(
          (attempt) => attempt.route.provider === candidate.provider && attempt.route.model === candidate.model,
        ),
    );
  }
  private scheduleSuccess(agent: Agent, run: ModelRun, route: ModelRoute, reason: unknown) {
    const task = (async () => {
      await this.host.sticky(agent, route);
      run.switched = route.model;
      this.host.select(agent, undefined);
      this.finish(run, reason);
      await this.writes.settled();
    })().catch((error) => {
      this.finish(run, { kind: 'error', error: { code: 'PERSISTENCE', message: String(error) } });
    });
    this.tasks.set(run.id, task);
    void task.finally(() => {
      if (this.tasks.get(run.id) === task) this.tasks.delete(run.id);
    });
  }
  private schedule(agent: Agent, config: AgentConfiguration, run: ModelRun) {
    if (this.tasks.has(run.id)) return;
    const epoch = this.epochs.get(agent.id) ?? 0;
    const valid = () =>
      !this.stopped &&
      run.state === 'switching' &&
      this.agents.has(agent.id) &&
      run.revision === config.revision &&
      epoch === (this.epochs.get(agent.id) ?? 0);
    const task = (async () => {
      await agent.whenIdle();
      if (!valid()) return;
      await agent.runMaintenance(async (signal) => {
        if (!valid() || signal.aborted) return;
        // Recovery must see the failed native turn as well as its switching sidecar.
        if (!(await this.ctx.sessions.flush(agent.session)))
          throw new Error('Fallback turn has no persistence barrier');
        await this.checkpoint();
        if (!valid() || signal.aborted) return;
        const published = await this.host.check(agent, run);
        if (!valid() || signal.aborted) return;
        if (published.published) {
          this.host.select(agent, undefined);
          this.finish(run, run.terminal);
          return;
        }
        if (!run.pending) {
          const next = this.candidates(config, run)[0];
          if (!next) {
            this.finish(run, run.terminal);
            return;
          }
          const history = agent.session.snapshotEvents();
          const unadmitted = run.inputs.filter((id) => inputEvidence(history, id).consumedSeq === undefined);
          const originals = unadmitted.flatMap((id) =>
            history
              .flatMap((event) =>
                event.type === 'agent/inbox/spliced' ? event.data.inserted.filter((message) => message.id === id) : [],
              )
              .slice(0, 1),
          );
          const messages = originals.length
            ? originals
            : [
                freezeMessage({
                  id: MessageId(`nano-fallback:${run.id}:${run.attempts.length}`),
                  role: 'user' as const,
                  content: [
                    {
                      type: 'text' as const,
                      text: 'Continue the original request after the previous model failed. This is automatic recovery, not new human instruction or authorization.',
                    },
                  ],
                  source: { kind: 'nano-fallback' as const, logicalRunId: run.id },
                }),
              ];
          run.pending = { route: next, messages };
          await this.save(run);
          if (!valid() || signal.aborted) return;
        }
        this.host.select(agent, run.pending.route);
        for (const message of run.pending.messages) {
          const evidence = this.nativeEvidence(agent, message.id);
          if (!evidence.pending && evidence.consumedSeq === undefined) agent.followup(freezeMessage(message));
        }
        if (!(await this.ctx.sessions.flush(agent.session)))
          throw new Error('Fallback inbox has no persistence barrier');
        if (!valid() || signal.aborted) {
          for (const message of run.pending?.messages ?? []) agent.inbox.remove(message.id);
          this.host.select(agent, undefined);
        }
      });
    })().catch((error) => {
      this.host.select(agent, undefined);
      this.finish(run, { kind: 'error', error: { code: 'PERSISTENCE', message: String(error) } });
    });
    this.tasks.set(run.id, task);
    void task.finally(() => {
      if (this.tasks.get(run.id) === task) this.tasks.delete(run.id);
      this.host.notify(agent.id);
      if (run.state === 'switching' && !run.pending) this.schedule(agent, config, run);
    });
  }
  /** Invalidate durable unfinished attempts before any restored Agent can attach. */
  async cancelPersisted(owns: (sessionId: string) => boolean = () => true,
    coldOwns?: (sessionId: string) => Promise<boolean>): Promise<void> {
    await this.ready;
    for (const {agent} of this.agents.values()) if (owns(agent.id)) this.interrupt(agent);
    await Promise.allSettled([...this.tasks].filter(([id]) => {
      const run = this.runs.get(id);
      return run && owns(run.sessionId);
    }).map(([, task]) => task));
    for (const runs of this.runsBySession.values()) for (const run of runs.active()) {
      if ((owns(run.sessionId) || await coldOwns?.(run.sessionId)) && run.state !== 'completed') this.finish(run, {kind: 'cancelled', reason: 'agent_disabled'});
    }
    await this.checkpoint();
  }
  /** Discard snapshots and in-memory records for the retired Sessions. */
  async forget(sessionIds: ReadonlySet<string>): Promise<void> {
    await this.writes.forget((_, run) => sessionIds.has(run.sessionId));
    for (const id of sessionIds) {
      for (const run of this.list(id)) this.runs.delete(run.id);
      this.runsBySession.delete(id);
      this.attachedSessions.delete(id);
      this.workModels.delete(id);
      this.epochs.delete(id);
    }
  }
  async stop() {
    this.stopped = true;
    for (const { agent } of this.agents.values()) this.interrupt(agent);
    await Promise.allSettled(this.tasks.values());
    await this.writes.settled();
    await (await this.storage).close();
  }
}
