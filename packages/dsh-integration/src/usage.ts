import { randomUUID } from 'node:crypto';
import type { Context } from '@deepseek-ai/cordis';
import { SessionId, type Session, type SessionEvent } from '@deepseek-ai/dsh-session';
import type {} from '@deepseek-ai/dsh-subagent';
import { deriveTurnTokenUsage } from '@deepseek-ai/dsh-token-meter/client';
import type { UsageReadResult, UsageReport } from '@nano/product-contracts';

interface SessionUsage {
  initialized: boolean;
  through: number;
  pending: SessionEvent[];
  turn: SessionEvent[];
}
interface RootUsage {
  id: string;
  epoch: string;
  initialized: boolean;
  sessions: Map<string, SessionUsage>;
  dirty: Set<string>;
  reports: UsageReport[];
  tail: Promise<unknown>;
}

/** Runtime-local projection; native logs and the PA outbox remain the durable owners. */
class UsageReader {
  private readonly roots = new Map<string, RootUsage>();
  readonly owners = new Map<string, RootUsage>();

  constructor(private readonly ctx: Context) {
    ctx.on('session/event', (session, event) => {
      if (!session.isOwnSeq(event.seq)) return;
      let ancestor: Session | undefined = session;
      let root: RootUsage | undefined;
      while (ancestor) {
        root = this.owners.get(ancestor.id);
        if (root || !ancestor.header.parentSession) break;
        ancestor = ctx.sessions.get(ancestor.header.parentSession);
      }
      if (!root) return; // Work preceding the first recovery is covered by its cold scan.
      const state = this.session(root, session.id);
      if (event.seq <= state.through) return;
      state.pending.push(event);
      root.dirty.add(session.id);
      this.discover(root, event);
    });
  }

  read(rootId: string, cursor?: string): Promise<UsageReadResult> {
    let root = this.roots.get(rootId);
    if (!root) {
      root = {id: rootId, epoch: randomUUID(), initialized: false, sessions: new Map(),
        dirty: new Set(), reports: [], tail: Promise.resolve()};
      this.roots.set(rootId, root);
      this.session(root, rootId);
    }
    const target = root;
    const result = target.tail.then(() => this.drain(target, cursor));
    target.tail = result.catch(() => {});
    return result;
  }

  private session(root: RootUsage, id: string): SessionUsage {
    let state = root.sessions.get(id);
    if (!state) {
      state = {initialized: false, through: -1, pending: [], turn: []};
      root.sessions.set(id, state);
      root.dirty.add(id);
      this.owners.set(id, root);
    }
    return state;
  }

  private discover(root: RootUsage, event: SessionEvent) {
    if (event.type === 'subagent/catalog' && event.data.mode !== 'unknown')
      this.session(root, event.data.childId);
  }

  private async drain(root: RootUsage, cursor?: string): Promise<UsageReadResult> {
    if (!root.initialized) {
      try {
        const children = await this.ctx.subagents.listDescendants(SessionId(root.id));
        for (const child of children) if (child.kind === 'child') this.session(root, child.id);
        // Unavailable branches are not a complete recovery. Retry discovery until
        // storage is readable, while retaining already rebuilt accounting.
        root.initialized = !children.some(child => child.kind === 'diagnostic' && child.reason !== 'unsupported');
      } catch (error) {
        if ((error as {code?: string}).code === 'SESSION_QUERY_SESSION_NOT_FOUND')
          return {reports: [], cursor: ''}; // A binding can precede its first persisted session.
        throw error;
      }
    }
    // Visit each changed session at most once per read. New children are added to this
    // Set during replay; additional events for a visited session wait for the next read.
    const visited = new Set<string>();
    for (const id of root.dirty) {
      if (visited.has(id)) continue;
      visited.add(id);
      root.dirty.delete(id);
      const state = root.sessions.get(id)!;
      try { await this.update(root, id, state); }
      catch (error) { root.dirty.add(id); throw error; }
    }
    const [epoch, position] = cursor?.split(':') ?? [];
    const offset = Number(position);
    const start = epoch === root.epoch && Number.isSafeInteger(offset) && offset >= 0 && offset <= root.reports.length ? offset : 0;
    return {reports: root.reports.slice(start), cursor: `${root.epoch}:${root.reports.length}`};
  }

  private async update(root: RootUsage, id: string, state: SessionUsage) {
    const live = this.ctx.sessions.get(SessionId(id));
    const cut = live?.seq;
    let durableLive = false;
    if (live) {
      try {
        if (!await this.ctx.sessions.flush(live)) throw new Error('Usage read has no persistence barrier');
        durableLive = true;
      } catch (error) {
        if (this.ctx.sessions.get(SessionId(id)) === live) throw error;
        // Natural child teardown may race this read. Only its persisted observation
        // can certify the queued events once it is no longer attached.
      }
    }
    if (state.initialized && durableLive) {
      const events = state.pending.filter(event => event.seq < cut!);
      this.consume(root, id, state, events);
    } else {
      using observation = await this.ctx.sessionQuery.observeSession(SessionId(id), {projectionMode: 'none'});
      // A prepared read can become live while resolving storage. Retry with its own
      // flush cut instead of treating that live observation as durable.
      if (observation.source === 'live' && !durableLive) {
        return this.update(root, id, state);
      }
      const through = durableLive ? Math.min(cut! - 1, observation.cursor) : observation.cursor;
      if (!durableLive && state.pending.some(event => event.seq > through))
        throw new Error('Usage events are not yet persisted');
      const events = observation.events.slice(Math.max(observation.inheritedEventCount, state.through + 1), through + 1);
      this.consume(root, id, state, events);
      state.through = through;
      state.initialized = true;
    }
    state.pending = state.pending.filter(event => event.seq > state.through);
    if (state.pending.length) root.dirty.add(id);
  }

  private consume(root: RootUsage, id: string, state: SessionUsage, events: readonly SessionEvent[]) {
    for (const event of events) {
      if (event.seq <= state.through) continue;
      this.discover(root, event);
      if (event.type === 'turn/start') state.turn = [];
      if (event.type === 'turn/start' || state.turn.length) state.turn.push(event);
      if (event.type === 'turn/end' && state.turn.length) {
        const usage = deriveTurnTokenUsage(state.turn);
        if (usage) root.reports.push({sessionId: id, turn: event.data.turn, time: event.time,
          usage: {prompt_tokens: usage.totalTokens - usage.outputTokens, completion_tokens: usage.outputTokens, total_tokens: usage.totalTokens}});
        state.turn = [];
      }
      state.through = event.seq;
    }
  }
}

const readers = new WeakMap<Context, UsageReader>();

/** Read durable completed-turn facts after an optional runtime-local cursor.
 *
 * Args:
 *   ctx: Runtime context owning the native event stream and persistence services.
 *   rootId: Trusted product binding whose descendants are included.
 *   cursor: Last page saved by the caller; absent or stale cursors replay all facts.
 * Returns:
 *   Incremental reports and a cursor that is safe to retain after saving them.
 */
export function readUsage(ctx: Context, rootId: string, cursor?: string): Promise<UsageReadResult> {
  let reader = readers.get(ctx);
  if (!reader) { reader = new UsageReader(ctx); readers.set(ctx, reader); }
  return reader.read(rootId, cursor);
}

/** Resolve an already discovered child's binding when its live ancestors unloaded.
 *
 * Args:
 *   ctx: The runtime context used for usage reads.
 *   sessionId: Session publishing a new event.
 * Returns:
 *   The known root binding, or undefined before discovery.
 */
export function usageRoot(ctx: Context, sessionId: string): string | undefined {
  return readers.get(ctx)?.owners.get(sessionId)?.id;
}
