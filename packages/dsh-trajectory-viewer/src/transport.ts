const calls = new Set(['session/list', 'session/page', 'session/projections', 'session/attachment']);
const streams = new Set(['session/control', 'session/follow']);

interface Pending {
  resolve(value: any): void;
  reject(error: Error): void;
}

/** Carry the official decoded RPC vocabulary over one parent-owned read capability. */
export function createReadonlyTransport(port: MessagePort, options: {
  onGenerationChanged(): void;
  onInterrupted?(message: string): void;
}) {
  let serial = 0;
  let disposed = false;
  const pending = new Map<string, Pending>();
  const active = new Set<string>();
  const localHolds = new Set<() => void>();
  function request(type: string, fields: Record<string, unknown>, signal?: AbortSignal): Promise<any> {
    if (disposed) return Promise.reject(new Error('Viewer disposed'));
    if (signal?.aborted) return Promise.reject(signal.reason ?? new Error('Read aborted'));
    const requestId = String(++serial);
    return new Promise((resolve, reject) => {
      const abort = () => { pending.delete(requestId); reject(signal?.reason ?? new Error('Read aborted')); };
      const clean = () => signal?.removeEventListener('abort', abort);
      pending.set(requestId, {
        resolve: value => { clean(); resolve(value); },
        reject: error => { clean(); reject(error); },
      });
      signal?.addEventListener('abort', abort, { once: true });
      port.postMessage({ type, requestId, ...fields });
    });
  }
  const receive = (event: MessageEvent) => {
    const message = event.data;
    const waiter = pending.get(message?.requestId);
    if (!waiter) return;
    pending.delete(message.requestId);
    if (message.type === 'result') waiter.resolve(message.value);
    else {
      waiter.reject(new Error(`${message.code}: ${message.message}`));
      if (message.code === 'generation_changed') options.onGenerationChanged();
      else options.onInterrupted?.(message.message);
    }
  };
  port.addEventListener('message', receive);
  port.start();
  function assertAllowed(endpoint: string, method: string, allowed: Set<string>) {
    if (endpoint !== '/api' || !allowed.has(method)) throw new Error(`Read-only viewer denied ${method}`);
  }
  function abortStream(streamId: string) {
    if (!active.delete(streamId)) return;
    // A stream release is observation cleanup; it never calls session/cancel.
    void request('abort', { streamId }).catch(() => {});
  }
  const rpc = {
    async call(endpoint: string, method: string, params: unknown, signal?: AbortSignal) {
      assertAllowed(endpoint, method, calls);
      return request('call', { method, params }, signal);
    },
    async *open(endpoint: string, method: string, params: unknown, signal: AbortSignal): AsyncGenerator<any> {
      if (endpoint === '/api' && method === '$events') {
        // The shell has already authenticated the sole read capability. Host-wide
        // events are deliberately not forwarded into this isolated composition.
        yield { type: 'ready', clientId: crypto.randomUUID(), host: { home: '' } };
        await new Promise<void>(resolve => {
          const finish = () => { localHolds.delete(finish); signal.removeEventListener('abort', finish); resolve(); };
          localHolds.add(finish);
          if (signal.aborted || disposed) finish();
          else signal.addEventListener('abort', finish, { once: true });
        });
        return;
      }
      assertAllowed(endpoint, method, streams);
      // Complete open even if its caller leaves meanwhile, so the acquired
      // handle can still be released rather than leaked at the parent.
      const { streamId } = await request('open', { method, params });
      active.add(streamId);
      const abort = () => abortStream(streamId);
      signal.addEventListener('abort', abort, { once: true });
      try {
        while (!signal.aborted && !disposed) {
          const batch = await request('next', { streamId }, signal);
          for (const frame of batch.frames) {
            if (signal.aborted || disposed) return;
            yield frame;
          }
          if (batch.done) return;
        }
      } finally {
        signal.removeEventListener('abort', abort);
        abortStream(streamId);
      }
    },
  };
  return {
    rpc,
    dispose() {
      if (disposed) return;
      for (const streamId of active) abortStream(streamId);
      disposed = true;
      for (const finish of localHolds) finish();
      for (const waiter of pending.values()) waiter.reject(new Error('Viewer disposed'));
      pending.clear();
      port.removeEventListener('message', receive);
      port.close();
    },
  };
}
