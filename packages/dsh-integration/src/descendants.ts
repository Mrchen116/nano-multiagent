/** Keep Work lineage and durable cuts without retaining native history bodies. */
import type { Context } from '@deepseek-ai/cordis';
import { SessionId, SessionLogOffset, type Session, type SessionEvent } from '@deepseek-ai/dsh-session';
import type { SessionPersistenceRevision, SessionPersistenceSnapshot } from '@deepseek-ai/dsh-session-persistence';
import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { SubagentError, type SubagentCatalogEntry, type SubagentDescendantListEntry } from '@deepseek-ai/dsh-subagent';
import { SessionQueryError, type SessionObservation } from '@deepseek-ai/dsh-session-query';
import type { RuntimeWorkPage } from '@nano/product-contracts';
import { z } from 'zod';
import { RpcError } from './rpc.js';

interface Witness { header: string; eventCount?: number; sizeBytes?: number }
interface Catalog {
  rootId: string;
  cursor: number;
  children: SubagentCatalogEntry[];
  active: boolean;
  interruptedTurnEnd?: number | null;
  witness?: Witness;
}
interface CatalogDomain extends DomainSpec { tables: { sessions: DomainTableSpec<string, Catalog> } }
export const descendantDomain: CatalogDomain = defineDomain({name:'nano_work_catalog',version:1,layout:'per-record',tables:{
  sessions:domainTable(z.object({rootId:z.string(),cursor:z.number(),children:z.array(z.custom<SubagentCatalogEntry>()),active:z.boolean(),
    interruptedTurnEnd:z.number().nullable().optional(),
    witness:z.object({header:z.string(),eventCount:z.number().optional(),sizeBytes:z.number().optional()}).optional()})),
}});
type Descendant = SubagentDescendantListEntry & { throughSeq?: number };
interface Edge {
  root: SessionId;
  parent: SessionId;
  entry: SubagentCatalogEntry;
  pendingSeq?: number;
}
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
  private readonly edges = new Map<SessionId, Edge>();
  private readonly storage;
  readonly ready: Promise<void>;

  constructor(private readonly ctx: Context) {
    this.storage = ctx.storageDomain.open(descendantDomain);
    this.ready = this.storage.then(storage => {
      for (const [encoded, catalog] of storage.table('sessions').entries()) {
        const id = SessionId(Buffer.from(encoded,'base64url').toString());
        this.catalogs.set(id,catalog); this.owners.set(id,catalog.rootId);
        this.indexEdges(id, catalog);
      }
    });
    ctx.effect(() => async () => { await this.ready; await (await this.storage).close(); });
  }

  /** Resolve known lineage after live ancestors unload. */
  rootOf(id: string): string | undefined { return this.owners.get(id); }

  /** Forget the retired identities after their readers have settled. */
  forget(ids: Iterable<string>): void {
    for (const id of ids) {
      this.owners.delete(id);
      this.catalogs.delete(SessionId(id));
      this.revisions.delete(SessionId(id));
      this.edges.delete(SessionId(id));
    }
  }

  /** Remember live ownership without consuming inherited catalog events. */
  remember(session: Session, event: SessionEvent, rootId: string): SessionId | undefined {
    this.owners.set(session.id,rootId);
    if (!session.isOwnSeq(event.seq) || event.type !== 'subagent/catalog' || event.data.mode === 'unknown') return;
    const {childId:id, childCreatedAt:createdAt, mode, label} = event.data;
    this.owners.set(id,rootId);
    const entry: SubagentCatalogEntry = mode === 'continuable' ? {id,createdAt,mode,label:label!} : {id,createdAt,mode,label};
    this.edges.set(id,{root:SessionId(rootId),parent:session.id,entry,pendingSeq:event.seq});
    return id;
  }

  /** A child can trigger Work only after its parent has announced the native edge. */
  hasChild(id: string): boolean { return this.edges.has(SessionId(id)); }

  private indexEdges(parent: SessionId, catalog: Catalog): void {
    for (const entry of catalog.children) if (entry.mode !== 'unknown') {
      this.owners.set(entry.id,catalog.rootId);
      this.edges.set(entry.id,{root:SessionId(catalog.rootId),parent,entry});
    }
  }

  private async confirm(edge: Edge): Promise<void> {
    if (edge.pendingSeq === undefined) return;
    const parent = this.ctx.sessions.get(edge.parent);
    if (parent) {
      if (!await this.ctx.sessions.flush(parent)) throw new RpcError(-32005,'Parent catalog has no persistence barrier');
    } else {
      const stored = await this.ctx.sessionPersistence.open(edge.parent,'read');
      try {
        const event = (await stored.read(SessionLogOffset(edge.pendingSeq),1)).events[0];
        if (event?.type !== 'subagent/catalog' || event.data.childId !== edge.entry.id)
          throw new RpcError(-32005,'Parent catalog fact is unavailable');
      } finally { await stored.close(); }
    }
    edge.pendingSeq = undefined;
  }

  /** Fetch one trusted lineage, without reading unrelated sibling catalogs. */
  async targets(root: SessionId, child: SessionId): Promise<Descendant[]> {
    await this.ready;
    const ancestry: Edge[] = [];
    const visited = new Set<SessionId>();
    for (let id = child; id !== root;) {
      const edge = this.edges.get(id);
      if (!edge || edge.root !== root || visited.has(id)) throw new RpcError(-32004,'Child has no trusted Work lineage');
      visited.add(id);
      ancestry.push(edge);
      id = edge.parent;
    }
    const rows: Descendant[] = [];
    for (const edge of ancestry.reverse()) {
      await this.confirm(edge);
      const live = this.ctx.sessions.get(edge.entry.id);
      const cached = this.catalogs.get(edge.entry.id);
      const throughSeq = live ? live.seq - 1 : cached && !cached.active && await this.unchanged(edge.entry.id,cached) ? cached.cursor : undefined;
      const {createdAt: _, ...identity} = edge.entry;
      if (identity.mode === 'unknown') continue;
      rows.push({...identity,kind:'child',parentId:edge.parent,depth:rows.length+1,
        activity:live ? 'running' : 'inactive',hasChildren:!!cached?.children.length,throughSeq});
    }
    return rows;
  }

  /** Read the latest crash interruption of each supported direct child without activating it. */
  async interruptedChildren(rootId: SessionId): Promise<{id: SessionId; turnEnd: number}[]> {
    const {catalog} = await this.observe(rootId, rootId);
    const interrupted: {id: SessionId; turnEnd: number}[] = [];
    for (const child of catalog.children) {
      if (child.mode === 'unknown') continue;
      try {
        const {catalog: observed} = await this.observe(child.id, rootId, {requireInterruption: true});
        if (observed.interruptedTurnEnd != null && !this.ctx.agents.get(child.id)) {
          interrupted.push({id: child.id, turnEnd: observed.interruptedTurnEnd});
        }
      } catch (error) {
        if (!(error instanceof SessionQueryError)) throw error;
        this.ctx.logger.warn(`Cannot inspect subagent ${child.id} for interruption: ${error.message}`);
      }
    }
    return interrupted;
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

  /** Walk native lineage without attaching event bodies to catalog rows. */
  catalog(rootId: SessionId): AsyncIterable<Descendant> { return this.scan(rootId); }

  /** A hot event page does not materialize that Session's historical child catalog. */
  async eventPage(root: SessionId, id: SessionId, afterSeq: number, modelChanged: boolean,
    livePage: (session: Session, head: number) => Promise<RuntimeWorkPage>,
    coldPage: (cut: SessionObservation) => Promise<RuntimeWorkPage>): Promise<RuntimeWorkPage | undefined> {
    const edge = this.edges.get(id);
    if (!edge || edge.root !== root) throw new RpcError(-32004,'Child has no trusted Work lineage');
    await this.confirm(edge);
    const live = this.ctx.sessions.get(id);
    if (live) {
      const head = live.seq - 1;
      if (!await this.ctx.sessions.flush(live)) throw new RpcError(-32005,'Child Session has no persistence barrier');
      return livePage(live,head);
    }
    const cached = this.catalogs.get(id);
    if (!modelChanged && cached && !cached.active && cached.cursor === afterSeq && await this.unchanged(id,cached)) return;
    // Cold reads share the prepared native observation with recovery discovery.
    using cut = await this.ctx.sessionQuery.observeSession(id);
    return coldPage(cut);
  }

  private async *scan(rootId: SessionId): AsyncGenerator<Descendant> {
    await this.ready;
    const root = await this.observe(rootId,rootId);
    const stack = root.catalog.children.map(entry => ({ entry, parentId: rootId, depth: 1 })).reverse();
    const visited = new Set([rootId]);
    for (let position = stack.pop(); position; position = stack.pop()) {
      const { entry, parentId, depth } = position;
      if (visited.has(entry.id)) continue;
      visited.add(entry.id);
      if (entry.mode === 'unknown') {
        yield {kind:'diagnostic',id:entry.id,parentId,depth,reason:'unsupported'};
        continue;
      }
      this.owners.set(entry.id,rootId);
      let read;
      try { read = await this.observe(entry.id,rootId); }
      catch (error) {
        if (error instanceof SubagentError || error instanceof RpcError) throw error;
        const code = (error as { code?: string })?.code;
        yield { kind: 'diagnostic', id: entry.id, parentId, depth,
          reason: code === 'SESSION_QUERY_CORRUPT_SESSION' || code === 'SESSION_QUERY_SOURCE_CONFLICT' ? 'corrupt' : 'unavailable' };
        continue;
      }
      const { createdAt: _, ...identity } = entry;
      yield { ...identity, kind: 'child', parentId, depth,
        activity: this.ctx.sessions.get(entry.id) ? 'running' : 'inactive',
        hasChildren: read.catalog.children.length > 0, throughSeq: read.catalog.cursor };

      for (const child of [...read.catalog.children].reverse()) stack.push({ entry: child, parentId: entry.id, depth: depth + 1 });
    }
  }

  private async unchanged(id: SessionId, cached: Catalog): Promise<boolean> {
    const live=this.ctx.sessions.get(id);
    if(live)return live.seq-1===cached.cursor;
    const persistence=this.ctx.sessionPersistence,snapshot=await persistence.stat(id);
    if(this.ctx.sessions.get(id))return false;
    const prior=this.revisions.get(id);
    return !!snapshot && (prior?.identity===persistence.identity && prior.revision===snapshot.revision || sameWitness(cached.witness,snapshot));
  }

  private async observe(id: SessionId, rootId: SessionId, {requireInterruption}: {
    requireInterruption?: boolean;
  } = {}): Promise<{ catalog: Catalog }> {
    const cached=this.catalogs.get(id);
    if(cached?.rootId===rootId && (!requireInterruption || cached.interruptedTurnEnd !== undefined) &&
      (!cached.active || this.ctx.agents?.get(id)?.status==='running') && await this.unchanged(id,cached))
      return {catalog:cached};
    const live=this.ctx.sessions.get(id);
    if(live && !await this.ctx.sessions.flush(live))throw new RpcError(-32005,'Child Session has no persistence barrier');
    const before=await this.ctx.sessionPersistence.stat(id);
    using observation=await this.ctx.sessionQuery.observeSession(id);
    const children=observation.projections?.values.subagentCatalog;
    if(!children)throw new SubagentError('Descendant reads require the subagentCatalog projection','SUBAGENT_CONTROL_PROJECTIONS_UNAVAILABLE');
    const agent=this.ctx.agents?.get(id);
    const lastBoundary=observation.events.findLast(event=>event.seq>=observation.inheritedEventCount && (event.type==='turn/start'||event.type==='turn/end'));
    const interruptedTurnEnd=lastBoundary?.type==='turn/end' && lastBoundary.data.reason.kind==='interrupted' ? lastBoundary.seq : null;
    const inbox=observation.projections?.values.inbox;
    const active=(agent ? agent.status==='running' : lastBoundary?.type==='turn/start') || !inbox || inbox['next-turn'].length>0 || inbox['next-step'].length>0;
    // An observation can acquire later live events than the first flush. Certify
    // that immutable cut too; never advance the consumer over unflushed events.
    if(observation.source==='live' && live && !await this.ctx.sessions.flush(live))throw new RpcError(-32005,'Child Session has no persistence barrier');
    const after=await this.ctx.sessionPersistence.stat(id);
    const stable=before && after && before.revision===after.revision &&
      (observation.source==='live' ? live?.seq===observation.cursor+1 : observation.revision===after.revision);
    const catalog:Catalog={rootId,cursor:observation.cursor,children,active:!!active,interruptedTurnEnd,...(stable?{witness:witness(after)}:{})};
    this.catalogs.set(id,catalog);this.owners.set(id,rootId);
    this.indexEdges(id,catalog);
    if(stable)this.revisions.set(id,{identity:this.ctx.sessionPersistence.identity,revision:after.revision});
    else this.revisions.delete(id);
    await (await this.storage).table('sessions').put(key(id),catalog);
    return {catalog};
  }
}
