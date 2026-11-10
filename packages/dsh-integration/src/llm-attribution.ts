/** Preserve proxy log grouping and capture model connection failures before adapter normalization. */
import { AsyncLocalStorage } from 'node:async_hooks';
import type { Context } from '@deepseek-ai/cordis';
import { isAgentLoopRequest } from '@deepseek-ai/dsh-llm';
import { DecoratorHandler, getGlobalDispatcher, setGlobalDispatcher, type Dispatcher } from 'undici';

const connectionCodes = new Set([
  'EAI_AGAIN', 'ENOTFOUND', 'ECONNREFUSED', 'EHOSTDOWN', 'EHOSTUNREACH',
  'ENETDOWN', 'ENETUNREACH', 'EADDRNOTAVAIL', 'UND_ERR_CONNECT_TIMEOUT',
]);

/** Install model HTTP attribution and return a single-use connection failure check for the native turn. */
export function installLlmAttribution(ctx: Context, rootOf: (sessionId: string) => string): (signal: AbortSignal) => boolean {
  const attribution = new AsyncLocalStorage<{ sessionId: string; rootId: string; connectionFailed?: boolean }>();
  const connectionFailures = new WeakSet<AbortSignal>();
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
    const attributed = { ...options, headers };
    if (current.connectionFailed === undefined) return dispatch(attributed, handler);
    // pi-ai flattens establishment errors and broken response streams into TRANSPORT.
    current.connectionFailed = false;
    const observed = new DecoratorHandler(handler);
    return dispatch(attributed, Object.assign(observed, {
      onResponseError(controller: Dispatcher.DispatchController, error: NodeJS.ErrnoException) {
        current.connectionFailed = connectionCodes.has(error.code ?? '') ||
          (error.syscall === 'connect' && error.code === 'ETIMEDOUT') ||
          (error.code === 'ECONNRESET' &&
            error.message === 'Client network socket disconnected before secure TLS connection was established');
        handler.onResponseError?.(controller, error);
      },
    }));
  });
  setGlobalDispatcher(dispatcher);
  ctx.effect(() => () => {
    if (getGlobalDispatcher() === dispatcher) setGlobalDispatcher(previous);
  });
  ctx.on('llm/stream', async function* (options, next) {
    if (!options.sessionId) { yield* next(); return; }
    const signal = isAgentLoopRequest(options) ? options.signal : undefined;
    if (signal) connectionFailures.delete(signal);
    const identity = { sessionId: String(options.sessionId), rootId: rootOf(String(options.sessionId)), connectionFailed: signal ? false : undefined };
    const iterator = attribution.run(identity, () => next()[Symbol.asyncIterator]());
    try {
      while (true) {
        const item = await attribution.run(identity, () => iterator.next());
        if (item.done) return;
        if (signal && identity.connectionFailed && item.value.type === 'finish' &&
            item.value.reason.kind === 'error' && item.value.reason.failure.status === undefined) {
          connectionFailures.add(signal);
        }
        yield item.value;
      }
    } finally {
      await attribution.run(identity, () => iterator.return?.());
    }
  }, { prepend: true });
  return signal => connectionFailures.delete(signal);
}
