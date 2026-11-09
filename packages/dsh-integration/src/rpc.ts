/** Bidirectional JSON-RPC for the private node/runtime stdio connection. */
import { createInterface, type Interface } from 'node:readline';
import type { Readable, Writable } from 'node:stream';

type Handler = (params: unknown) => unknown | Promise<unknown>;
interface Pending { resolve(value: unknown): void; reject(error: Error): void }
interface Frame { value: unknown; resolve(): void; reject(error: Error): void; key?: string }
const queueLimit = 256;

/** A protocol failure retains its stable code without prescribing a retry. */
export class RpcError extends Error {
  constructor(readonly code: number, message: string) { super(message); this.name = 'RpcError'; }
}

/** Keep response dispatch independent from handlers awaiting reverse calls. */
export class RpcPeer {
  private readonly lines: Interface;
  private readonly handlers = new Map<string, { handler: Handler; pull: boolean }>();
  private readonly pending = new Map<number, Pending>();
  private readonly listeners = new Set<(method: string, params: unknown) => void>();
  private nextId = 1;
  private closed = false;
  private readonly frames: Frame[] = [];
  private blocked?: Frame;
  private pulls = Promise.resolve();
  private pulling = 0;

  constructor(input: Readable, private readonly output: Writable, private readonly onFailure?: (error: Error) => void) {
    this.lines = createInterface({ input, crlfDelay: Infinity });
    this.lines.on('line', line => { void this.receive(line); });
    this.lines.on('close', () => this.fail(new Error('RPC input ended')));
    input.on('error', error => this.fail(error));
    output.on('error', error => this.fail(error));
    output.on('close', () => this.fail(new Error('RPC output closed')));
    output.on('drain', this.drain);
  }

  /** Register a method. Paged producers may share a single lane through writeout. */
  handle(method: string, handler: Handler, options?: {pull?: boolean}): () => void {
    if (this.handlers.has(method)) throw new Error(`RPC handler already registered: ${method}`);
    this.handlers.set(method, {handler, pull: options?.pull === true});
    return () => { this.handlers.delete(method); };
  }

  /** Observe one-way events without waiting for any in-flight request. */
  onNotification(listener: (method: string, params: unknown) => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  /** Send once; callers must query durable operation identity after uncertain loss. */
  request(method: string, params: unknown): Promise<unknown> {
    if (this.closed) return Promise.reject(new Error('RPC connection closed'));
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      void this.send({ jsonrpc: '2.0', id, method, params }).catch(error => {
        this.pending.delete(id); reject(error);
      });
    });
  }

  /** Publish a notification; replaceable hints may be combined while blocked. */
  notify(method: string, params: unknown, key?: string): void {
    if (!this.closed) void this.send({ jsonrpc: '2.0', method, params }, key).catch(error => this.fail(error));
  }

  /** Reject unresolved calls and release this reader without owning the streams. */
  close(error = new Error('RPC connection closed; operation outcome may be unknown')): void {
    if (this.closed) return;
    this.closed = true;
    this.lines.close();
    this.output.off('drain', this.drain);
    this.blocked?.reject(error);
    this.blocked = undefined;
    for (const frame of this.frames.splice(0)) frame.reject(error);
    for (const pending of this.pending.values()) pending.reject(error);
    this.pending.clear();
    this.listeners.clear();
  }

  private fail(error: Error): void {
    if (this.closed) return;
    this.close(error);
    this.onFailure?.(error);
  }

  private send(value: unknown, key?: string): Promise<void> {
    if (this.closed) return Promise.reject(new Error('RPC connection closed'));
    const queued = key === undefined ? undefined : this.frames.find(frame => frame.key === key);
    if (queued) { queued.value = value; return Promise.resolve(); }
    if (this.frames.length >= queueLimit) {
      const error = new Error('RPC output queue is full; operation outcome may be unknown');
      this.fail(error);
      return Promise.reject(error);
    }
    return new Promise((resolve, reject) => {
      this.frames.push({value, key, resolve, reject});
      this.pump();
    });
  }

  private readonly drain = () => {
    this.blocked?.resolve();
    this.blocked = undefined;
    this.pump();
  };

  private pump(): void {
    while (!this.closed && !this.blocked) {
      const frame = this.frames.shift();
      if (!frame) return;
      let data: string;
      try { data = `${JSON.stringify(frame.value)}\n`; }
      catch (error) { frame.reject(error as Error); continue; }
      frame.value = undefined;
      try {
        if (this.output.write(data)) frame.resolve();
        else this.blocked = frame;
      } catch (error) {
        frame.reject(error as Error);
        this.fail(error as Error);
      }
    }
  }

  private async receive(line: string): Promise<void> {
    if (this.closed) return;
    let message: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(line);
      if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('invalid');
      message = parsed as Record<string, unknown>;
    } catch {
      await this.send({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Invalid JSON-RPC frame' } }).catch(() => {});
      return;
    }
    if (typeof message.method === 'string') {
      if (message.id === undefined) {
        for (const listener of this.listeners) listener(message.method, message.params);
        return;
      }
      const entry = this.handlers.get(message.method);
      const respond = async () => {
        if (this.closed) return;
        let response: unknown;
        try {
          if (!entry) throw new RpcError(-32601, `Unknown method: ${message.method}`);
          const result = await entry.handler(message.params);
          response = {jsonrpc:'2.0', id:message.id, result:result ?? null};
        } catch (error) {
          response = {jsonrpc:'2.0', id:message.id, error:{
            code:error instanceof RpcError ? error.code : -32000,
            message:error instanceof Error ? error.message : 'Runtime operation failed',
          }};
        }
        await this.send(response).catch(error => this.fail(error));
      };
      if (!entry?.pull) await respond();
      else if (this.pulling >= queueLimit) this.fail(new Error('RPC pull queue is full'));
      else {
        this.pulling++;
        this.pulls = this.pulls.then(respond).finally(() => { this.pulling--; });
        await this.pulls;
      }
    } else if (typeof message.id === 'number') {
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error && typeof message.error === 'object') {
        const failure = message.error as { code: number; message: string };
        pending.reject(new RpcError(failure.code, failure.message));
      } else pending.resolve(message.result);
    }
  }
}
