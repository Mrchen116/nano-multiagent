/** Read descendant changes without retaining or replaying unchanged cold histories. */
import type { Context } from '@deepseek-ai/cordis';
import type { SessionId, SessionEvent } from '@deepseek-ai/dsh-session';
import type { SessionPersistenceRevision } from '@deepseek-ai/dsh-session-persistence';
import { SubagentError, type SubagentCatalogEntry, type SubagentDescendantListEntry } from '@deepseek-ai/dsh-subagent';
import type {} from '@deepseek-ai/dsh-session-query';
import { RpcError } from './rpc.js';

interface Catalog {
  identity?: symbol;
  revision?: SessionPersistenceRevision;
  cursor: number;
  children: SubagentCatalogEntry[];
}
type Descendant = SubagentDescendantListEntry & { events?: SessionEvent[]; throughSeq?: number };

/** Keep only catalog metadata; native observations continue to own all history. */
export class DescendantReader {
  private readonly catalogs = new Map<SessionId, Catalog>();

  constructor(private readonly ctx: Context) {}

  /** Read reachable descendants in native catalog order.
   *
   * Args:
   *   rootId: Trusted root already resolved by the runtime's binding checks.
   *   cursors: Consumer-confirmed native event positions, absent for full replay.
   *   refresh: Synchronous projection-version check, called after acquiring an
   *     observation cut (and on cold metadata hits). May run twice for a child.
   * Returns:
   *   Children with complete own events when changed, otherwise an empty array;
   *   unavailable branches retain the native diagnostic vocabulary.
   * Raises:
   *   Error: Root/catalog service failures or a live persistence barrier failure.
   */
  async read(rootId: SessionId, cursors: Record<string, number> = {}, refresh: (id: SessionId) => boolean = () => false): Promise<Descendant[]> {
    const root = await this.observe(rootId);
    const stack = root.catalog.children.map(entry => ({ entry, parentId: rootId, depth: 1 })).reverse();
    const visited = new Set([rootId]);
    const result: Descendant[] = [];
    for (let position = stack.pop(); position; position = stack.pop()) {
      const { entry, parentId, depth } = position;
      if (visited.has(entry.id)) continue;
      visited.add(entry.id);
      let read;
      try { read = await this.observe(entry.id, cursors[entry.id], refresh); }
      catch (error) {
        if (error instanceof SubagentError || error instanceof RpcError) throw error;
        const code = (error as { code?: string })?.code;
        result.push({ kind: 'diagnostic', id: entry.id, parentId, depth,
          reason: code === 'SESSION_QUERY_CORRUPT_SESSION' || code === 'SESSION_QUERY_SOURCE_CONFLICT' ? 'corrupt' : 'unavailable' });
        continue;
      }
      if (entry.mode === 'unknown') result.push({ kind: 'diagnostic', id: entry.id, parentId, depth, reason: 'unsupported' });
      else {
        const { createdAt: _, ...identity } = entry;
        result.push({ ...identity, kind: 'child', parentId, depth,
          activity: this.ctx.sessions.get(entry.id) ? 'running' : 'inactive',
          hasChildren: read.catalog.children.length > 0, throughSeq: read.catalog.cursor, events: read.events });
      }
      for (const child of [...read.catalog.children].reverse()) stack.push({ entry: child, parentId: entry.id, depth: depth + 1 });
    }
    return result;
  }

  private async observe(id: SessionId, cursor?: number, refresh?: (id: SessionId) => boolean): Promise<{ catalog: Catalog; events: SessionEvent[] }> {
    const live = this.ctx.sessions.get(id);
    if (live && !await this.ctx.sessions.flush(live)) throw new RpcError(-32005, 'Child Session has no persistence barrier');
    const persistence = this.ctx.sessionPersistence;
    const cached = this.catalogs.get(id);
    if (!live && cached?.identity === persistence.identity && cached.revision !== undefined) {
      const snapshot = await persistence.stat(id);
      // A session may have become live during stat; never hide its unflushed tail.
      if (!this.ctx.sessions.get(id) && snapshot?.revision === cached.revision && cursor === cached.cursor && !refresh?.(id)) {
        return { catalog: cached, events: [] };
      }
    }
    using observation = await this.ctx.sessionQuery.observeSession(id);
    // Model state can advance while observe awaits I/O. Capture it only at this
    // cut, without another await before materializing the matching event prefix.
    const replay = refresh?.(id) ?? false;
    const children = observation.projections?.values.subagentCatalog;
    if (!children) throw new SubagentError('Descendant reads require the subagentCatalog projection', 'SUBAGENT_CONTROL_PROJECTIONS_UNAVAILABLE');
    const events = refresh && (replay || cursor !== observation.cursor)
      ? observation.events.slice(observation.inheritedEventCount) : [];
    const catalog: Catalog = { identity: persistence.identity, revision: observation.revision, cursor: observation.cursor, children };
    this.catalogs.set(id, catalog);
    return { catalog, events };
  }
}
