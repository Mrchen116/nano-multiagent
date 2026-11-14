import { randomUUID } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { LlmFailure } from '@deepseek-ai/dsh-llm';
import { RetryId } from '@deepseek-ai/dsh-llm-retry';

const initialDelayMs = 5000;
const maxDelayMs = 60000;
const policyKey = 'nano:model-connection';

function upstreamConnectionFailed(failure: LlmFailure): boolean {
  // The adapter preserves the bridge's typed 502 in different envelopes across wire APIs.
  if (failure.code !== 'SERVER') return false;
  const body = /^(?:502:? |[^\n]+ API error \(502\): )(\{.*\})$/s.exec(failure.message)?.[1];
  if (!body) return false;
  try {
    const value = JSON.parse(body);
    const report = (value?.error ?? value) as { type?: unknown; message?: unknown } | undefined;
    return report?.type === 'upstream_connection_error' &&
      typeof report.message === 'string' && /^Connect(?:Error|Timeout):/.test(report.message);
  } catch {
    return false;
  }
}

/** Keep network recovery waits within the live DSH step, with a separate retry budget. */
export function attachModelConnectionRetry(agent: Agent, takeConnectionFailure: (signal: AbortSignal) => boolean,
  canSwitchAfterFailure: (turn: number, signal: AbortSignal) => Promise<boolean> = async () => false): void {
  let state: { signal: AbortSignal; step: number; retryId: RetryId; retry: number; delayMs: number } | undefined;
  agent.ctx.on('agent/request-error', async ({ turn, step, provider, signal, failure }, next) => {
    const connectionFailed = takeConnectionFailure(signal);
    // Sleep can leave a request silent until its watchdog expires without a socket error.
    const timedOut = failure.code === 'TIMEOUT' && failure.status === undefined &&
      /^pi-ai stream idle timeout after \d+ms$/.test(failure.message);
    if (!connectionFailed && !timedOut && !upstreamConnectionFailed(failure)) return next();
    if (!connectionFailed && timedOut && await canSwitchAfterFailure(turn, signal)) return next();
    signal.throwIfAborted();
    if (state?.signal !== signal || state.step !== step) {
      state = { signal, step, retryId: RetryId(randomUUID()), retry: 0, delayMs: initialDelayMs };
    }
    const { retryId, delayMs } = state;
    const retry = ++state.retry;
    agent.session.append('llm/retry', { retryId, turn, step, provider, mode: 'always', policyKey, retry, delayMs, failure });
    await delay(delayMs, undefined, { signal });
    agent.session.append('llm/retry-started', { retryId, turn, step, retry });
    state.delayMs = Math.min(delayMs * 2, maxDelayMs);
    return { kind: 'retry' };
  }, { prepend: true });
}
