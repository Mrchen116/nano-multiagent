import {randomUUID} from 'node:crypto';
import {nodeResponseTypes, type NodeCommand, type NodeInput, type NodeOutput, type NodeRequest} from './node-rpc-contracts.js';
import {decodeNodeResult, isRecord} from './node-rpc-values.js';

const inspections = new Set<NodeCommand>(['agent.capabilities.resolve','node.capabilities.resolve','agent.prompt.preview.request','node.prompt.preview.request']);
const inspectionReplies = new Set<string>([...inspections].map(command => nodeResponseTypes[command]));
interface Transport<Connection> {
  current(nodeId: string): Connection | undefined;
  send(nodeId: string, frame: {type: NodeCommand | 'node.request.cancel'; payload: object}): boolean;
  updating(nodeId: string): boolean;
}
interface Pending<Connection> {
  connection: Connection | undefined;
  responseType: string;
  complete(payload: unknown): void;
  stop(error: Error): void;
}

/** Own request correlation and timers, independently of IM persistence and business services. */
export class NodeRpc<Connection> {
  private readonly pending = new Map<string, Pending<Connection>>();
  constructor(private readonly transport: Transport<Connection>) {}

  /** Bound temporary inspections; durable timeouts still leave recovery to the caller. */
  readonly request: NodeRequest = <K extends NodeCommand>(nodeId: string, command: K, payload: NodeInput<NoInfer<K>>, signal?: AbortSignal): Promise<NodeOutput<K>> => {
    if (this.transport.updating(nodeId)) return Promise.reject(Object.assign(new Error('Computer is updating; try again when it reconnects'), {statusCode:409}));
    const inspection = inspections.has(command), requestId = payload.request_id ?? randomUUID();
    if (inspection && signal?.aborted) return Promise.reject(Object.assign(new Error('Catalog request cancelled'), {statusCode:503}));
    return new Promise((resolve, reject) => {
      const connection = this.transport.current(nodeId);
      const cleanup = () => { clearTimeout(timer); signal?.removeEventListener('abort',abort); this.pending.delete(requestId); };
      const stop = (error: Error) => {
        cleanup();
        if (inspection && connection !== undefined && this.transport.current(nodeId) === connection)
          this.transport.send(nodeId,{type:'node.request.cancel',payload:{target_request_id:requestId}});
        reject(error);
      };
      const abort = () => stop(Object.assign(new Error('Catalog request cancelled'), {statusCode:503}));
      const timer = setTimeout(() => stop(Object.assign(new Error('node response timeout'), {statusCode:504})),inspection ? 9000 : 10000);
      this.pending.set(requestId, {
        connection,
        responseType: nodeResponseTypes[command],
        complete: value => {
          cleanup();
          try {
            if (inspection && isRecord(value) && typeof value.error_code === 'string')
              throw Object.assign(new Error('Catalog inspection unavailable'), {statusCode:value.error_code === 'catalog_timeout' ? 504 : 503});
            resolve(decodeNodeResult(command, value));
          } catch (error) { reject(error); }
        },
        stop,
      });
      if (inspection) signal?.addEventListener('abort',abort,{once:true});
      if (!this.transport.send(nodeId, {type:command, payload:{...payload,request_id:requestId,...(inspection ? {deadline_at:Date.now()+9000} : {})}})) {
        cleanup();
        reject(Object.assign(new Error('node offline'), {statusCode:503}));
      }
    });
  };

  /** Consume authenticated inspection late replies; durable receipts retain dispatcher semantics. */
  accept(connection: Connection, type: string, payload: unknown): boolean {
    if (!isRecord(payload) || typeof payload.request_id !== 'string') return false;
    const waiter = this.pending.get(payload.request_id);
    if (!waiter) return inspectionReplies.has(type);
    if (waiter.connection !== connection || waiter.responseType !== type) return false;
    waiter.complete(payload);
    return true;
  }

  /** Release inspections on disconnect without changing durable mutation recovery. */
  disconnect(connection: Connection): void {
    for (const waiter of this.pending.values()) if (waiter.connection === connection && inspectionReplies.has(waiter.responseType))
      waiter.stop(Object.assign(new Error('node offline'), {statusCode:503}));
  }

  /** Reject callers and cancel temporary inspections before sockets are released. */
  close(): void {
    for (const waiter of this.pending.values()) waiter.stop(new Error('server stopped'));
  }
}
