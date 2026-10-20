/** Preserve Nano's proxy log grouping through the public LLM and HTTP seams. */
import { AsyncLocalStorage } from 'node:async_hooks';
import type { Context } from '@deepseek-ai/cordis';
import { getGlobalDispatcher, setGlobalDispatcher } from 'undici';
import type { GenerateOptions, StreamChunk } from '@deepseek-ai/dsh-llm';

/** Response facts belong to one model request, never a parent/root or cached reviewer. */
export interface HttpFactsSink { active: boolean; status?: number; requestId?: string; retryAfterUntil?: number }
const reviewHttp = new AsyncLocalStorage<HttpFactsSink>();

/** Carry a fixed sink through iterator creation, next and return without retaining a prompt. */
export async function* withReviewHttpFacts<T>(sink: HttpFactsSink, next: () => AsyncIterable<T>): AsyncGenerator<T> {
  const iterator = reviewHttp.run(sink, () => next()[Symbol.asyncIterator]());
  try {
    for (;;) {
      const item = await reviewHttp.run(sink, () => iterator.next());
      if (item.done) return;
      yield item.value;
    }
  } finally { await reviewHttp.run(sink, () => iterator.return?.()); }
}

function observe(sink: HttpFactsSink, status: number, headers: Record<string, string | string[] | undefined>): void {
  if (!sink.active || status < 400 && sink.status !== undefined && sink.status >= 400) return;
  sink.status = status;
  const header = (key: string) => { const value = headers[key]; return Array.isArray(value) ? value[0] : value; };
  sink.requestId = (header('request-id') ?? header('x-request-id') ?? header('anthropic-request-id'))?.slice(0, 256);
  const raw = header('retry-after');
  let duration: number | undefined;
  if (raw && /^\d+(?:\.\d+)?$/.test(raw.trim())) duration = Number(raw) * 1000;
  else if (raw) { const date = Date.parse(raw); if (Number.isFinite(date) && date > Date.now()) duration = date - Date.now(); }
  sink.retryAfterUntil = duration !== undefined && Number.isFinite(duration) && duration >= 0 ? performance.now() + duration : undefined;
}

/** Install request-local transport attribution without changing native session identities. */
export function installLlmAttribution(ctx: Context, rootOf: (sessionId: string) => string,
  wrap: (options: GenerateOptions, next: () => AsyncIterable<StreamChunk>) => AsyncIterable<StreamChunk> = (_options, next) => next()): void {
  const attribution = new AsyncLocalStorage<{ sessionId: string; rootId: string }>();
  const previous = getGlobalDispatcher();
  const dispatcher = previous.compose(dispatch => (options, handler) => {
    const current = attribution.getStore();
    const sink = reviewHttp.getStore();
    // Only model POSTs are observed; never read response bodies, URLs or credentials.
    if (options.method !== 'POST' || !/\/(messages|chat\/completions|responses)(?:\?|$)/.test(options.path)) return dispatch(options, handler);
    if (sink?.active) {
      const originalHandler = handler;
      handler = new Proxy(originalHandler, { get(target, key) {
        const value = Reflect.get(target, key, target);
        if (key === 'onResponseStart') return function(...args: Parameters<NonNullable<typeof target.onResponseStart>>) {
          observe(sink, args[1], args[2]);
          return value?.apply(target, args);
        };
        return typeof value === 'function' ? value.bind(target) : value;
      } });
    }
    if (!current) return dispatch(options, handler);
    const original = options.headers;
    const entries: [string, string | number | string[] | undefined][] = Array.isArray(original)
      ? Array.from({ length: original.length / 2 }, (_, i) => [original[i * 2]!, original[i * 2 + 1]!])
      : original && Symbol.iterator in original ? [...original] : Object.entries(original ?? {});
    const headers = Object.fromEntries(entries.filter(([key]) => !['x-session-id', 'x-agent-session-id'].includes(key.toLowerCase())));
    headers['X-Session-Id'] = current.rootId;
    headers['X-Agent-Session-Id'] = current.sessionId;
    return dispatch({ ...options, headers }, handler);
  });
  setGlobalDispatcher(dispatcher);
  ctx.effect(() => () => {
    if (getGlobalDispatcher() === dispatcher) setGlobalDispatcher(previous);
  });
  ctx.on('llm/stream', async function* (options, next) {
    if (!options.sessionId) { yield* wrap(options, next); return; }
    const identity = { sessionId: String(options.sessionId), rootId: rootOf(String(options.sessionId)) };
    const iterator = attribution.run(identity, () => wrap(options, next)[Symbol.asyncIterator]());
    try {
      while (true) {
        const item = await attribution.run(identity, () => iterator.next());
        if (item.done) return;
        yield item.value;
      }
    } finally {
      await attribution.run(identity, () => iterator.return?.());
    }
  }, { prepend: true });
}
