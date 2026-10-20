import { Context } from '@deepseek-ai/cordis';
import { LlmError } from '@deepseek-ai/dsh-llm';
import { expect, it, vi } from 'vitest';
import { CodexApproval } from '../src/policy/codex.js';
import { ReviewRecovery, type ReviewTrace } from '../src/policy/recovery.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';
import type { ApprovalReviewRequest } from '../src/policy/types.js';

function deferred<T = void>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => resolve = done); return { promise, resolve }; }
function harness(run: (turn: { events: any[]; input: string; cancelled: Promise<void> }) => Promise<void>, options: { lateCreate?: Promise<void>; lateDispose?: Promise<void> | ((id: string) => Promise<void>) } = {}) {
  const ctx = new Context(); const disposed: string[] = []; const inputs: string[] = []; let rows: any[] = [{ user: 'original permission', origin: { kind: 'human' } }];
  ctx.provide('llm', { resolveModelInfo: async () => ({ context: { contextWindow: 100000 } }) } as any);
  ctx.provide('tools', { schemas: () => [{ name: 'edit', parameters: { type: 'object' } }] } as any);
  ctx.provide('agents', { create: async (options_: any) => {
    const events: any[] = [...(options_.seed ?? [])]; const cancelled = deferred(); let pending = Promise.resolve();
    const agent = { id: options_.sessionId, session: { snapshotEvents: () => events, deriveMessages: () => events.filter(e => e.type === 'user/message').map(e => e.data) },
      followup(message: any) { inputs.push(message.content[0].text); events.push({ type: 'user/message', seq: events.length, data: message }); pending = run({ events, input: message.content[0].text, cancelled: cancelled.promise }); },
      whenIdle: () => pending, cancel: () => cancelled.resolve() };
    if (options.lateCreate) await options.lateCreate;
    return { agent, dispose: async () => { cancelled.resolve(); await pending.catch(() => {}); if (options.lateDispose) await (typeof options.lateDispose === 'function' ? options.lateDispose(agent.id) : options.lateDispose); disposed.push(agent.id); } };
  } } as any);
  const plugin = new CodexApproval(ctx);
  const controller = new AbortController(); const traces: ReviewTrace[] = [];
  const request = { exec: { agent: { id: 'parent', session: { header: { cwd: '/tmp' } } }, callId: 'pending', name: 'edit', arguments: { path: 'a', text: 'complete' }, signal: controller.signal }, config: { agentId: 'a', revision: '1', approval: { ...approvalDefaults, rules: 'codex' } }, reviewer: { provider: 'fixture', model: 'fixture' }, sources: { history: async () => rows, restoreEntries: (r: any) => r }, inherited: [] } as unknown as ApprovalReviewRequest;
  const review = async () => {
    const recovery = new ReviewRecovery(controller.signal, 'pending', 'codex', request.reviewer);
    try { return await plugin.review({ ...request, recovery }); }
    finally { traces.push(recovery.finish('test', 'test')); }
  };
  return { plugin, request, review, traces, controller, disposed, inputs, setRows: (next: any[]) => rows = next, close: () => ctx.fiber.dispose() };
}
function verdict(events: any[]) {
  events.push({ type: 'assistant/message', seq: events.length, data: { message: { content: [{ type: 'text', text: '{"outcome":"allow"}' }] } } });
  events.push({ type: 'turn/end', seq: events.length, data: { reason: { kind: 'completed' } } });
}
const overflow = () => new LlmError('context too large', 'CONTEXT_WINDOW_EXCEEDED');

it('rebuilds rewritten evidence and changed configuration without retaining old authorization', async () => {
  const h = harness(async ({ events }) => verdict(events));
  try {
    const first = await h.review(); expect(first.metadata?.contextMode).toBe('full');
    h.setRows([{ user: 'new instruction only', origin: { kind: 'human' } }]);
    const changed = await h.review(); expect(changed.metadata?.sessionId).not.toBe(first.metadata?.sessionId); expect(h.inputs.at(-1)).not.toContain('original permission');
    h.request.config = { ...h.request.config, revision: '2' };
    const configured = await h.review(); expect(configured.metadata?.sessionId).not.toBe(changed.metadata?.sessionId);
    expect(h.disposed).toContain(first.metadata!.sessionId); expect(h.disposed).toContain(changed.metadata!.sessionId);
    await h.plugin.release('parent'); expect(h.disposed).toContain(configured.metadata!.sessionId);
    expect((await h.review()).metadata?.contextMode).toBe('full');
  } finally { await h.close(); }
});

it('replays frozen full evidence after structured overflow and commits only the successful rebuild', async () => {
  let calls = 0; const h = harness(async ({ events }) => { if (++calls === 2) throw overflow(); verdict(events); });
  try {
    await h.review(); h.setRows([{ user: 'original permission', origin: { kind: 'human' } }, { tool_result: 'new evidence' }]);
    const result = await h.review(); expect(result.metadata?.contextMode).toBe('rebuild');
    expect(h.inputs[1]).not.toContain('original permission'); expect(h.inputs[2]).toContain('original permission'); expect(h.inputs[2]).toContain('new evidence');
    expect(h.traces[1]).toMatchObject({ contextRebuilds: 1, retriesUsed: 0 });
    expect((await h.review()).metadata?.sessionId).toBe(result.metadata?.sessionId);
  } finally { await h.close(); }
});

it('keeps the action context allowance across context rebuild → 503 → new full → overflow', async () => {
  vi.useFakeTimers(); let calls = 0;
  const h = harness(async () => { if (++calls === 2) throw new LlmError('overload', 'SERVER', { status: 503 }); throw overflow(); });
  try {
    const pending = h.review(); const rejected = expect(pending).rejects.toMatchObject({ category: 'context' });
    await vi.advanceTimersByTimeAsync(1100); await rejected;
    expect(calls).toBe(3); expect(h.disposed).toHaveLength(3);
    expect(h.traces[0]).toMatchObject({ contextRebuilds: 1, retriesUsed: 1 });
    expect(h.inputs.every(input => input.includes('original permission'))).toBe(true);
  } finally { await h.close(); vi.useRealTimers(); }
});

it('cancels a context rebuild without accepting late grants or retrying', async () => {
  const retry = deferred(); let calls = 0;
  const h = harness(async ({ events, cancelled }) => { if (++calls === 1) throw overflow(); retry.resolve(); await cancelled; verdict(events); });
  try {
    const pending = h.review(); const rejected = expect(pending).rejects.toThrow();
    await retry.promise; h.controller.abort(); await rejected;
    expect(h.disposed).toHaveLength(2); expect(h.traces[0]?.retriesUsed).toBe(0);
  } finally { await h.close(); }
});

it('cleans late creation without followup and quarantines the parent until that handle is gone', async () => {
  vi.useFakeTimers(); const create = deferred();
  const h = harness(async ({ events }) => verdict(events), { lateCreate: create.promise });
  try {
    const pending = h.review(); const rejected = expect(pending).rejects.toMatchObject({ category: 'cleanup_unavailable' });
    await vi.advanceTimersByTimeAsync(95_000); await rejected;
    await expect(h.review()).rejects.toMatchObject({ category: 'cleanup_unavailable' });
    create.resolve(); await vi.advanceTimersByTimeAsync(0);
    expect(h.inputs).toHaveLength(0); expect(h.disposed).toHaveLength(1);
    expect((await h.review()).decision.behavior).toBe('allow');
  } finally { create.resolve(); await h.close(); vi.useRealTimers(); }
});

it('retains parent quarantine until every concurrent failed branch has actually drained', async () => {
  vi.useFakeTimers(); const first = deferred(); const second = deferred(); let disposals = 0; let calls = 0;
  const gates = [first.promise, second.promise];
  const h = harness(async ({ events }) => { if (++calls <= 2) throw new LlmError('overload', 'SERVER', { status: 503 }); verdict(events); }, { lateDispose: async () => { await gates[disposals++]; } });
  try {
    const a = h.review(); const b = h.review();
    const rejected = Promise.all([expect(a).rejects.toMatchObject({ category: 'cleanup_unavailable' }), expect(b).rejects.toMatchObject({ category: 'cleanup_unavailable' })]);
    await vi.waitFor(() => expect(disposals).toBe(2)); await vi.advanceTimersByTimeAsync(5000); await rejected;
    first.resolve(); await vi.advanceTimersByTimeAsync(0);
    await expect(h.review()).rejects.toMatchObject({ category: 'cleanup_unavailable' });
    second.resolve(); await vi.advanceTimersByTimeAsync(0);
    expect((await h.review()).decision.behavior).toBe('allow');
  } finally { first.resolve(); second.resolve(); await h.close(); vi.useRealTimers(); }
});

it('quarantines a slow dispose, blocks new reviewers, then releases only after actual drain', async () => {
  vi.useFakeTimers(); const drain = deferred(); let count = 0;
  const h = harness(async ({ events }) => { if (++count === 1) throw new LlmError('overload', 'SERVER', { status: 503 }); verdict(events); }, { lateDispose: drain.promise });
  try {
    const pending = h.review(); const rejected = expect(pending).rejects.toMatchObject({ category: 'cleanup_unavailable' });
    await vi.advanceTimersByTimeAsync(5000); await rejected;
    await expect(h.review()).rejects.toMatchObject({ category: 'cleanup_unavailable' });
    expect(count).toBe(1); drain.resolve(); await vi.advanceTimersByTimeAsync(0);
    expect((await h.review()).decision.behavior).toBe('allow');
  } finally { drain.resolve(); await h.close(); vi.useRealTimers(); }
});
