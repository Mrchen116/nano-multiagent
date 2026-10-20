import { Context } from '@deepseek-ai/cordis';
import { LlmError } from '@deepseek-ai/dsh-llm';
import { expect, it, vi } from 'vitest';
import { approvalDefaults } from '../../product-contracts/src/approval.js';
import { classify } from '../src/policy/classifier.js';
import { CodexApproval } from '../src/policy/codex.js';
import { ApprovalSources, codexEntries } from '../src/policy/sources.js';
import { ReviewRecovery } from '../src/policy/recovery.js';
import type { ApprovalReviewRequest } from '../src/policy/types.js';

for (const policy of ['nano', 'codex'] as const) for (const restored of [false, true]) {
  it(`${policy} freezes normalized ${restored ? 'cross-epoch restored' : 'same-epoch live'} evidence across 503 without resurrecting omitted parent history`, async () => {
    vi.useFakeTimers();
    const sources = new ApprovalSources();
    const message = { id: 'permission', sender: { type: 'user', id: 'owner', is_owner: true }, reply_to: 'sent-1', content: [{ type: 'text', text: 'Only the public draft' }] };
    const inbox = { target: 'group', conversation_type: 'group', delivery: 'participant', next_cursor: 'page-2', messages: [message] };
    const inherited = sources.restoreEntries([
      { id: 'inbox-live', tool_result: JSON.stringify(inbox), outcome: 'ok' },
      { id: 'inbox-live', inbox_result: inbox, observation: 'live' },
      { id: 'inbox-legacy-live', name: 'inbox', host_context_live: JSON.stringify({ ...inbox, messages: [{ ...message, id: 'legacy' }] }) },
      { id: 'inbox-restored', inbox_result: { ...inbox, messages: [{ ...message, id: 'restored' }] }, observation: 'restored' },
      { id: 'distinct-call', tool_result: 'DISTINCT_RETAINED_RESULT', outcome: 'ok' },
    ], restored);
    const snapshot = structuredClone(inherited);
    const inputs: string[] = []; let requests = 0;
    let effective = [{ id: 'human', role: 'user', content: [{ type: 'text', text: 'Effective compressed summary only' }], source: { kind: 'nano-human' } }];
    const agent = { id: 'parent', session: { id: 'parent', header: { cwd: '/tmp' }, isOwnSeq: () => true, snapshotEvents: () => [], deriveMessages: () => effective } };
    const mutateAfterFailure = () => {
      inherited.length = 0;
      effective = [{ ...effective[0]!, content: [{ type: 'text', text: 'LATE_REINTRODUCED_OLD_AUTHORIZATION' }] }];
    };
    const ctx = new Context();
    ctx.provide('llm', {
      resolveModelInfo: async () => ({ context: { contextWindow: 100000 } }),
      stream: async function* (options: any) {
        inputs.push(options.messages[0].content[0].text);
        if (++requests === 1) { mutateAfterFailure(); throw new LlmError('fixture', 'SERVER', { status: 503 }); }
        yield { type: 'block-end', index: 0, block: { type: 'text', text: '<block>no</block>' } };
        yield { type: 'finish', reason: { kind: 'stop' } };
      },
    } as any);
    ctx.provide('tools', { schemas: () => [{ name: 'edit', parameters: { type: 'object' } }] } as any);
    ctx.provide('agents', { create: async (options: any) => {
      const events: any[] = []; let pending: Promise<void> = Promise.resolve();
      const native = { id: options.sessionId, session: { snapshotEvents: () => events, deriveMessages: () => [] },
        followup(message: any) {
          inputs.push(message.content[0].text);
          pending = Promise.resolve().then(() => {
            if (++requests === 1) { mutateAfterFailure(); throw new LlmError('fixture', 'SERVER', { status: 503 }); }
            events.push({ type: 'assistant/message', data: { message: { content: [{ type: 'text', text: 'Assessment: {"outcome":"allow"}' }] } } }, { type: 'turn/end', data: { reason: { kind: 'completed' } } });
          });
        }, whenIdle: () => pending, cancel() {},
      };
      return { agent: native, dispose: () => pending.catch(() => {}) };
    } } as any);
    const recovery = new ReviewRecovery(new AbortController().signal, 'action', policy, { provider: 'fixture', model: 'review' });
    const request = { exec: { agent, name: 'edit', callId: 'action', arguments: { path: '/tmp/public.md', content: 'PRECISE_ACTION' }, signal: recovery.signal }, config: { agentId: 'a', revision: '1', mode: 'global', approval: { ...approvalDefaults, rules: policy } }, sources, inherited, reviewer: { provider: 'fixture', model: 'review' }, recovery } as unknown as ApprovalReviewRequest;
    const guardian = new CodexApproval(ctx);
    try {
      const pending = policy === 'nano' ? classify(ctx, request) : guardian.review(request);
      await vi.waitFor(() => expect(requests).toBe(1));
      await vi.advanceTimersByTimeAsync(600);
      expect((await pending).decision.behavior).toBe('allow');
      expect(inputs).toHaveLength(2); expect(inputs[1]).toBe(inputs[0]);
      const input = inputs[1]!;
      expect(input).not.toContain('LATE_REINTRODUCED_OLD_AUTHORIZATION');
      expect(input).toContain('Effective compressed summary only'); expect(input).toContain('PRECISE_ACTION');
      const section = policy === 'nano' ? input.split('<transcript>\n')[1]!.split('\n</transcript>')[0]! : input.split('<conversation_transcript>\n')[1]!.split('\n</conversation_transcript>')[0]!;
      const actual = section.split('\n').filter(line => line.startsWith('{')).map(line => JSON.parse(line)).filter(row => row.inbox_result);
      const expected = (policy === 'codex' ? codexEntries(snapshot) : snapshot).filter(row => row.inbox_result);
      expect(actual).toEqual(expected);
      expect(actual.find(row => row.id === 'inbox-live').observation).toBe(restored ? 'restored' : 'live');
      expect(actual.find(row => row.id === 'inbox-legacy-live').observation).toBe(restored ? 'restored' : 'live');
      expect(actual.find(row => row.id === 'inbox-restored').observation).toBe('restored');
      expect(recovery.trace).toMatchObject({ retriesUsed: 1, formatRetriesUsed: 0 });
    } finally { recovery.finish('test', 'test'); await ctx.fiber.dispose(); vi.useRealTimers(); }
  });
}
