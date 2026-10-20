import { Context } from '@deepseek-ai/cordis';
import { LlmError } from '@deepseek-ai/dsh-llm';
import { afterEach, expect, it, vi } from 'vitest';
import { approvalDefaults } from '../../product-contracts/src/approval.js';
import { NanoApproval } from '../src/policy/approval.js';
import { approvalDomain, type ApprovalAudit } from '../src/policy/audit.js';
import { ReviewRecovery } from '../src/policy/recovery.js';

function harness(mode: string, source: object, fallback: string, origin?: string, failStorage = false) {
  const ctx = new Context(); const rows: ApprovalAudit[] = []; const parent = new AbortController(); let requests = 0;
  const config = { agentId: 'a', revision: '1', provider: 'fixture', model: 'main', mode, approval: { ...approvalDefaults, rules: 'nano', unattendedFallback: fallback } };
  const agent = { id: 'parent', session: { header: { cwd: '/tmp', origin }, requestHeader: () => undefined, snapshotEvents: () => [{ seq: 0, type: 'turn/start' }, { seq: 1, type: 'user/message', data: { source } }] } };
  ctx.provide('storageDomain', { open: async () => ({ close: async () => {}, table: (name: string) => ({ get: () => name === 'sessions' ? rows : undefined, update: async (_id: string, update: any) => { if (failStorage) throw new Error('disk unavailable'); const result = update(rows); rows.splice(0, rows.length, ...approvalDomain.tables.sessions.valueSchema.parse(result)); } }) }) } as any);
  ctx.provide('permissionPresets', { registerAuto: () => {} } as any);
  ctx.provide('ccApproval', { exempt: async () => false, review: async (request: any) => request.recovery.run('cc-s1', 30_000, async () => { requests++; throw new LlmError('fixture', 'SERVER', { status: 503 }); }) } as any);
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

it('reads unchanged version-one audit rows and accepts optional recovery without migration', () => {
  const old = { time: 1, callId: 'old', tool: 'bash', source: 'classifier_allow', decision: 'allow', reason: '', consecutive: 0, total: 0 };
  const recovery = new ReviewRecovery(new AbortController().signal, 'new', 'nano', { provider: 'fixture', model: 'review' });
  expect(approvalDomain.version).toBe(1); expect(approvalDomain.layout).toBe('per-record');
  expect(approvalDomain.tables.sessions.valueSchema.parse([old, { ...old, recovery: recovery.finish('unknown', 'deny') }])).toHaveLength(2);
});
