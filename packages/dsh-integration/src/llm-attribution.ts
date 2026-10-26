/** Preserve Nano's proxy log grouping through the public LLM and HTTP seams. */
import { AsyncLocalStorage } from 'node:async_hooks';
import type { Context } from '@deepseek-ai/cordis';
import { getGlobalDispatcher, setGlobalDispatcher } from 'undici';
import { currentReviewHttpSink, observeReviewResponse } from './policy/review-http.js';

/** Install request-local transport attribution without changing native session identities. */
export function installLlmAttribution(ctx: Context, rootOf: (sessionId: string) => string): void {
  const attribution = new AsyncLocalStorage<{ sessionId: string; rootId: string }>();
  const previous = getGlobalDispatcher();
  const dispatcher = previous.compose(dispatch => (options, handler) => {
    const current = attribution.getStore();
    const sink = currentReviewHttpSink();
    // Only model protocol requests carry identity/facts, never tool/attachment HTTP.
    if ((!current && !sink) || options.method !== 'POST' || !/\/(messages|chat\/completions|responses)(?:\?|$)/.test(options.path))
      return dispatch(options, handler);
    const observed = sink ? new Proxy(handler, {
      get(target, key, receiver) {
        const value = Reflect.get(target, key, receiver);
        if (typeof value !== 'function') return value;
        if (key === 'onResponseStart') return (...args: unknown[]) => {
          observeReviewResponse(sink, args[1] as number, args[2] as Record<string, string | string[] | undefined>);
          return value.apply(target, args);
        };
        // Preserve old-style handlers too; do not introduce a new handler method/protocol.
        if (key === 'onHeaders') return (...args: unknown[]) => {
          const raw = args[1] as Buffer[]; const headers: Record<string, string> = {};
          for (let i = 0; i < raw.length; i += 2) headers[String(raw[i]).toLowerCase()] = String(raw[i + 1]);
          observeReviewResponse(sink, args[0] as number, headers);
          return value.apply(target, args);
        };
        return value.bind(target);
      },
    }) : handler;
    if (!current) return dispatch(options, observed);
    const original = options.headers;
    const entries: [string, string | number | string[] | undefined][] = Array.isArray(original)
      ? Array.from({ length: original.length / 2 }, (_, i) => [original[i * 2]!, original[i * 2 + 1]!])
      : original && Symbol.iterator in original ? [...original] : Object.entries(original ?? {});
    const headers = Object.fromEntries(entries.filter(([key]) => !['x-session-id', 'x-agent-session-id'].includes(key.toLowerCase())));
    headers['X-Session-Id'] = current.rootId;
    headers['X-Agent-Session-Id'] = current.sessionId;
    return dispatch({ ...options, headers }, observed);
  });
  setGlobalDispatcher(dispatcher);
  ctx.effect(() => () => {
    if (getGlobalDispatcher() === dispatcher) setGlobalDispatcher(previous);
  });
  ctx.on('llm/stream', async function* (options, next) {
    if (!options.sessionId) { yield* next(); return; }
    const identity = { sessionId: String(options.sessionId), rootId: rootOf(String(options.sessionId)) };
    const iterator = attribution.run(identity, () => next()[Symbol.asyncIterator]());
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
