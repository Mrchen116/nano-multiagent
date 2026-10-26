import { AsyncLocalStorage } from 'node:async_hooks';

/** Request-local, allowlisted HTTP observations; never prompt, body or credentials. */
export interface ReviewHttpFacts {
  status?: number;
  requestId?: string;
  retryAfterMs?: number;
  receivedAt?: number;
}
export interface HttpFactsSink { active: () => boolean; facts: ReviewHttpFacts }
const sinks = new AsyncLocalStorage<HttpFactsSink>();

export function currentReviewHttpSink(): HttpFactsSink | undefined { return sinks.getStore(); }

/** Keep the same sink around iterator creation, consumption and return. */
export async function* withReviewHttpFacts<T>(sink: HttpFactsSink, source: () => AsyncIterable<T>): AsyncGenerator<T> {
  const iterator = sinks.run(sink, () => source()[Symbol.asyncIterator]());
  try {
    while (true) {
      const item = await sinks.run(sink, () => iterator.next());
      if (item.done) return;
      if (sink.active()) yield item.value;
    }
  } finally { await sinks.run(sink, () => iterator.return?.()); }
}

/** Observe only a failed model response; successful responses do not erase failure facts. */
export function observeReviewResponse(sink: HttpFactsSink, status: number, headers: Record<string, string | string[] | undefined>): void {
  if (!sink.active() || status < 400) return;
  const get = (key: string) => { const value = headers[key]; return Array.isArray(value) ? value[0] : value; };
  const receivedAt = performance.now();
  const raw = get('retry-after');
  let retryAfterMs: number | undefined;
  if (raw !== undefined) {
    const seconds = /^\d+(?:\.\d+)?$/.test(raw.trim()) ? Number(raw) * 1000 : NaN;
    const delay = Number.isFinite(seconds) ? seconds : Date.parse(raw) - Date.now();
    if (Number.isFinite(delay) && delay >= 0) retryAfterMs = delay;
  }
  sink.facts = { status, receivedAt, ...(retryAfterMs !== undefined ? { retryAfterMs } : {}),
    requestId: get('request-id') ?? get('x-request-id') ?? get('anthropic-request-id') };
}
