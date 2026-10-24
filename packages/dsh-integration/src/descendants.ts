/** Keep Work lineage and durable cuts without retaining native history bodies. */
import type { Context } from '@deepseek-ai/cordis';
import { SessionId, type Session, type SessionEvent } from '@deepseek-ai/dsh-session';
import type { SessionPersistenceRevision, SessionPersistenceSnapshot } from '@deepseek-ai/dsh-session-persistence';
import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { SubagentError, type SubagentCatalogEntry, type SubagentDescendantListEntry } from '@deepseek-ai/dsh-subagent';
import type {} from '@deepseek-ai/dsh-session-query';
import { z } from 'zod';
import { RpcError } from './rpc.js';

interface Witness { header: string; eventCount?: number; sizeBytes?: number }
interface Catalog {
  rootId: string;
  cursor: number;
  children: SubagentCatalogEntry[];
  active: boolean;
  witness?: Witness;
}
interface CatalogDomain extends DomainSpec { tables: { sessions: DomainTableSpec<string, Catalog> } }
const domain: CatalogDomain = defineDomain({name:'nano_work_catalog',version:1,layout:'per-record',tables:{
  sessions:domainTable(z.object({rootId:z.string(),cursor:z.number(),children:z.array(z.custom<SubagentCatalogEntry>()),active:z.boolean(),
    witness:z.object({header:z.string(),eventCount:z.number().optional(),sizeBytes:z.number().optional()}).optional()})),
}});
type Descendant = SubagentDescendantListEntry & { events?: SessionEvent[]; throughSeq?: number };
const key = (id: string) => Buffer.from(id).toString('base64url');
const witness = (snapshot?: SessionPersistenceSnapshot): Witness | undefined => snapshot?.header &&
  (snapshot.eventCount !== undefined || snapshot.sizeBytes !== undefined)
  ? {header:JSON.stringify(snapshot.header),eventCount:snapshot.eventCount,sizeBytes:snapshot.sizeBytes} : undefined;
const sameWitness = (prior: Witness | undefined, snapshot?: SessionPersistenceSnapshot): boolean => {
  const next = witness(snapshot);
  if (!prior || !next || prior.header !== next.header) return false;
  // Both observations describe the same immutable, append-only artifact. Unlike
  // revision, its public byte/event count remains meaningful after restart.
  return prior.eventCount !== undefined && next.eventCount !== undefined ? prior.eventCount === next.eventCount
    : prior.sizeBytes !== undefined && next.sizeBytes !== undefined && prior.sizeBytes === next.sizeBytes;
};

/** Persist only metadata; native observations remain the sole body owner. */
export class DescendantReader {
  private readonly catalogs = new Map<SessionId, Catalog>();
  private readonly revisions = new Map<SessionId, {identity:symbol;revision:SessionPersistenceRevision}>();
  private readonly owners = new Map<string, string>();
  private readonly storage;
  readonly ready: Promise<void>;

  constructor(private readonly ctx: Context) {
    this.storage = ctx.storageDomain.open(domain);
    this.ready = this.storage.then(storage => {
      for (const [encoded, catalog] of storage.table('sessions').entries()) {
        const id = SessionId(Buffer.from(encoded,'base64url').toString());
        this.catalogs.set(id,catalog); this.owners.set(id,catalog.rootId);
      }
    });
    ctx.effect(() => async () => { await this.ready; await (await this.storage).close(); });
  }

  /** Resolve known lineage after live ancestors unload. */
  rootOf(id: string): string | undefined { return this.owners.get(id); }

  /** Remember live ownership without consuming inherited catalog events. */
  remember(session: Session, event: SessionEvent, rootId: string): void {
    this.owners.set(session.id,rootId);
    if (session.isOwnSeq(event.seq) && event.type === 'subagent/catalog' && event.data.mode !== 'unknown')
      this.owners.set(event.data.childId,rootId);
  }

  /** Check saved cuts without hydrating Agents or opening history bodies.
   *
   * Args:
   *   rootId: Trusted root binding.
   *   cursors: Product projection positions, independent of transport ACKs.
   *   refresh: Whether model projection metadata changed at the checked cut.
   * Returns:
   *   True only when every reachable supported execution is settled and covered.
   */
  async settled(rootId: SessionId, cursors: Record<string, number>, refresh: (id: SessionId) => boolean, includeChildren = true): Promise<boolean> {
    await this.ready;
    const stack=[rootId],visited=new Set<string>();
    for (let id=stack.pop();id;id=stack.pop()) {
      if(visited.has(id))continue;visited.add(id);
      const cached=this.catalogs.get(id);
      if(!cached || cached.rootId!==rootId || cached.active || (cursors[id]??-1)<cached.cursor ||
        !await this.unchanged(id,cached) || refresh(id))return false;
      this.owners.set(id,rootId);
      if(includeChildren)for(const entry of cached.children)if(entry.mode!=='unknown')stack.push(entry.id);
    }
    return true;
  }

  /** Read reachable descendants in native catalog order.
   *
   * Args:
   *   rootId: Trusted root already resolved by the runtime's binding checks.
   *   cursors: Consumer-confirmed native positions; absent means full replay.
   *   refresh: Synchronous model-version check at the observation cut.
   * Returns:
   *   Changed children with own events, unchanged children with empty events,
   *   and native diagnostics for unavailable branches.
   */
  async read(rootId: SessionId, cursors: Record<string, number> = {}, refresh: (id: SessionId) => boolean = () => false): Promise<Descendant[]> {
    await this.ready;
    const root = await this.observe(rootId,rootId);
    const stack = root.catalog.children.map(entry => ({ entry, parentId: rootId, depth: 1 })).reverse();
    const visited = new Set([rootId]);
    const result: Descendant[] = [];
    for (let position = stack.pop(); position; position = stack.pop()) {
      const { entry, parentId, depth } = position;
      if (visited.has(entry.id)) continue;
      visited.add(entry.id);
      if(entry.mode!=='unknown')this.owners.set(entry.id,rootId);
      let read;
      try { read = await this.observe(entry.id,rootId,cursors[entry.id],refresh); }
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

  private async unchanged(id: SessionId, cached: Catalog): Promise<boolean> {
    const live=this.ctx.sessions.get(id);
    if(live)return live.seq-1===cached.cursor;
    const persistence=this.ctx.sessionPersistence,snapshot=await persistence.stat(id);
    if(this.ctx.sessions.get(id))return false;
    const prior=this.revisions.get(id);
    return !!snapshot && (prior?.identity===persistence.identity && prior.revision===snapshot.revision || sameWitness(cached.witness,snapshot));
  }

  private async observe(id: SessionId, rootId: SessionId, cursor?: number, refresh?: (id: SessionId) => boolean): Promise<{ catalog: Catalog; events: SessionEvent[] }> {
    const cached=this.catalogs.get(id);
    if(cached?.rootId===rootId && (!cached.active || this.ctx.agents?.get(id)?.status==='running') && await this.unchanged(id,cached) && (!refresh || cursor===cached.cursor && !refresh(id)))
      return {catalog:cached,events:[]};
    const live=this.ctx.sessions.get(id);
    if(live && !await this.ctx.sessions.flush(live))throw new RpcError(-32005,'Child Session has no persistence barrier');
    const before=await this.ctx.sessionPersistence.stat(id);
    using observation=await this.ctx.sessionQuery.observeSession(id);
    // Capture model state at the same cut, before the subsequent durability await.
    const replay=refresh?.(id)??false;
    const children=observation.projections?.values.subagentCatalog;
    if(!children)throw new SubagentError('Descendant reads require the subagentCatalog projection','SUBAGENT_CONTROL_PROJECTIONS_UNAVAILABLE');
    const events=refresh && (replay || cursor!==observation.cursor) ? observation.events.slice(observation.inheritedEventCount) : [];
    const agent=this.ctx.agents?.get(id);
    const lastBoundary=agent ? undefined : observation.events.findLast(event=>event.seq>=observation.inheritedEventCount && (event.type==='turn/start'||event.type==='turn/end'));
    const inbox=observation.projections?.values.inbox;
    const active=(agent ? agent.status==='running' : lastBoundary?.type==='turn/start') || !inbox || inbox['next-turn'].length>0 || inbox['next-step'].length>0;
    // An observation can acquire later live events than the first flush. Certify
    // that immutable cut too; never advance the consumer over unflushed events.
    if(observation.source==='live' && live && !await this.ctx.sessions.flush(live))throw new RpcError(-32005,'Child Session has no persistence barrier');
    const after=await this.ctx.sessionPersistence.stat(id);
    const stable=before && after && before.revision===after.revision &&
      (observation.source==='live' ? live?.seq===observation.cursor+1 : observation.revision===after.revision);
    const catalog:Catalog={rootId,cursor:observation.cursor,children,active:!!active,...(stable?{witness:witness(after)}:{})};
    this.catalogs.set(id,catalog);this.owners.set(id,rootId);
    if(stable)this.revisions.set(id,{identity:this.ctx.sessionPersistence.identity,revision:after.revision});
    else this.revisions.delete(id);
    await (await this.storage).table('sessions').put(key(id),catalog);
    return {catalog,events};
  }
}
