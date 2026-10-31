import {randomUUID} from 'node:crypto';
import type {ImContext} from './context.js';
import type {NodeCapabilities} from './node-rpc-contracts.js';

/** Scope confirmed candidates to the exact authenticated binding and saved configuration. */
export interface CatalogScope {
  owner_id: string;
  node_id: string;
  agent_id?: string;
  node_epoch: number;
  workspace_root?: string | null;
  profile_version?: number;
  connection: object;
}
export interface CatalogRead {
  capabilities: NodeCapabilities;
  captured_at: string;
  current(): boolean;
}
interface Slot {
  scope: CatalogScope;
  result?: CatalogRead;
  capturedAt?: number;
  failure?: {error: unknown; retryAt: number};
  pending?: Promise<CatalogRead>;
  abort?: AbortController;
  requestId?: string;
}
const unavailable = () => Object.assign(new Error('Catalog read superseded'), {statusCode:503});

/** Own bounded, memory-only candidates and refreshes independently of configuration writes. */
export class CatalogReads {
  private readonly slots = new Map<string, Slot>();
  private active = 0;

  /** Invalidate delivered results and cancel waiters before a changed catalog can be read. */
  invalidateNode(nodeId: string): void {
    for (const [key, slot] of this.slots) if (slot.scope.node_id === nodeId) {
      this.slots.delete(key);
      slot.abort?.abort(unavailable());
    }
  }

  /** Reuse a confirmed value for five minutes or join one deadline-bounded refresh.
   *
   * Args:
   *   scope: Authenticated identity and current committed configuration.
   *   load: Fresh inspection which receives the refresh owner's cancellation signal.
   * Returns:
   *   Candidates, their original capture time and a fence for final response/snapshot writes.
   */
  read(scope: CatalogScope, load: (signal: AbortSignal, requestId: string) => Promise<NodeCapabilities>): Promise<CatalogRead> {
    const key = JSON.stringify([scope.owner_id,scope.node_id,scope.agent_id ?? null,1]);
    let slot = this.slots.get(key);
    if (slot && (slot.scope.connection !== scope.connection || slot.scope.node_epoch !== scope.node_epoch
      || slot.scope.workspace_root !== scope.workspace_root || slot.scope.profile_version !== scope.profile_version)) {
      this.slots.delete(key);
      slot.abort?.abort(unavailable());
      slot = undefined;
    }
    if (!slot) {
      if (this.slots.size >= 256) {
        const victim = [...this.slots].find(([, value]) => !value.pending);
        if (!victim) return Promise.reject(Object.assign(new Error('Catalog refresh capacity reached'), {statusCode:503}));
        this.slots.delete(victim[0]);
      }
      slot = {scope};
    }
    this.slots.delete(key);
    this.slots.set(key,slot);
    const entry = slot, current = () => this.slots.get(key) === entry;
    if (entry.result && Date.now() - entry.capturedAt! < 300000) return Promise.resolve(entry.result);
    if (entry.pending) return entry.pending;
    if (entry.failure && Date.now() < entry.failure.retryAt) return Promise.reject(entry.failure.error);
    const controller = new AbortController(), started = Date.now();
    entry.abort = controller;
    entry.requestId = randomUUID();
    this.active++;
    this.metric('start', 0, entry);
    let abort!: () => void;
    const canceled = new Promise<never>((_resolve,reject) => {
      abort = () => reject(controller.signal.reason ?? unavailable());
      controller.signal.addEventListener('abort',abort,{once:true});
    });
    const timer = setTimeout(() => controller.abort(Object.assign(new Error('Catalog response timeout'), {statusCode:504})),9000);
    // A loader may fail synchronously or ignore abort; neither may retain this slot's waiter.
    let loaded: Promise<NodeCapabilities>;
    try { loaded = load(controller.signal,entry.requestId); } catch (error) { loaded = Promise.reject(error); }
    entry.pending = Promise.race([loaded,canceled]).then(capabilities => {
      if (!current()) throw unavailable();
      entry.capturedAt = Date.now();
      entry.failure = undefined;
      entry.result = {capabilities,captured_at:new Date(entry.capturedAt).toISOString(),current};
      this.metric('success',Date.now()-started,entry);
      return entry.result;
    }).catch(error => {
      if (current()) entry.failure = {error,retryAt:Date.now()+1000};
      this.metric((error as {statusCode?:number})?.statusCode === 504 ? 'timeout' : controller.signal.aborted ? 'cancelled' : 'failed',Date.now()-started,entry);
      throw error;
    }).finally(() => {
      clearTimeout(timer);
      controller.signal.removeEventListener('abort',abort);
      entry.pending = undefined;
      entry.abort = undefined;
      this.active--;
      this.metric('settled',Date.now()-started,entry);
    });
    return entry.pending;
  }

  private metric(result: string, duration: number, slot: Slot): void {
    console.info(JSON.stringify({event:'catalog_refresh',request_id:slot.requestId,result,duration_ms:duration,active_catalog_refreshes:this.active,
      stale_age_ms:slot.capturedAt === undefined ? null : Date.now()-slot.capturedAt}));
  }
}
const contexts = new WeakMap<ImContext,CatalogReads>();
/** Share refresh ownership across routes and authenticated Gateway invalidation events. */
export function catalogReads(ctx: ImContext): CatalogReads {
  let reads = contexts.get(ctx);
  if (!reads) { reads = new CatalogReads(); contexts.set(ctx,reads); }
  return reads;
}
