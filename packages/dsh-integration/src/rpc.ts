/** Bidirectional JSON-RPC for the private node/runtime stdio connection. */
import { createInterface, type Interface } from 'node:readline';
import type { Readable, Writable } from 'node:stream';

type Handler = (params: unknown) => unknown | Promise<unknown>;
interface Pending { resolve(value: unknown): void; reject(error: Error): void }

/** A protocol failure retains its stable code without prescribing a retry. */
export class RpcError extends Error {
  constructor(readonly code: number, message: string) { super(message); this.name = 'RpcError'; }
}

/** Keep response dispatch independent from handlers awaiting reverse calls. */
export class RpcPeer {
  private readonly lines: Interface;
  private readonly handlers = new Map<string, Handler>();
  private readonly pending = new Map<number, Pending>();
  private readonly listeners = new Set<(method: string, params: unknown) => void>();
  private nextId = 1;
  private closed = false;

  constructor(input: Readable, private readonly output: Writable) {
    this.lines = createInterface({ input, crlfDelay: Infinity });
    this.lines.on('line', line => { void this.receive(line); });
    this.lines.on('close', () => this.close());
    input.on('error', () => this.close());
    output.on('error', () => this.close());
  }

  /** Register one method; returned disposer belongs to the serving plugin. */
  handle(method: string, handler: Handler): () => void {
    if (this.handlers.has(method)) throw new Error(`RPC handler already registered: ${method}`);
    this.handlers.set(method, handler);
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
      try { this.write({ jsonrpc: '2.0', id, method, params }); }
      catch (error) { this.pending.delete(id); reject(error); }
    });
  }

  /** Publish a transient notification; durable events remain separately queryable. */
  notify(method: string, params: unknown): void {
    if (!this.closed) this.write({ jsonrpc: '2.0', method, params });
  }

  /** Reject unresolved calls and release this reader without owning the streams. */
  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.lines.close();
    for (const pending of this.pending.values()) pending.reject(new Error('RPC connection closed; operation outcome may be unknown'));
    this.pending.clear();
    this.listeners.clear();
  }

  private write(value: unknown): void {
    this.output.write(`${JSON.stringify(value)}\n`);
  }

  private async receive(line: string): Promise<void> {
    let message: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(line);
      if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('invalid');
      message = parsed as Record<string, unknown>;
    } catch {
      this.write({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Invalid JSON-RPC frame' } });
      return;
    }
    if (typeof message.method === 'string') {
      if (message.id === undefined) {
        for (const listener of this.listeners) listener(message.method, message.params);
        return;
      }
      try {
        const handler = this.handlers.get(message.method);
        if (!handler) throw new RpcError(-32601, `Unknown method: ${message.method}`);
        const result = await handler(message.params);
        if (!this.closed) this.write({ jsonrpc: '2.0', id: message.id, result: result ?? null });
      } catch (error) {
        if (!this.closed) this.write({ jsonrpc: '2.0', id: message.id, error: {
          code: error instanceof RpcError ? error.code : -32000,
          message: error instanceof Error ? error.message : 'Runtime operation failed',
        } });
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
