import { randomUUID } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { LlmFailure } from '@deepseek-ai/dsh-llm';
import { RetryId } from '@deepseek-ai/dsh-llm-retry';

const initialDelayMs = 5000;
const maxDelayMs = 60000;
const policyKey = 'nano:model-connection';

function upstreamConnectionFailed(failure: LlmFailure): boolean {
  // The local Anthropic bridge answers with a typed 502 when it cannot dial its upstream.
  const prefix = '502 ';
  if (failure.code !== 'SERVER' || !failure.message.startsWith(prefix)) return false;
  try {
    const report = JSON.parse(failure.message.slice(prefix.length))?.error as { type?: unknown; message?: unknown } | undefined;
    return report?.type === 'upstream_connection_error' &&
      typeof report.message === 'string' && /^Connect(?:Error|Timeout):/.test(report.message);
  } catch {
    return false;
  }
}

/** Keep connection waits within the live DSH step, with a separate retry budget. */
export function attachModelConnectionRetry(agent: Agent, takeConnectionFailure: (signal: AbortSignal) => boolean): void {
  let state: { signal: AbortSignal; step: number; retryId: RetryId; retry: number; delayMs: number } | undefined;
  agent.ctx.on('agent/request-error', async ({ turn, step, provider, signal, failure }, next) => {
    if (!takeConnectionFailure(signal) && !upstreamConnectionFailed(failure)) return next();
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
