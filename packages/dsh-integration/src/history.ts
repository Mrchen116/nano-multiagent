import { AsyncLocalStorage } from "node:async_hooks";
import { access, mkdir, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { Context } from "@deepseek-ai/cordis";
import type { Agent } from "@deepseek-ai/dsh-agent";
import type { SessionController } from "@deepseek-ai/dsh-api-session-controller";
import { SessionId, type Session } from "@deepseek-ai/dsh-session";
import {
  defineDomain,
  domainTable,
  type Domain,
  type DomainSpec,
  type DomainTableSpec,
} from "@deepseek-ai/dsh-storage-domain";
import { z } from "zod";
import type { AgentConfiguration } from "./index.js";
import type { ModelRoute } from "./model-policy.js";

interface Snapshot {
  sessionId: string;
  turn: number;
  config: AgentConfiguration;
}
interface Override {
  config: AgentConfiguration;
  baseRevision: string;
}
interface Fork {
  source: string;
  messageId: string;
  status: "pending" | "ready";
  sessionId?: string;
  idMap: Record<string, string>;
  override: Override;
}
interface HistoryDomain extends DomainSpec {
  tables: {
    snapshots: DomainTableSpec<string, Snapshot>;
    overrides: DomainTableSpec<string, Override>;
    forks: DomainTableSpec<string, Fork>;
  };
}
const configSchema = z.custom<AgentConfiguration>();
const overrideSchema = z.object({
  config: configSchema,
  baseRevision: z.string(),
});
const domain: HistoryDomain = defineDomain({
  name: "nano_history",
  version: 1,
  layout: "per-record",
  tables: {
    snapshots: domainTable(
      z.object({
        sessionId: z.string(),
        turn: z.number(),
        config: configSchema,
      }),
    ),
    overrides: domainTable(overrideSchema),
    forks: domainTable(
      z.object({
        source: z.string(),
        messageId: z.string(),
        status: z.enum(["pending", "ready"]),
        sessionId: z.string().optional(),
        idMap: z.record(z.string(), z.string()),
        override: overrideSchema,
      }),
    ),
  },
});
const key = (value: string) => Buffer.from(value).toString("base64url");
const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value));

/** Stores Nano configuration facts; native DSH owns the prefix and fork lifecycle. */
export class NativeHistory {
  private readonly state: Promise<Domain<HistoryDomain>>;
  private readonly creating = new AsyncLocalStorage<{
    id: string;
    fork: Fork;
  }>();
  private readonly operations = new Map<
    string,
    Promise<{ sessionId: string; idMap: Record<string, string> }>
  >();
  private readonly exports = new Map<string, Promise<void>>();
  private writes: Promise<void> = Promise.resolve();
  constructor(
    private readonly ctx: Context,
    private readonly home: string,
  ) {
    this.state = ctx.storageDomain.open(domain);
    ctx.on("session/event", (session, event) => {
      if (
        event.type === "turn/end" &&
        session.header.agentPreset?.startsWith("nano:")
      )
        this.queueExport(session);
    });
    ctx.effect(() => async () => {
      await this.stop();
      await (await this.state).close();
    });
  }
  async configuration(
    agent: Agent,
    desired: AgentConfiguration,
    parent?: AgentConfiguration,
  ): Promise<AgentConfiguration> {
    const state = await this.state;
    const creating = this.creating.getStore();
    if (
      creating &&
      agent.session.header.parentSession === creating.fork.source &&
      agent.session.header.origin !== "subagent"
    ) {
      creating.fork.sessionId = agent.id;
      await state.table("forks").put(key(creating.id), creating.fork);
      await state.table("overrides").put(key(agent.id), creating.fork.override);
      return copy(creating.fork.override.config);
    }
    const saved = state.table("overrides").get(key(agent.id));
    if (saved?.baseRevision === desired.revision) return copy(saved.config);
    if (agent.session.header.origin === "subagent" && parent) {
      await state
        .table("overrides")
        .put(key(agent.id), {
          config: copy(parent),
          baseRevision: desired.revision,
        });
      return copy(parent);
    }
    return copy(desired);
  }
  attach(agent: Agent, config: AgentConfiguration, route: () => ModelRoute) {
    agent.ctx.on(
      "agent/pre-step",
      async (_payload, next) => {
        const decision = await next();
        if (decision.kind === "reject") return decision;
        const start = agent.session
          .snapshotEvents()
          .findLast((event) => event.type === "turn/start");
        if (start?.type === "turn/start") {
          const snapshot: Snapshot = {
            sessionId: agent.id,
            turn: start.data.turn,
            config: copy({ ...config, ...route() }),
          };
          this.writes = this.writes.then(async () => {
            const table = (await this.state).table("snapshots");
            const id = key(`${agent.id}:${snapshot.turn}`);
            if (!table.get(id)) await table.put(id, snapshot);
          });
          await this.writes;
        }
        return decision;
      },
      { prepend: true },
    );
  }
  fork(
    agent: Agent,
    messageId: string,
    operationId: string,
    desired: AgentConfiguration,
    controller: SessionController,
  ) {
    const active = this.operations.get(operationId);
    if (active) return active;
    const task = this.performFork(
      agent,
      messageId,
      operationId,
      desired,
      controller,
    ).finally(() => this.operations.delete(operationId));
    this.operations.set(operationId, task);
    return task;
  }
  private async performFork(
    agent: Agent,
    messageId: string,
    operationId: string,
    desired: AgentConfiguration,
    controller: SessionController,
  ) {
    await this.writes;
    if (!(await this.ctx.sessions.flush(agent.session)))
      throw new Error("Fork source has no persistence barrier");
    const state = await this.state;
    const forks = state.table("forks");
    const id = key(operationId);
    let record = forks.get(id);
    if (
      record &&
      (record.source !== agent.id || record.messageId !== messageId)
    )
      throw new Error("Fork operation identity conflict");
    if (record?.status === "ready")
      return { sessionId: record.sessionId!, idMap: record.idMap };
    if (record)
      throw new Error(
        "Interrupted fork is not ready; its source remains available",
      );
    const events = agent.session.snapshotEvents();
    const point = events.find(
      (event) =>
        event.type === "assistant/message" &&
        event.data.message.id === messageId,
    );
    if (!point)
      throw new Error(
        "Fork point is not an available native assistant message",
      );
    const prefix = events.filter((event) => event.seq <= point.seq);
    const turn = prefix.findLast((event) => event.type === "turn/start");
    if (turn?.type !== "turn/start")
      throw new Error("Fork point has no native turn");
    const snapshot = state
      .table("snapshots")
      .get(key(`${agent.id}:${turn.data.turn}`));
    if (!snapshot)
      throw new Error("Fork point has no saved configuration snapshot");
    const idMap = Object.fromEntries(
      prefix.flatMap((event) =>
        event.type === "user/message"
          ? [[event.data.id, event.data.id]]
          : event.type === "assistant/message"
            ? [[event.data.message.id, event.data.message.id]]
            : [],
      ),
    );
    record = {
      source: agent.id,
      messageId,
      status: "pending",
      idMap,
      override: { config: snapshot.config, baseRevision: desired.revision },
    };
    await forks.put(id, record);
    const result = await this.creating.run(
      { id: operationId, fork: record },
      () => controller.fork({ sessionId: agent.id, atSeq: point.seq }),
    );
    const session = this.ctx.sessions.get(result.sessionId)!;
    if (!(await this.ctx.sessions.flush(session)))
      throw new Error("Fork has no persistence barrier");
    for (const [, original] of state.table("snapshots").entries())
      if (original.sessionId === agent.id && original.turn <= turn.data.turn) {
        await state
          .table("snapshots")
          .put(key(`${result.sessionId}:${original.turn}`), {
            ...original,
            sessionId: result.sessionId,
          });
      }
    await forks.put(id, {
      ...record,
      sessionId: result.sessionId,
      status: "ready",
    });
    await this.queueExport(session);
    return { sessionId: result.sessionId, idMap };
  }
  private async writeExport(
    header: Session["header"],
    events: ReturnType<Session["snapshotEvents"]>,
  ) {
    const directory = join(this.home, "exports");
    await mkdir(directory, { recursive: true });
    const path = join(directory, `${key(header.id)}.jsonl`);
    const body =
      [{ type: "nano-dsh-history", version: 1, header }, ...events]
        .map((value) => JSON.stringify(value))
        .join("\n") + "\n";
    await writeFile(`${path}.tmp`, body);
    await rename(`${path}.tmp`, path);
    if (header.cwd) {
      const readable = join(header.cwd, ".nanoassistant", "chat_history");
      await mkdir(readable, { recursive: true });
      const target = join(readable, `${encodeURIComponent(header.id)}.jsonl`);
      const messages = events.flatMap((event) => {
        const message =
          event.type === "user/message"
            ? event.data
            : event.type === "assistant/message"
              ? event.data.message
              : undefined;
        if (!message) return [];
        const content = message.content
          .flatMap((block) =>
            block.type === "text"
              ? [block.text]
              : block.type === "image"
                ? ["[image]"]
                : [],
          )
          .join("\n");
        return content
          ? [
              {
                ts: new Date(event.time).toISOString(),
                role: message.role,
                content,
                source: message.source.kind,
              },
            ]
          : [];
      });
      await writeFile(
        `${target}.tmp`,
        messages.map((message) => JSON.stringify(message)).join("\n") + "\n",
      );
      await rename(`${target}.tmp`, target);
    }
  }
  private queueExport(session: Session) {
    const previous = this.exports.get(session.id) ?? Promise.resolve();
    const task = previous
      .catch(() => {})
      .then(async () => {
        if (!(await this.ctx.sessions.flush(session)))
          throw new Error("History export has no persistence barrier");
        await this.writeExport(session.header, session.snapshotEvents());
      });
    this.exports.set(session.id, task);
    void task.catch((error) =>
      this.ctx.logger("nano-history").warn(String(error)),
    );
    return task;
  }
  async recoverExports(sessionIds: string[]) {
    for (const id of sessionIds) {
      try {
        using observation = await this.ctx.sessionQuery.observeSession(
          SessionId(id),
        );
        await this.writeExport(observation.header, observation.events);
      } catch (error) {
        // New product bindings may precede their first persisted native Session.
        if (
          (error as { code?: string }).code !==
          "SESSION_QUERY_SESSION_NOT_FOUND"
        )
          throw error;
      }
    }
  }
  /** Only checks a separately produced export; prompt generation never reads transcripts. */
  async path(sessionId: string) {
    await this.exports.get(sessionId);
    const path = join(this.home, "exports", `${key(sessionId)}.jsonl`);
    await access(path);
    return path;
  }
  async stop() {
    await this.writes;
    await Promise.allSettled(this.exports.values());
  }
}
