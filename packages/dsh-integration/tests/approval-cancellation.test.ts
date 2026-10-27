import { Context } from '@deepseek-ai/cordis';
import { expect, it } from 'vitest';
import { NanoApproval } from '../src/policy/approval.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

function deferred() { let resolve!: () => void; const promise = new Promise<void>(done => { resolve = done; }); return { promise, resolve }; }

it.each(['audit', 'preparation'] as const)('cancels without waiting for uncooperative %s and never publishes a late grant', async phase => {
  const ctx = new Context(); const entered = deferred(); const release = deferred();
  const controller = new AbortController(); let rows: any[] = []; let writes = Promise.resolve(); let updates = 0; let reviews = 0; let effects = 0;
  const table = { get: () => rows, update: (_id: string, update: (rows: any[]) => any[]) => {
    writes = writes.then(async () => { if (phase === 'audit' && updates++ === 0) { entered.resolve(); await release.promise; } rows = update(rows); });
    return writes;
  } };
  ctx.provide('storageDomain', { open: async () => ({ table: (name: string) => name === 'sessions' ? table : { get: () => undefined }, close: async () => {} }) } as any);
  ctx.provide('permissionPresets', { registerAuto: () => {} } as any);
  ctx.provide('nanoProduct', { call: async () => { entered.resolve(); await release.promise; return { original: 'owner evidence' }; } } as any);
  ctx.provide('ccApproval', { review: async () => { reviews++; return { decision: { behavior: 'allow', reason: 'authorized' } }; } } as any);
  const config: any = { agentId: 'a', revision: '1', mode: 'global', provider: 'fixture', model: 'review', personal: phase === 'preparation', approval: { ...approvalDefaults } };
  const service = new NanoApproval(ctx, () => config);
  const agent: any = { id: 'parent', session: { requestHeader: () => undefined, header: { origin: 'main' }, snapshotEvents: () => [] } };
  const exec: any = { agent, name: 'fixture_effect', arguments: { exact: 'action' }, callId: 'original-call', signal: controller.signal };
  try {
    const pending = ctx.waterfall('tools/pre-execute', exec, async () => ({ kind: 'allow' as const })).then(decision => { if (decision.kind === 'allow') effects++; return decision; });
    await entered.promise;
    controller.abort();
    // The storage/preparation gate remains unresolved until AFTER dispatch returns.
    expect(await pending).toEqual({ kind: 'cancel' });
    expect(effects).toBe(0);
    expect(reviews).toBe(phase === 'audit' ? 1 : 0);
    release.resolve();
    await new Promise(resolve => setTimeout(resolve, 10)); await writes;
    expect(await service.entries('parent')).toEqual([expect.objectContaining({ callId: 'original-call', source: 'classifier_cancel', decision: 'cancel', consecutive: 0, total: 0,
      retry: expect.objectContaining({ finalCategory: 'cancel', extraUsed: 0 }) })]);
    expect(effects).toBe(0);
    expect(reviews).toBe(phase === 'audit' ? 1 : 0);
  } finally { release.resolve(); await ctx.fiber.dispose(); }
}, 2000);
