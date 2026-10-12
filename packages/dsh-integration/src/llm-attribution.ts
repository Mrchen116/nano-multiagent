/** Preserve Nano's proxy log grouping through the public LLM and HTTP seams. */
import { AsyncLocalStorage } from 'node:async_hooks';
import type { Context } from '@deepseek-ai/cordis';
import { getGlobalDispatcher, setGlobalDispatcher } from 'undici';

/** Install request-local transport attribution without changing native session identities. */
export function installLlmAttribution(ctx: Context, rootOf: (sessionId: string) => string): void {
  const attribution = new AsyncLocalStorage<{ sessionId: string; rootId: string }>();
  const previous = getGlobalDispatcher();
  const dispatcher = previous.compose(dispatch => (options, handler) => {
    const current = attribution.getStore();
    // Only model protocol requests carry the identity, never unrelated tool/attachment HTTP.
    if (!current || options.method !== 'POST' || !/\/(messages|chat\/completions|responses)(?:\?|$)/.test(options.path))
      return dispatch(options, handler);
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
