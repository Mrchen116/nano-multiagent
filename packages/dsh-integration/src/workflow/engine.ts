import { AsyncLocalStorage } from "node:async_hooks";
import { randomUUID } from "node:crypto";
import {
  WorkflowEngine,
  WorkflowRunId,
  type WorkflowRun,
  type WorkflowStartRequest,
  type WorkflowResult,
} from "@deepseek-ai/dsh-workflow";
import type { Context } from "@deepseek-ai/cordis";
import type { Agent } from "@deepseek-ai/dsh-agent";
import type { Domain } from "@deepseek-ai/dsh-storage-domain";
import type { PtcJsonValue } from "@deepseek-ai/dsh-ptc-runtime";
import type { ObjectJsonSchema } from "@deepseek-ai/dsh-tools";
import type {} from "@deepseek-ai/dsh-sandbox-policy";
import { ReasoningEffortId } from "@deepseek-ai/dsh-llm";
import { SessionId, type Session } from "@deepseek-ai/dsh-session";
import type { AgentConfiguration } from "../index.js";
import { WorkflowControl, type CallOptions } from "./control.js";
import { workflowProgram } from "./guest.js";
import { outputTokens } from "./budget.js";
import {
  workflowDomain,
  type WorkflowDomain,
  type WorkflowRecord,
  type BudgetRecord,
} from "./state.js";
import { WorkflowCatalog } from "./catalog.js";

interface Options {
  configuration(agent: Agent): AgentConfiguration;
  completed(record: WorkflowRecord): void;
}
interface Live {
  handle: WorkflowRun;
  record: WorkflowRecord;
  control: WorkflowControl;
  abort: AbortController;
}
export interface NanoWorkflowRequest extends WorkflowStartRequest {
  resumeFromRunId?: string;
  outputTokenTarget?: number;
}
const key = (value: string) => Buffer.from(value).toString("base64url");

/** One durable Workflow owner built on public PTC and subagent services. */
export class NanoWorkflowEngine extends WorkflowEngine {
  static inject = [
    "subagents",
    "ptcRuntime",
    "sandboxPolicy",
    "storageDomain",
    "sessions",
    "sessionQuery",
    "nanoModels",
    "nanoApproval",
    "tools",
  ];
  private readonly storage: Promise<Domain<WorkflowDomain>>;
  private readonly host: Context;
  private readonly live = new Map<string, Live>();
  private readonly budgets = new Map<string, BudgetRecord>();
  private readonly creating = new AsyncLocalStorage<AgentConfiguration>();
  private writes = Promise.resolve();
  private readonly ready: Promise<void>;
  private stopping = false;
  constructor(
    ctx: Context,
    private readonly options: Options,
  ) {
    super(ctx);
    this.host = ctx;
    this.storage = ctx.storageDomain.open(workflowDomain);
    this.ready = this.recover();
    ctx.on("session/event", (session, event) => {
      if (
        event.type !== "assistant/message" &&
        event.type !== "assistant/attempt"
      )
        return;
      void this.ready
        .then(async () => {
          for (const budget of this.budgets.values()) {
            if (budget.parentSessionId === session.id)
              this.refreshParent(budget);
            if (budget.sources[session.id]) {
              this.observeBudget(budget, session);
              await this.saveBudget(budget);
            }
          }
        })
        .catch((error) => ctx.logger("nano-workflow").warn(String(error)));
    });
    ctx.effect(() => async () => {
      await this.stop();
      await (await this.storage).close();
    });
  }
  childConfiguration(parent: AgentConfiguration): AgentConfiguration {
    return this.creating.getStore() ?? parent;
  }
  private async recover() {
    const storage = await this.storage;
    for (const [, budget] of storage.table("budgets").entries())
      this.budgets.set(budget.id, budget);
    for (const [, record] of storage.table("runs").entries())
      this.recoveredRecords.set(record.id, record);
    for (const [id, record] of storage.table("runs").entries())
      if (record.state === "running" || record.state === "paused") {
        await storage.table("runs").put(id, {
          ...record,
          state: "interrupted",
          endedAt: Date.now(),
          revision: record.revision + 1,
        });
      }
  }
  private save(record: WorkflowRecord) {
    record.revision++;
    const snapshot = structuredClone(record);
    return this.enqueue(async () => {
      await (await this.storage).table("runs").put(key(record.id), snapshot);
    });
  }
  private enqueue(write: () => Promise<void>) {
    const task = this.writes.then(write);
    this.writes = task;
    return task;
  }
  private saveBudget(budget: BudgetRecord) {
    const snapshot = structuredClone(budget);
    return this.enqueue(async () => {
      await (await this.storage).table("budgets").put(key(budget.id), snapshot);
    });
  }
  private refreshParent(budget: BudgetRecord) {
    const run = this.host.nanoModels.fallback
      .list(budget.parentSessionId)
      .find((run) => run.id === budget.id);
    if (run)
      budget.sources[budget.parentSessionId]!.turns = run.attempts.map(
        (attempt) => attempt.turn,
      );
  }
  private observeBudget(budget: BudgetRecord, session: Session) {
    const source = budget.sources[session.id]!;
    source.output = outputTokens(
      session.snapshotEvents().filter((event) => session.isOwnSeq(event.seq)),
      source.turns,
    );
  }
  private async spent(budget: BudgetRecord) {
    this.refreshParent(budget);
    for (const [sessionId, source] of Object.entries(budget.sources)) {
      const live = this.host.sessions.get(SessionId(sessionId));
      if (live) this.observeBudget(budget, live);
      else {
        using observation = await this.host.sessionQuery.observeSession(
          SessionId(sessionId),
        );
        source.output = outputTokens(
          observation.events.slice(observation.inheritedEventCount),
          source.turns,
        );
      }
    }
    await this.saveBudget(budget);
    return Object.values(budget.sources).reduce(
      (sum, source) => sum + source.output,
      0,
    );
  }
  private async remaining(budget: BudgetRecord) {
    const spent = await this.spent(budget);
    return budget.target === null ? null : Math.max(0, budget.target - spent);
  }
  async read(parent: Agent, id?: string) {
    await this.ready;
    const records = [...(await this.storage).table("runs").entries()]
      .map(([, record]) => record)
      .filter(
        (record) =>
          record.parentSessionId === parent.id && (!id || record.id === id),
      );
    if (id && !records.length)
      throw new Error("Workflow does not belong to this parent Session");
    for (const budgetId of new Set(records.map((record) => record.budgetId))) {
      const budget = this.budgets.get(budgetId);
      if (budget) await this.spent(budget);
    }
    // Public tool outputs must omit optional undefined fields, just like persisted JSON.
    return JSON.parse(JSON.stringify(records.map((record) => this.project(record)))) as ReturnType<NanoWorkflowEngine["project"]>[];
  }
  private project(record: WorkflowRecord) {
    const budget = this.budgets.get(record.budgetId);
    const shared = Object.values(budget?.sources ?? {}).reduce(
      (sum, source) => sum + source.output,
      0,
    );
    const calls = record.calls.map((call) => ({
      ...call,
      outputTokens: call.attempts.reduce(
        (sum, attempt) => sum + (budget?.sources[attempt.id]?.output ?? 0),
        0,
      ),
    }));
    const phases: Record<string, number> = {};
    for (const call of calls) {
      const phase = call.options.phase ?? "";
      phases[phase] = (phases[phase] ?? 0) + call.outputTokens;
    }
    return {
      ...record,
      calls,
      durationMs: (record.endedAt ?? Date.now()) - record.startedAt,
      usage: {
        outputTokens: calls.reduce((sum, call) => sum + call.outputTokens, 0),
        sharedOutputTokens: shared,
        target: budget?.target ?? null,
        remaining:
          budget?.target === null || !budget
            ? null
            : Math.max(0, budget.target - shared),
        phases,
      },
    };
  }
  async launch(request: NanoWorkflowRequest): Promise<WorkflowRun> {
    await this.ready;
    if (request.resumeFromRunId) {
      const prior = (
        await this.read(request.parent, request.resumeFromRunId)
      )[0]!;
      this.recoveredRecords.set(prior.id, prior);
      if (this.live.has(prior.id))
        throw new Error("Use resume control for a live paused Workflow");
      request = {
        ...request,
        script: request.script ?? prior.script,
        args: request.args === undefined ? prior.args : request.args,
        meta: request.meta ?? prior.meta,
      };
    }
    const run = this.start(request);
    await this.save(this.live.get(run.id)!.record);
    return run;
  }
  start(request: NanoWorkflowRequest): WorkflowRun {
    if (this.stopping) throw new Error("Workflow engine is stopping");
    if (
      typeof request.script !== "string" ||
      !request.meta?.name ||
      !request.meta?.description
    )
      throw new Error(
        "Workflow requires a JavaScript script, name and description",
      );
    const id = WorkflowRunId(randomUUID());
    const abort = new AbortController();
    const turn = request.parent.session
      .snapshotEvents()
      .findLast((event) => event.type === "turn/start");
    const modelRun = this.host.nanoModels.fallback
      .list(request.parent.id)
      .findLast(
        (run) =>
          turn?.type === "turn/start" &&
          run.attempts.some((attempt) => attempt.turn === turn.data.turn),
      );
    const budgetId =
      modelRun?.id ??
      `${request.parent.id}:${turn?.type === "turn/start" ? turn.data.turn : 0}`;
    const targetMatch = /(?<!\w)\+(\d+)([km])\b/i.exec(
      this.host.nanoApproval.sources.humanText(request.parent),
    );
    const tokenTarget =
      request.outputTokenTarget ??
      (targetMatch
        ? Number(targetMatch[1]) *
          (targetMatch[2]!.toLowerCase() === "k" ? 1000 : 1000000)
        : null);
    if (
      tokenTarget !== null &&
      (!Number.isSafeInteger(tokenTarget) || tokenTarget < 0)
    )
      throw new Error("Invalid shared output-token target");
    let budget = this.budgets.get(budgetId);
    if (!budget) {
      budget = {
        id: budgetId,
        parentSessionId: request.parent.id,
        target: tokenTarget,
        sources: {
          [request.parent.id]: {
            turns: modelRun?.attempts.map((attempt) => attempt.turn) ?? [
              turn?.type === "turn/start" ? turn.data.turn : 0,
            ],
            output: 0,
          },
        },
      };
      this.budgets.set(budgetId, budget);
    } else if (
      request.outputTokenTarget !== undefined &&
      budget.target !== request.outputTokenTarget
    )
      throw new Error("Shared turn budget is already fixed");
    const record: WorkflowRecord = {
      id,
      parentSessionId: request.parent.id,
      inputIds: [
        ...new Set([
          ...(modelRun?.inputs ?? []),
          ...request.parent.session
            .snapshotEvents()
            .filter(
              (event) =>
                event.type === "user/message" &&
                event.seq > (turn?.seq ?? -1) &&
                ["nano-human", "nano-system"].includes(event.data.source.kind),
            )
            .map((event) => (event.data as { id: string }).id),
        ]),
      ],
      budgetId,
      guideline: this.host.nanoModels.ultracode(request.parent)
        ? "unrestricted"
        : (this.options.configuration(request.parent).workflow?.sizeGuideline ??
          "medium"),
      script: request.script,
      args: request.args ?? null,
      meta: structuredClone(request.meta),
      route: this.host.nanoModels.route(request.parent),
      state: "running",
      startedAt: Date.now(),
      revision: 0,
      calls: [],
      logs: [],
      ...(request.resumeFromRunId
        ? { resumedFrom: request.resumeFromRunId }
        : {}),
    };
    const previous =
      request.resumeFromRunId && this.storageRecord(request.resumeFromRunId);
    if (previous && previous.parentSessionId !== request.parent.id)
      throw new Error("Workflow does not belong to this parent Session");
    const parentConfiguration = structuredClone(
      this.options.configuration(request.parent),
    );
    const interactive =
      parentConfiguration.mode !== "global" &&
      request.parent.session
        .snapshotEvents()
        .some(
          (event) =>
            event.type === "user/message" &&
            event.seq > (turn?.seq ?? -1) &&
            event.data.source.kind === "nano-human",
        );
    const allowed = this.host.tools
      .schemas(request.parent)
      .map((tool) => tool.name)
      .filter(
        (name) => !["workflow", "subagent", "subagent_fork"].includes(name),
      );
    let eventSeq = 0;
    const control = new WorkflowControl({
      concurrency: 8,
      maxAgents: Math.min(request.maxTotalAgents ?? 1000, 1000),
      previous: previous ? previous.calls : [],
      remaining: () => this.remaining(budget!),
      persist: async (calls) => {
        record.calls = calls;
        const threshold = (
          { small: 5, medium: 15, large: 50 } as Record<string, number>
        )[record.guideline];
        if (
          threshold &&
          calls.length >= threshold &&
          !record.logs.some((log) => log.text.startsWith("Size advisory:"))
        )
          record.logs.push({
            at: Date.now(),
            text: `Size advisory: ${calls.length} calls reached the ${record.guideline} guideline; accepted work continues.`,
          });
        await this.save(record);
      },
      start: async (prompt, options, signal) => {
        const route = {
          ...record.route,
          ...Object.fromEntries(
            Object.entries(options).filter(([key]) =>
              ["provider", "model", "reasoningEffort"].includes(key),
            ),
          ),
        };
        const config = {
          ...parentConfiguration,
          ...route,
          modelRouteFrozen: true,
          toolAllowlist: allowed,
          workflowParent: {
            sessionId: request.parent.id,
            inputIds: record.inputIds,
            interactive,
          },
        };
        const child = await this.creating.run(config, () =>
          this.host.subagents.start(request.subagentProvider ?? "fork", {
            parent: request.parent,
            prompt: [{ type: "text", text: prompt }],
            label: options.label ?? prompt.slice(0, 80),
            signal,
            agentOptions: {
              ...route,
              reasoningEffort: route.reasoningEffort
                ? ReasoningEffortId(route.reasoningEffort)
                : undefined,
            },
            toolFilter: { allow: allowed },
            ...(options.schema
              ? { outputSchema: options.schema as ObjectJsonSchema }
              : {}),
          }),
        );
        const childInfo = {
          seq: ++eventSeq,
          label: options.label ?? prompt.slice(0, 80),
          phase: options.phase,
          childId: child.id,
        };
        this.emitWorkflowEvent(
          "workflow/agent-start",
          { id, meta: record.meta },
          childInfo,
        );
        budget!.sources[child.id] = { output: 0 };
        if (child.localAgent)
          this.observeBudget(budget!, child.localAgent.session);
        await this.saveBudget(budget!);
        return {
          id: child.id,
          dispose: () => child.dispose(),
          result: child.result.then(
            async (result) => {
              if (child.localAgent) {
                await this.host.sessions.flush(child.localAgent.session);
                this.observeBudget(budget!, child.localAgent.session);
                await this.saveBudget(budget!);
              }
              this.emitWorkflowEvent(
                "workflow/agent-end",
                { id, meta: record.meta },
                {
                  ...childInfo,
                  outcome: signal.aborted
                    ? "cancelled"
                    : result.stopReason === "completed"
                      ? "completed"
                      : "failed",
                },
              );
              return {
                success: result.stopReason === "completed",
                ...(result.diagnostic ? {error: result.diagnostic} : {}),
                value:
                  result.structured ??
                  result.output
                    .filter((block) => block.type === "text")
                    .map((block) => block.text)
                    .join("\n"),
              };
            },
            (error) => {
              this.emitWorkflowEvent(
                "workflow/agent-end",
                { id, meta: record.meta },
                {
                  ...childInfo,
                  outcome: signal.aborted ? "cancelled" : "failed",
                },
              );
              throw error;
            },
          ),
        };
      },
    });
    const cancel = () => {
      abort.abort();
      control.stop();
    };
    request.signal?.addEventListener("abort", cancel, { once: true });
    if (request.signal?.aborted) cancel();
    const result = this.drive(request, record, control, budget, abort)
      .catch(
        (error): WorkflowResult => ({
          value: null,
          stopReason: abort.signal.aborted ? "cancelled" : "error",
          error: String(error),
          agentsStarted: control.calls.length,
        }),
      )
      .finally(() => {
        request.signal?.removeEventListener("abort", cancel);
        this.live.delete(id);
      });
    const handle: WorkflowRun = {
      id,
      meta: record.meta,
      result,
      cancel,
      dispose: async () => {
        if (this.live.has(id)) cancel();
        await result;
        await control.drain();
      },
    };
    this.live.set(id, { handle, record, control, abort });
    return handle;
  }
  private recoveredRecords = new Map<string, WorkflowRecord>();
  private storageRecord(id: string) {
    const record = this.recoveredRecords.get(id);
    if (!record) throw new Error("Workflow recovery source is unavailable");
    return record;
  }
  private async drive(
    request: NanoWorkflowRequest,
    record: WorkflowRecord,
    control: WorkflowControl,
    budget: BudgetRecord,
    abort: AbortController,
  ): Promise<WorkflowResult> {
    let outcome: WorkflowResult;
    const programs = new Set<Promise<unknown>>();
    try {
      await this.ready;
      await this.save(record);
      await this.saveBudget(budget);
      this.emitWorkflowEvent("workflow/start", {
        id: record.id,
        meta: record.meta,
      });
      const value = await this.program(
        request.parent,
        record.script,
        record.args,
        0,
        record,
        control,
        budget,
        abort.signal,
        programs,
      );
      outcome = {
        value,
        stopReason: "completed",
        agentsStarted: control.calls.length,
      };
    } catch (error) {
      outcome = {
        value: null,
        stopReason: abort.signal.aborted ? "cancelled" : "error",
        error: String(error),
        agentsStarted: control.calls.length,
      };
    }
    // Native PTC cannot own outstanding host bindings; settle all of them here.
    abort.abort();
    control.stop();
    await control.drain();
    await Promise.allSettled(programs);
    record.state = outcome.stopReason;
    record.result = outcome;
    record.endedAt = Date.now();
    await this.spent(budget);
    await this.saveBudget(budget);
    await this.save(record);
    this.recoveredRecords.set(record.id, structuredClone(record));
    this.emitWorkflowEvent(
      "workflow/end",
      { id: record.id, meta: record.meta },
      {
        stopReason: outcome.stopReason,
        error: outcome.error,
        agentsStarted: outcome.agentsStarted,
      },
    );
    this.options.completed(structuredClone(record));
    return outcome;
  }
  private async program(
    parent: Agent,
    script: string,
    args: unknown,
    depth: number,
    record: WorkflowRecord,
    control: WorkflowControl,
    budget: BudgetRecord,
    signal: AbortSignal,
    programs: Set<Promise<unknown>>,
  ): Promise<unknown> {
    let phase: string | undefined;
    const info = { id: record.id, meta: record.meta };
    const result = await this.host.ptcRuntime.run(
      this.host.ptcRuntime.resolve({
        program: workflowProgram(script, args),
        cwd: parent.session.header.cwd,
        sandboxPolicy: this.host.sandboxPolicy.resolve({
          session: parent.session,
        }),
        timeoutMs: null,
        signal,
        bindings: [
          {
            global: "nanoWorkflow",
            errorClass: {
              name: "NanoWorkflowError",
              memberNameProperty: "operation",
            },
            functions: {
              agent: async (raw) => {
                const { prompt, options } = raw as {
                  prompt: string;
                  options: CallOptions;
                };
                if (
                  typeof prompt !== "string" ||
                  !options ||
                  Object.keys(options).some(
                    (key) =>
                      ![
                        "label",
                        "phase",
                        "provider",
                        "model",
                        "reasoningEffort",
                        "schema",
                      ].includes(key),
                  )
                )
                  throw new Error("Invalid Workflow agent prompt or option");
                return (await control.call(prompt, {
                  ...record.route,
                  ...options,
                  phase: options.phase ?? phase,
                })) as PtcJsonValue;
              },
              phase: async (raw) => {
                phase = String((raw as { title: string }).title);
                record.logs.push({ at: Date.now(), text: phase, phase });
                await this.save(record);
                this.emitWorkflowEvent("workflow/phase", info, phase);
                return null;
              },
              log: async (raw) => {
                const text = String((raw as { text: string }).text);
                record.logs.push({ at: Date.now(), text, phase });
                await this.save(record);
                this.emitWorkflowEvent("workflow/log", info, text);
                return null;
              },
              budget: async (raw) =>
                (raw as { kind: string }).kind === "spent"
                  ? this.spent(budget)
                  : this.remaining(budget),
              workflow: async (raw) => {
                if (depth >= 1)
                  throw new Error("Workflow nesting is limited to one level");
                const { reference, args } = raw as {
                  reference: string;
                  args: unknown;
                };
                const definition =
                  await this.catalog(parent).resolve(reference);
                const task = this.program(
                  parent,
                  definition.script,
                  args,
                  depth + 1,
                  record,
                  control,
                  budget,
                  signal,
                  programs,
                );
                programs.add(task);
                try {
                  return (await task) as PtcJsonValue;
                } finally {
                  programs.delete(task);
                }
              },
            },
          },
        ],
      }),
    );
    if (result.error)
      throw new Error(`${result.error.kind}: ${result.error.message}`);
    return result.value ?? null;
  }
  private readonly namespaces: { name: string; path: string }[] = [];
  registerNamespace(name: string, path: string) {
    const entry = { name, path };
    this.namespaces.push(entry);
    return () => {
      const index = this.namespaces.indexOf(entry);
      if (index >= 0) this.namespaces.splice(index, 1);
    };
  }
  catalog(parent: Agent) {
    return new WorkflowCatalog(
      parent.session.header.cwd!,
      process.env.NANO_OWNER_CONFIG_ROOT,
      this.namespaces,
    );
  }
  async control(parent: Agent, id: string, action: string, ordinal?: number) {
    const record = (await this.read(parent, id))[0]!;
    const live = this.live.get(id);
    if (!live) {
      if (action !== "resume")
        throw new Error(`Workflow is ${record.state}; no live process exists`);
      this.recoveredRecords.set(id, record);
      const run = await this.launch({
        parent,
        script: record.script,
        args: record.args,
        meta: record.meta,
        resumeFromRunId: id,
      });
      return { runId: run.id };
    }
    if (action === "pause") {
      live.control.pause();
      live.record.state = "paused";
    } else if (action === "resume") {
      live.control.resume();
      live.record.state = "running";
    } else if (action === "stop") {
      live.handle.cancel();
      await live.handle.result;
    } else if (action === "restart_child") await live.control.restart(ordinal!);
    else if (action === "stop_child") await live.control.stopChild(ordinal!);
    else throw new Error("Unknown Workflow control action");
    await this.save(live.record);
    return structuredClone(live.record);
  }
  async pending() {
    await this.ready;
    return [...(await this.storage).table("runs").entries()]
      .map(([, record]) => record)
      .filter((record) => record.result && !record.delivered)
      .map((record) => this.project(record));
  }
  async acknowledge(id: string) {
    const table = (await this.storage).table("runs");
    const record = table.get(key(id));
    if (record) await table.put(key(id), { ...record, delivered: true });
  }
  async command(parent: Agent, id: string, argument: string) {
    await this.ready;
    const table = (await this.storage).table("commands");
    const previous = table.get(key(id));
    if (previous) {
      if (previous.sessionId !== parent.id || previous.argument !== argument)
        throw new Error("Workflow command identity conflict");
      return {
        text:
          previous.text ?? "上次控制操作的结果未确认；请先查看 Workflow 状态。",
      };
    }
    await table.put(key(id), { sessionId: parent.id, argument });
    let text: string;
    try {
      const [runId, action, ordinal, name] = argument
        .split(/\s+/)
        .filter(Boolean);
      const saved =
        action === "save" ? (await this.read(parent, runId))[0] : undefined;
      const result = saved
        ? await this.catalog(parent).save(
            { ...saved.meta, name: name ?? saved.meta.name },
            saved.script,
            ordinal as "project" | "personal",
          )
        : !runId
          ? await this.read(parent)
          : !action
            ? await this.read(parent, runId)
            : await this.control(
                parent,
                runId,
                action === "restart" ? "restart_child" : action,
                ordinal ? Number(ordinal) : undefined,
              );
      text = JSON.stringify(result, null, 2);
    } catch (error) {
      text = String(error);
    }
    await table.put(key(id), { sessionId: parent.id, argument, text });
    return { text };
  }
  async stopSession(sessionId: string) {
    const active = [...this.live.values()].filter(
      (run) => run.record.parentSessionId === sessionId,
    );
    for (const run of active) run.handle.cancel();
    await Promise.all(active.map((run) => run.handle.result));
    return active.length;
  }
  async stop() {
    this.stopping = true;
    for (const run of this.live.values()) run.handle.cancel();
    await Promise.all(
      [...this.live.values()].map((run) => run.handle.dispose()),
    );
    await this.writes;
  }
}
