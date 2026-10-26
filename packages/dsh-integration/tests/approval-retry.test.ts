import { expect, it } from 'vitest';
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
