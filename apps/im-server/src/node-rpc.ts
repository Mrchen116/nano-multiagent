import {randomUUID} from 'node:crypto';
import {nodeResponseTypes, type NodeCommand, type NodeInput, type NodeOutput, type NodeRequest} from './node-rpc-contracts.js';
import {decodeNodeResult, isRecord} from './node-rpc-values.js';

interface Transport<Connection> {
  current(nodeId: string): Connection | undefined;
  send(nodeId: string, frame: {type: NodeCommand; payload: object}): boolean;
  updating(nodeId: string): boolean;
}
interface Pending<Connection> {
  connection: Connection | undefined;
  responseType: string;
  complete(payload: unknown): void;
  reject(error: Error): void;
  timer: NodeJS.Timeout;
}

/** Own request correlation and timers, independently of IM persistence and business services. */
export class NodeRpc<Connection> {
  private readonly pending = new Map<string, Pending<Connection>>();
  constructor(private readonly transport: Transport<Connection>) {}

  /** Send one command on the current connection; a timeout leaves durable recovery to its caller. */
  readonly request: NodeRequest = <K extends NodeCommand>(nodeId: string, command: K, payload: NodeInput<NoInfer<K>>): Promise<NodeOutput<K>> => {
    if (this.transport.updating(nodeId)) return Promise.reject(Object.assign(new Error('Computer is updating; try again when it reconnects'), {statusCode:409}));
    const requestId = payload.request_id ?? randomUUID();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(requestId);
        reject(Object.assign(new Error('node response timeout'), {statusCode:504}));
      }, 10000);
      this.pending.set(requestId, {
        connection: this.transport.current(nodeId),
        responseType: nodeResponseTypes[command],
        complete: value => {
          try { resolve(decodeNodeResult(command, value)); }
          catch (error) { reject(error); }
        },
        reject,
        timer,
      });
      if (!this.transport.send(nodeId, {type:command, payload:{...payload,request_id:requestId}})) {
        clearTimeout(timer);
        this.pending.delete(requestId);
        reject(Object.assign(new Error('node offline'), {statusCode:503}));
      }
    });
  };

  /** Match an already authenticated frame; unrelated and late frames are left to the dispatcher. */
  accept(connection: Connection, type: string, payload: unknown): boolean {
    if (!isRecord(payload) || typeof payload.request_id !== 'string') return false;
    const waiter = this.pending.get(payload.request_id);
    if (!waiter || waiter.connection !== connection || waiter.responseType !== type) return false;
    clearTimeout(waiter.timer);
    this.pending.delete(payload.request_id);
    waiter.complete(payload);
    return true;
  }

  /** Reject outstanding callers before the server releases its database and sockets. */
  close(): void {
    for (const waiter of this.pending.values()) {
      clearTimeout(waiter.timer);
      waiter.reject(new Error('server stopped'));
    }
    this.pending.clear();
  }
}
