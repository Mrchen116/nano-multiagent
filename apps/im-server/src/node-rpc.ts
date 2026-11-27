import {inspectionTimeouts} from '@nano/product-contracts';
import {randomUUID} from 'node:crypto';
import {nodeCommands, inspectionReplies, type NodeCommand, type NodeInput, type NodeOutput, type NodeRequest} from '@nano/product-contracts/node-rpc';
import {decodeNodeResult, isRecord} from './node-rpc-values.js';

interface Transport<Connection> {
  current(nodeId: string): Connection | undefined;
  send(nodeId: string, frame: {type: NodeCommand | 'node.request.cancel'; payload: object}): boolean;
  updating(nodeId: string): boolean;
  windows(nodeId: string): boolean;
}
interface Pending<Connection> {
  connection: Connection | undefined;
  responseType: string;
  complete(payload: unknown): void;
  stop(error: Error): void;
}

const WINDOWS_SLOW_MUTATION_COMMANDS = new Set<NodeCommand>([
  'agent.create',
  'agent.config.apply',
  'agent.config.operation.status',
  'node.setup.request',
]);

/** Own request correlation and timers, independently of IM persistence and business services. */
export class NodeRpc<Connection> {
  private readonly pending = new Map<string, Pending<Connection>>();
  constructor(private readonly transport: Transport<Connection>) {}

  /** Bound temporary inspections; durable timeouts still leave recovery to the caller. */
  readonly request: NodeRequest = <K extends NodeCommand>(nodeId: string, command: K, payload: NodeInput<NoInfer<K>>, signal?: AbortSignal): Promise<NodeOutput<K>> => {
    if (this.transport.updating(nodeId)) return Promise.reject(Object.assign(new Error('Computer is updating; try again when it reconnects'), {statusCode:409}));
    const inspection = nodeCommands[command].inspection, requestId = payload.request_id ?? randomUUID();
    const isWindows = this.transport.windows(nodeId);
    const slowWindowsMutation = isWindows && WINDOWS_SLOW_MUTATION_COMMANDS.has(command);
    const carriesDeadline = inspection || slowWindowsMutation;
    const timeoutMs = inspection ? inspectionTimeouts(isWindows).rpcMs : (slowWindowsMutation ? 60_000 : 10_000);
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
      const timer = setTimeout(() => stop(Object.assign(new Error('node response timeout'), {statusCode:504})),timeoutMs);
      this.pending.set(requestId, {
        connection,
        responseType: nodeCommands[command].responseType,
        complete: value => {
          cleanup();
          try {
            const result = decodeNodeResult(command,value);
            if (inspection && 'error_code' in result && typeof result.error_code === 'string')
              throw Object.assign(new Error('Catalog inspection unavailable'), {statusCode:result.error_code === 'catalog_timeout' ? 504 : 503});
            resolve(result);
          } catch (error) { reject(error); }
        },
        stop,
      });
      if (inspection) signal?.addEventListener('abort',abort,{once:true});
      if (!this.transport.send(nodeId, {type:command, payload:{...payload,request_id:requestId,...(carriesDeadline ? {deadline_at:Date.now()+timeoutMs} : {})}})) {
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
