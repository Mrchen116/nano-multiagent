import type { Context } from '@deepseek-ai/cordis';
import {
  freezeMessage,
  isAgentLoopRequest,
  type Message,
  type StreamChunk,
  type UserMessage
} from '@deepseek-ai/dsh-llm';
import { SessionId, type Session } from '@deepseek-ai/dsh-session';
import { defineDomain, domainTable } from '@deepseek-ai/dsh-storage-domain';
import { createHash } from 'node:crypto';
import { z } from 'zod';
import { RecordWrites } from './record-writes.js';

const textPart = z.object({ type: z.literal('text'), text: z.string() });
const decision = z.object({
  sessionId: z.string(),
  inputId: z.string().optional(),
  toolCallId: z.string().optional(),
  content: z.array(textPart).optional(),
  retainImageIndices: z.array(z.number()).optional(),
  delivered: z.boolean().optional()
});
type Decision = z.infer<typeof decision>;

const domain = defineDomain({
  name: 'nano_chat_scope',
  version: 1,
  layout: 'per-record',
  tables: { decisions: domainTable(decision) }
});
const key = (row: Decision) => JSON.stringify([row.sessionId, row.inputId, row.toolCallId]);
const storageKey = (id: string) => createHash('sha256').update(id).digest('hex');
const rebuild = 'NANO_CHAT_SCOPE_CHANGED';
function identity(sessionId: string, message: Message): Decision | undefined {
  if (message.role === 'user') return { sessionId, inputId: message.id };
  if (message.role === 'tool') return { sessionId, toolCallId: message.toolCallId };
}
function replacement(row: Decision) {
  const content: NonNullable<Decision['content']> = row.content ?? [
    { type: 'text', text: row.toolCallId ? '{"messages":[]}' : 'Team chat input withdrawn.' }
  ];
  return content;
}
function accepted(chunk: StreamChunk): boolean {
  return (
    ((chunk.type === 'text-delta' || chunk.type === 'reasoning-delta') && !!chunk.text) ||
    (chunk.type === 'tool-call-delta' && !!chunk.argumentsDelta) ||
    (chunk.type === 'block-end' &&
      (chunk.block.type === 'tool-call'
        ? !!chunk.block.name
        : (chunk.block.type === 'text' || chunk.block.type === 'reasoning') && !!chunk.block.text))
  );
}

/** Order scope changes with the first provider handoff and project undelivered history on replay. */
export class ChatScope {
  private readonly rows = new Map<string, Decision>();
  private readonly storage;
  private readonly ready;
  private readonly writes;
  private readonly dispatches = new Map<string, Set<Promise<void>>>();
  private readonly preparations = new Map<
    string,
    { operationId: string; done: Promise<void>; release: () => void }
  >();
  private readonly holds = new Map<string, Promise<unknown>>();

  constructor(
    private readonly ctx: Context,
    private readonly owner: (sessionId: string) => string | undefined
  ) {
    this.storage = ctx.storageDomain.open(domain);
    this.ready = this.storage.then((db) => {
      for (const [, row] of db.table('decisions').entries()) this.rows.set(key(row), row);
    });
    this.writes = new RecordWrites<Decision>(async (id, row) => {
      await (await this.storage).table('decisions').put(storageKey(id), row);
    });
    ctx.on(
      'agent/pre-step',
      async ({ agent, step }, next) => {
        const result = await next();
        if (result.kind === 'reject') return result;
        await this.ready;
        const messages = result.messages.flatMap((m) => this.queued(agent.id, m));
        return result.messages.length && !messages.length && step === 0
          ? { kind: 'reject' }
          : { ...result, messages };
      },
      { prepend: true }
    );
    const scope = this;
    ctx.on(
      'llm/stream',
      async function* (options, next) {
        const sessionId = isAgentLoopRequest(options) ? options.sessionId : undefined;
        const agentId = sessionId && scope.owner(sessionId);
        if (!sessionId || !agentId) {
          yield* next();
          return;
        }
        await scope.ready;
        while (scope.preparations.has(agentId) || scope.holds.has(agentId))
          await (scope.preparations.get(agentId)?.done ?? scope.holds.get(agentId));
        const session = ctx.sessions.get(SessionId(sessionId));
        const changes = options.messages.filter((m) => m.id && scope.stale(sessionId, m));
        if (changes.length && session) {
          scope.project(session);
          await ctx.sessions.flush(session);
          const current = session.snapshotEvents();
          const start = current.findLast((e) => e.type === 'turn/start')?.seq ?? -1;
          const user = current.filter((e) => e.seq > start && e.type === 'user/message');
          const onlyWithdrawn =
            user.length > 0 &&
            user.every((e) => e.type === 'user/message' && scope.removed(sessionId, e.data)) &&
            !current.some((e) => e.seq > start && e.type === 'tool/result');
          yield {
            type: 'finish',
            reason: onlyWithdrawn
              ? { kind: 'stop' }
              : {
                  kind: 'error',
                  failure: { code: rebuild, message: 'Refresh chat scope before provider dispatch' }
                }
          };
          return;
        }
        const inboxCalls = new Set(
          options.messages.flatMap((m) =>
            m.role === 'assistant'
              ? m.content.flatMap((b) => (b.type === 'tool-call' && b.name === 'inbox' ? [String(b.id)] : []))
              : []
          )
        );
        const fresh = options.messages.flatMap((m) => {
          if (!m.id) return [];
          const id = identity(sessionId, m);
          if (!id || scope.rows.get(key(id))?.delivered || scope.removed(sessionId, m)) return [];
          if (
            (m.role === 'tool' && inboxCalls.has(m.toolCallId)) ||
            (m.role === 'user' &&
              (('nanoTeamChat' in m.source && m.source.nanoTeamChat === true) ||
                (m.source.kind === 'nano-system' &&
                  ['inbox', 'inbox-background'].includes(m.source.channel))))
          )
            return [id];
          return [];
        });
        if (!fresh.length) {
          yield* next();
          return;
        }
        let confirm!: () => void;
        const handoff = new Promise<void>((resolve) => {
          confirm = resolve;
        });
        const active = scope.dispatches.get(agentId) ?? new Set();
        active.add(handoff);
        scope.dispatches.set(agentId, active);
        let seen = false;
        try {
          for await (const chunk of next()) {
            if (!seen && accepted(chunk) && !options.signal?.aborted) {
              seen = true;
              await Promise.all(fresh.map((row) => scope.save({ ...row, delivered: true })));
              confirm();
            }
            yield chunk;
          }
        } finally {
          confirm();
          active.delete(handoff);
          if (!active.size) scope.dispatches.delete(agentId);
        }
      },
      { prepend: true }
    );
    ctx.on(
      'agent/request-error',
      async ({ failure }, next) => (failure.code === rebuild ? { kind: 'retry' } : next()),
      { prepend: true }
    );
    ctx.effect(() => async () => {
      await this.writes.flush();
      await (await this.storage).close();
    });
  }
  private save(row: Decision) {
    const id = key(row);
    this.rows.set(id, row);
    return this.writes.put(id, row);
  }
  private row(sessionId: string, message: Message) {
    const id = identity(sessionId, message);
    const row = id && this.rows.get(key(id));
    return row?.delivered ? undefined : row;
  }
  private removed(sessionId: string, message: Message) {
    const row = this.row(sessionId, message);
    return !!row && !row.content;
  }
  private stale(sessionId: string, message: Message) {
    const row = this.row(sessionId, message);
    if (!row) return false;
    const images = message.content.filter((block) => block.type === 'image');
    return (
      images.length !== (row.retainImageIndices?.length ?? 0) ||
      JSON.stringify(message.content.filter((block) => block.type !== 'image')) !==
        JSON.stringify(replacement(row))
    );
  }
  queued(sessionId: string, message: UserMessage): UserMessage[] {
    const row = this.row(sessionId, message);
    if (!row) return [message];
    return row.content ? [freezeMessage({ ...message, content: row.content })] : [];
  }
  private project(session: Session) {
    for (const seq of session.surface.nodes.slice()) {
      const event = session.eventAt(seq);
      if (!event || (event.type !== 'user/message' && event.type !== 'tool/result')) continue;
      const message = event.type === 'user/message' ? event.data : event.data.message;
      if (!this.stale(session.id, message)) continue;
      const row = this.row(session.id, message)!;
      const content = replacement(row);
      const placement = {
        surfaceOp: { op: 'replace' as const, startSeq: seq, endSeq: seq },
        sourceEventSeqs: [seq]
      };
      if (event.type === 'user/message') {
        const source = row.content
          ? event.data.source
          : {
              kind: 'nano-system' as const,
              channel: 'withdrawn-chat',
              actorId: this.owner(session.id) ?? '',
              messageId: event.data.id
            };
        session.append('user/message', { ...event.data, source, content }, placement);
      } else {
        const images = event.data.message.content.filter((block) => block.type === 'image');
        const keep = (row.retainImageIndices ?? []).flatMap((index) => images[index] ?? []);
        session.append(
          'tool/result',
          { ...event.data, message: { ...event.data.message, content: [...content, ...keep] } },
          placement
        );
      }
    }
  }
  async delivered(sessionId: string, inputId: string) {
    await this.ready;
    return this.rows.get(key({ sessionId, inputId }))?.delivered === true;
  }
  reserve(agentId: string, operationId: string) {
    if (this.preparations.has(agentId)) return;
    let release!: () => void;
    const done = new Promise<void>((resolve) => {
      release = resolve;
    });
    this.preparations.set(agentId, { operationId, done, release });
  }
  release(agentId: string, operationId: string) {
    const hold = this.preparations.get(agentId);
    if (hold?.operationId !== operationId) return;
    this.preparations.delete(agentId);
    hold.release();
  }
  async restrict(agentId: string, changes: Decision[]) {
    const prior = this.holds.get(agentId);
    const operation = (async () => {
      await prior;
      await this.ready;
      await Promise.all(this.dispatches.get(agentId) ?? []);
      const withdrawn = changes.filter((row) => !this.rows.get(key(row))?.delivered);
      await Promise.all(withdrawn.map((row) => this.save(row)));
      for (const sessionId of new Set(withdrawn.map((row) => row.sessionId))) {
        const agent = this.ctx.agents.get(SessionId(sessionId));
        if (agent)
          for (const m of [...agent.inbox.nextStep, ...agent.inbox.nextTurn]) {
            const [allowed] = this.queued(sessionId, m);
            if (!allowed) agent.inbox.remove(m.id);
            else if (allowed !== m) agent.inbox.replace(m.id, allowed);
          }
        const session = this.ctx.sessions.get(SessionId(sessionId));
        if (session) {
          this.project(session);
          await this.ctx.sessions.flush(session);
        }
      }
      return { withdrawn };
    })();
    this.holds.set(agentId, operation);
    try {
      return await operation;
    } finally {
      if (this.holds.get(agentId) === operation) this.holds.delete(agentId);
    }
  }
  async forget(sessionIds: ReadonlySet<string>) {
    await this.ready;
    await this.writes.forget((_, row) => sessionIds.has(row.sessionId));
    const table = (await this.storage).table('decisions');
    for (const [id, row] of this.rows)
      if (sessionIds.has(row.sessionId)) {
        await table.delete(storageKey(id));
        this.rows.delete(id);
      }
  }
}
