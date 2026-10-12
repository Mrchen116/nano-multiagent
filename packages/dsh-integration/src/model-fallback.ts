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
import { inputEvidence } from './input-evidence.js';

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
const domain: RunDomain = defineDomain({
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
  private readonly agents = new Map<string, { agent: Agent; config: AgentConfiguration }>();
  private readonly tasks = new Map<string, Promise<void>>();
  private readonly epochs = new Map<string, number>();
  private writes: Promise<void> = Promise.resolve();
  private failure: unknown;
  private stopped = false;
  constructor(
    private readonly ctx: Context,
    private readonly host: Host,
  ) {
    this.storage = ctx.storageDomain.open(domain);
    ctx.on('session/event', (session, event) => {
      const item = this.agents.get(session.id);
      if (item) this.observe(item.agent, item.config, event);
    });
  }
  async attach(agent: Agent, config: AgentConfiguration) {
    this.agents.set(agent.id, { agent, config });
    for (const [, run] of (await this.storage).table('runs').entries())
      if (run.sessionId === agent.id) this.runs.set(run.id, run);
    const active = this.list(agent.id).findLast((run) => run.state !== 'completed');
    if (active) {
      const history = agent.session.snapshotEvents();
      const end = history.findLast(
        (event) => event.type === 'turn/end' && active.attempts.some((attempt) => attempt.turn === event.data.turn),
      );
      if (active.revision !== config.revision) this.finish(active, { kind: 'cancelled' });
      else if (active.pending) {
        const evidence = active.pending.messages.map((message) => inputEvidence(history, message.id));
        const consumed = evidence.find((item) => item.turn !== undefined && item.turn !== active.attempts.at(-1)?.turn);
        if (consumed) {
          active.attempts.push({ turn: consumed.turn!, route: active.pending.route });
          active.state = 'running';
          delete active.pending;
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
    return [...this.runs.values()].filter((run) => run.sessionId === sessionId);
  }
  evidence(agent: Agent, inputId: string) {
    const evidence = inputEvidence(agent.session.snapshotEvents(), inputId);
    const run = this.list(agent.id).findLast((run) => run.inputs.includes(inputId));
    return run
      ? {
          ...evidence,
          turn: run.turn,
          turns: run.attempts.map((attempt) => attempt.turn),
          terminal: run.state === 'completed' ? run.terminal : undefined,
        }
      : evidence;
  }
  interrupt(agent: Agent) {
    this.epochs.set(agent.id, (this.epochs.get(agent.id) ?? 0) + 1);
    for (const run of this.list(agent.id))
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
    await this.writes;
    if (this.failure) throw this.failure;
  }
  allowed(agent: Agent, messages: UserMessage[]) {
    return messages.filter((message) => !this.list(agent.id).some((run) => run.withdrawn?.includes(message.id)));
  }
  private save(run: ModelRun) {
    const snapshot = structuredClone(run);
    const task = this.writes.then(async () => {
      if (this.failure) throw this.failure;
      await (await this.storage).table('runs').put(key(run.id), snapshot);
    });
    this.writes = task.catch((error) => {
      this.failure ??= error;
    });
    return task;
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
    if (event.type === 'turn/start') {
      const pending = this.list(agent.id).findLast((run) => run.state === 'switching' && run.pending);
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
        this.runs.set(run.id, run);
        void this.save(run);
      }
      return;
    }
    if (event.type !== 'turn/end') return;
    const run = this.list(agent.id).findLast((run) => run.attempts.some((attempt) => attempt.turn === event.data.turn));
    if (!run || run.state === 'completed') return;
    const history = agent.session.snapshotEvents();
    const ids = history.flatMap((event) =>
      event.type === 'agent/inbox/spliced' ? event.data.inserted.map((message) => message.id) : [],
    );
    for (const id of ids)
      if (
        inputEvidence(history, id).turn === event.data.turn &&
        !id.startsWith('nano-fallback:') &&
        !run.inputs.includes(id)
      )
        run.inputs.push(id);
    const attempt = run.attempts.at(-1)!;
    const reason = event.data.reason;
    if (reason.kind === 'error') attempt.error = reason.error;
    const executed = history.some(
      (event) => event.type === 'tool/call' && run.attempts.some((attempt) => attempt.turn === event.data.turn),
    );
    const candidates = this.candidates(config, run);
    const newer = [...agent.inbox.nextTurn, ...agent.inbox.nextStep].some(
      (message) => !run.inputs.includes(message.id) && message.source.kind !== 'nano-fallback',
    );
    if (
      reason.kind === 'error' &&
      available(reason.error) &&
      candidates.length &&
      !executed &&
      !newer &&
      !this.stopped
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
      await this.writes;
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
          const evidence = inputEvidence(agent.session.snapshotEvents(), message.id);
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
  async stop() {
    this.stopped = true;
    for (const { agent } of this.agents.values()) this.interrupt(agent);
    await Promise.allSettled(this.tasks.values());
    await this.writes;
    await (await this.storage).close();
  }
}
