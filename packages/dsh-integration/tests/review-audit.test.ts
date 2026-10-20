import { Context } from '@deepseek-ai/cordis';
import { LlmError } from '@deepseek-ai/dsh-llm';
import { afterEach, expect, it, vi } from 'vitest';
import { approvalDefaults } from '../../product-contracts/src/approval.js';
import { NanoApproval } from '../src/policy/approval.js';
import { approvalDomain, type ApprovalAudit } from '../src/policy/audit.js';
import { ReviewRecovery } from '../src/policy/recovery.js';

interface HarnessOptions {
  verdict?: 'allow' | 'deny'; denyLimit?: number;
  onPersist?: (ordinal: number, phase: 'before' | 'after') => Promise<void>;
  failStorageAt?: number;
}
function harness(mode: string, source: object, fallback: string, origin?: string, failStorage = false, options: HarnessOptions = {}) {
  const ctx = new Context(); const rows: ApprovalAudit[] = []; const parent = new AbortController(); let requests = 0; let writes = 0;
  const config = { agentId: 'a', revision: '1', provider: 'fixture', model: 'main', mode, approval: { ...approvalDefaults, rules: 'nano', unattendedFallback: fallback, ...(options.denyLimit ? { denyLimit: options.denyLimit } : {}) } };
  const agent = { id: 'parent', session: { header: { cwd: '/tmp', origin }, requestHeader: () => undefined, snapshotEvents: () => [{ seq: 0, type: 'turn/start' }, { seq: 1, type: 'user/message', data: { source } }] } };
  ctx.provide('storageDomain', { open: async () => ({ close: async () => {}, table: (name: string) => ({ get: () => name === 'sessions' ? rows : undefined, update: async (_id: string, update: any) => {
    const ordinal = ++writes;
    if (failStorage || options.failStorageAt === ordinal) throw new Error('disk unavailable');
    const result = approvalDomain.tables.sessions.valueSchema.parse(update(rows));
    await options.onPersist?.(ordinal, 'before');
    rows.splice(0, rows.length, ...result);
    await options.onPersist?.(ordinal, 'after');
  } }) }) } as any);
  ctx.provide('permissionPresets', { registerAuto: () => {} } as any);
  ctx.provide('ccApproval', { exempt: async () => false, review: async (request: any) => request.recovery.run('cc-s1', 30_000, async () => {
    requests++;
    if (options.verdict) {
      request.recovery.trace.knownUsage.push({ inputTokens: 7, outputTokens: 3 }); // Explicit fixture usage, not provider evidence.
      return { decision: { behavior: options.verdict, risk: 'low', reason: 'fixture verdict' } };
    }
    throw new LlmError('fixture', 'SERVER', { status: 503 });
  }) } as any);
  const plugin = new NanoApproval(ctx, () => config as any);
  const review = () => (plugin as any).review({ agent, name: 'bash', callId: 'action', arguments: { command: 'one fixture operation' }, signal: parent.signal }, async () => ({ kind: 'allow' }));
  return { rows, parent, review, requests: () => requests, close: () => ctx.fiber.dispose() };
}
afterEach(() => vi.useRealTimers());

it.each([
  ['single_thread', { kind: 'nano-human' }, 'deny', undefined, 'ask', 'interactive_pending'],
  ['global', { kind: 'nano-human' }, 'allow', undefined, 'deny', 'return_to_agent'],
  ['single_thread', { kind: 'agent-message' }, 'allow', 'subagent', 'deny', 'return_to_agent'],
  ['single_thread', { kind: 'schedule' }, 'allow', undefined, 'allow', 'unattended'],
  ['single_thread', { kind: 'schedule' }, 'deny', undefined, 'deny', 'unattended'],
  ['global', { kind: 'nano-system', channel: 'heartbeat' }, 'allow', undefined, 'allow', 'unattended'],
  ['global', { kind: 'nano-system', channel: 'heartbeat' }, 'deny', undefined, 'deny', 'unattended'],
])('preserves %s/%j old fallback %s only after the durable terminal trace', async (mode, source, fallback, origin, outcome, route) => {
  vi.useFakeTimers(); const h = harness(mode as string, source as object, fallback as string, origin as string | undefined);
  try {
    const pending = h.review(); await vi.advanceTimersByTimeAsync(2000);
    expect(await pending).toMatchObject({ kind: outcome }); expect(h.requests()).toBe(3);
    expect(h.rows[0]).toMatchObject({ decision: 'no_verdict', consecutive: 0, total: 0, recovery: { retriesUsed: 2, finalRoute: route, complete: true } });
    if (outcome !== 'ask') {
      expect(h.rows[1]?.reviewId).toBe(h.rows[0]!.recovery!.reviewId);
      expect(h.rows[1]?.recovery).toBeUndefined(); expect(h.rows[1]?.usage).toBeUndefined();
    }
  } finally { await h.close(); }
});

it('storage failure never becomes the configured unattended allow', async () => {
  vi.useFakeTimers(); const h = harness('global', { kind: 'schedule' }, 'allow', undefined, true);
  try {
    const pending = h.review(); const rejected = expect(pending).rejects.toThrow('disk unavailable');
    await vi.advanceTimersByTimeAsync(2000); await rejected; expect(h.rows).toEqual([]);
  } finally { await h.close(); }
});

it('cancellation during backoff records one cancellation and cannot fall back allow', async () => {
  vi.useFakeTimers(); const h = harness('global', { kind: 'schedule' }, 'allow');
  try {
    const pending = h.review(); await vi.advanceTimersByTimeAsync(100); h.parent.abort();
    await vi.advanceTimersByTimeAsync(2000);
    expect(await pending).toEqual({ kind: 'cancel' }); expect(h.requests()).toBe(1);
    expect(h.rows).toHaveLength(1); expect(h.rows[0]).toMatchObject({ decision: 'cancelled', consecutive: 0, total: 0, recovery: { finalRoute: 'cancel' } });
  } finally { await h.close(); }
});

const persistenceCases = [
  { name: 'model allow', verdict: 'allow', at: 1, mode: 'global', source: { kind: 'nano-human' }, fallback: 'deny' },
  { name: 'model deny', verdict: 'deny', at: 1, mode: 'global', source: { kind: 'nano-human' }, fallback: 'deny' },
  { name: 'unavailable before unattended allow', at: 1, mode: 'global', source: { kind: 'schedule' }, fallback: 'allow' },
  { name: 'unavailable before interactive ask', at: 1, mode: 'single_thread', source: { kind: 'nano-human' }, fallback: 'deny' },
  { name: 'unattended fallback allow', at: 2, mode: 'global', source: { kind: 'schedule' }, fallback: 'allow' },
  { name: 'unattended fallback deny', at: 2, mode: 'global', source: { kind: 'schedule' }, fallback: 'deny' },
  { name: 'Global return to agent', at: 2, mode: 'global', source: { kind: 'nano-human' }, fallback: 'allow' },
  { name: 'denial escalation fallback', verdict: 'deny', denyLimit: 1, at: 2, mode: 'global', source: { kind: 'schedule' }, fallback: 'allow' },
] as const;

for (const phase of ['before', 'after'] as const) it.each(persistenceCases)(`records final cancellation when $name is paused ${phase} its durable write`, async spec => {
  vi.useFakeTimers();
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
  let entered = false; let settled = false; let effects = 0;
  const h = harness(spec.mode, spec.source, spec.fallback, undefined, false, {
    verdict: 'verdict' in spec ? spec.verdict : undefined,
    denyLimit: 'denyLimit' in spec ? spec.denyLimit : undefined,
    onPersist: async (ordinal, currentPhase) => { if (ordinal === spec.at && currentPhase === phase) { entered = true; await gate; } },
  });
  try {
    const pending = h.review().then(result => { settled = true; if (result.kind === 'allow') effects++; return result; });
    await vi.advanceTimersByTimeAsync(2000);
    expect(entered).toBe(true); expect(settled).toBe(false);
    // The real parent AbortSignal crosses an outstanding storage promise, not a pre-review abort.
    h.parent.abort(); release();
    expect(await pending).toEqual({ kind: 'cancel' }); expect(effects).toBe(0);
    const original = h.rows.find(row => row.recovery)!;
    expect(original.decision).toBe('verdict' in spec ? spec.verdict : 'no_verdict');
    expect(original.recovery).toMatchObject({ complete: true, terminalReason: 'cancelled', finalRoute: 'cancel' });
    expect(original.recovery!.fallbackOutcome).toBeUndefined();
    expect(original.recovery!.knownUsage).toEqual('verdict' in spec ? [{ inputTokens: 7, outputTokens: 3 }] : []);
    const terminal = h.rows.at(-1)!;
    expect(terminal).toMatchObject({ source: 'review_cancelled', decision: 'cancelled', reviewId: original.recovery!.reviewId });
    expect(terminal.recovery).toBeUndefined(); expect(terminal.usage).toBeUndefined();
    expect(h.rows.filter(row => row.recovery)).toHaveLength(1);
    expect(h.rows.filter(row => row.decision === 'cancelled')).toHaveLength(1);
    const previous = h.rows.at(-2)!;
    expect([terminal.consecutive, terminal.total]).toEqual([previous.consecutive, previous.total]);
    if (spec.at === 1) expect(h.rows).toHaveLength(2); // Cancellation cannot enter fallback.
  } finally { release(); await h.close(); }
});

it('rejects instead of allowing when the cancellation-terminal write fails after model persistence', async () => {
  vi.useFakeTimers(); let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; }); let entered = false;
  const h = harness('global', { kind: 'schedule' }, 'allow', undefined, false, {
    verdict: 'allow', failStorageAt: 2,
    onPersist: async (ordinal, phase) => { if (ordinal === 1 && phase === 'after') { entered = true; await gate; } },
  });
  try {
    const pending = h.review(); await vi.advanceTimersByTimeAsync(0); expect(entered).toBe(true);
    const rejected = expect(pending).rejects.toThrow('disk unavailable'); h.parent.abort(); release(); await rejected;
    expect(h.rows).toHaveLength(1); expect(h.rows[0]!.decision).toBe('allow');
  } finally { release(); await h.close(); }
});

it('reads unchanged version-one audit rows and accepts optional recovery without migration', () => {
  const old = { time: 1, callId: 'old', tool: 'bash', source: 'classifier_allow', decision: 'allow', reason: '', consecutive: 0, total: 0 };
  const recovery = new ReviewRecovery(new AbortController().signal, 'new', 'nano', { provider: 'fixture', model: 'review' });
  expect(approvalDomain.version).toBe(1); expect(approvalDomain.layout).toBe('per-record');
  expect(approvalDomain.tables.sessions.valueSchema.parse([old, { ...old, recovery: recovery.finish('unknown', 'deny') }])).toHaveLength(2);
});
