import { expect, it } from 'vitest';
import { Context } from '@deepseek-ai/cordis';
import { NanoApproval } from '../src/policy/approval.js';
import type { ApprovalAudit } from '../src/policy/audit.js';
import { LlmError } from '@deepseek-ai/dsh-llm';
import { classify } from '../src/policy/classifier.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

it('recovers a CC stage-two service failure without replaying the valid first stage or executing a tool', async () => {
  const prompts: string[] = [];
  const ctx = { llm: {
    resolveModelInfo: async () => ({ context: { contextWindow: 100000 }, reasoning: { efforts: [{ id: 'high' }], defaultEffort: 'high' } }),
    stream: async function* (options: any) {
      prompts.push(options.messages[0].content[0].text);
      if (prompts.length === 2) throw new LlmError('temporary', 'SERVER', { status: 503 });
      yield { type: 'block-end', index: 0, block: { type: 'text', text: prompts.length === 1 ? '<block>yes</block><reason>needs second stage</reason>' : '<block>no</block>' } };
      yield { type: 'finish', reason: { kind: 'stop' } };
    },
  } };
  const result = await classify(ctx as any, {
    exec: { agent: { id: 'parent', session: { header: { cwd: '/tmp' } } }, signal: new AbortController().signal },
    config: { mode: 'global', approval: { ...approvalDefaults, rules: 'nano', globalRoot: '/tmp' } },
    sources: { transcript: async () => 'FROZEN_HUMAN_EVIDENCE' }, inherited: [], reviewer: { provider: 'fixture', model: 'review' },
  } as any);
  expect(result.decision.behavior).toBe('allow');
  expect(prompts).toHaveLength(3);
  expect(prompts[1]).toBe(prompts[2]);
  expect(prompts[0]).not.toBe(prompts[1]);
});

it.each(['allow','deny','unavailable'] as const)('fails closed on durable audit write failure after %s, without another review or effect', async verdict => {
  const ctx = new Context();let reviews = 0;let writes = 0;let durable: ApprovalAudit[] = [];
  const table = { get: () => durable, async update(_id:string, mutate:(rows:ApprovalAudit[])=>ApprovalAudit[]) { writes++;mutate(durable);throw new Error('controlled audit persistence failure'); } };
  ctx.provide('storageDomain',{open:async()=>({table:(name:string)=>name==='sessions'?table:{get:()=>undefined},close:async()=>{}})} as any);
  ctx.provide('permissionPresets',{registerAuto:()=>{}} as any);
  ctx.provide('codexApproval',{review:async()=>{reviews++;if(verdict==='unavailable')throw new LlmError('controlled unavailable','SERVER',{status:503});return{decision:{behavior:verdict,risk:'low',reason:'controlled'}};}} as any);
  const config={agentId:'a',revision:'1',mode:'single_thread',provider:'fixture',model:'main',approval:{...approvalDefaults,rules:'codex',unattendedFallback:'allow'}};
  new NanoApproval(ctx,()=>config as any);
  const agent={id:'parent',session:{header:{},requestHeader:()=>undefined,snapshotEvents:()=>[{type:'turn/start',seq:0},{type:'user/message',seq:1,data:{source:{kind:'schedule'}}}]}};
  try{
    let effects=0;
    await expect((async()=>{
      const decision=await ctx.waterfall('tools/pre-execute',{agent,callId:'audit-failed',name:'fixture_effect',arguments:{},signal:new AbortController().signal} as any,async()=>({kind:'allow'}));
      if(decision.kind==='allow')effects++;
    })()).rejects.toThrow('controlled audit persistence failure');
    expect([reviews,writes,effects]).toEqual([1,1,0]);expect(durable).toEqual([]);
  }finally{await ctx.fiber.dispose();}
});

it('persists concurrent deny traces with the route chosen by the atomic denial count', async () => {
  const ctx = new Context();
  let rows: ApprovalAudit[] = [];
  const table = {
    get: () => rows,
    async update(_id: string, mutate: (entries: ApprovalAudit[]) => ApprovalAudit[]) { rows = mutate(rows); },
  };
  ctx.provide('storageDomain', { open: async () => ({ table: (name: string) => name === 'sessions' ? table : { get: () => undefined }, close: async () => {} }) } as any);
  ctx.provide('permissionPresets', { registerAuto: () => {} } as any);
  ctx.provide('codexApproval', { review: async () => ({ decision: { behavior: 'deny', risk: 'low', reason: 'needs confirmation' } }) } as any);
  const config = { agentId: 'a', revision: '1', mode: 'single_thread', provider: 'fixture', model: 'main', approval: { ...approvalDefaults, rules: 'codex', denyLimit: 2, totalDenyLimit: 99 } };
  new NanoApproval(ctx, () => config as any);
  const agent = { id: 'parent', session: { header: {}, requestHeader: () => undefined, snapshotEvents: () => [
    { type: 'turn/start', seq: 0 },
    { type: 'user/message', seq: 1, data: { source: { kind: 'user', actorId: 'owner', channel: 'test', messageId: 'm' } } },
  ] } };
  try {
    // Exercise the public pre-execute chain, not private review/record methods.
    const decisions = await Promise.all(['A', 'B'].map(callId => ctx.waterfall('tools/pre-execute', {
      agent, callId, name: 'fixture_effect', arguments: {}, signal: new AbortController().signal,
    } as any, async () => ({ kind: 'allow' }))));
    expect(decisions.map(decision => decision.kind)).toEqual(['deny', 'ask']);
    expect(rows.map(row => [row.callId, row.consecutive, row.recovery?.finalRoute])).toEqual([
      ['A', 1, 'deny'], ['B', 2, 'interactive_pending'],
    ]);
    expect(rows.every(row => row.recovery?.complete && row.recovery.retriesUsed === 0)).toBe(true);
  } finally { await ctx.fiber.dispose(); }
});
