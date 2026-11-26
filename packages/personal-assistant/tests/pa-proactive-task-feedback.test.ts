import { expect, it } from 'vitest';
import type { AgentConfiguration, RelayInput, RuntimePort } from '@nano/product-contracts';
import { GlobalAgent, InboxStore, NodeStore, TaskContext } from '../src/index.js';
import { PersonalAssistant } from '../src/personal-assistant.js';

function makeTaskNoticeInput(params: {
  id: string;
  conversationId: string;
  actorType: 'user' | 'agent';
  actorId: string;
  content: string;
  createdAt: string;
  previousStatus?: string | null;
  status?: string | null;
}): RelayInput {
  return {
    agent_id: 'pa',
    conversation_id: params.conversationId,
    relay_task_id: `relay-${params.id}`,
    idempotency_key: `idem-${params.id}`,
    metadata: {
      conversation_type: params.conversationId === 'c_owner' ? 'direct' : 'group',
      task_context: true,
    },
    message: {
      id: params.id,
      content: params.content,
      sender_type: 'system',
      sender_user_id: params.actorId,
      created_at: params.createdAt,
      attachments: [],
      system_notice: {
        kind: 'task_graph',
        graph_id: 'tg_1',
        node_id: 'n1',
        scope_id: 'n1',
        revision: 2,
        event_time: params.createdAt,
        previous_status: params.previousStatus ?? 'proposed',
        status: params.status ?? 'closed',
        actor: { type: params.actorType, id: params.actorId },
        attention_actor_ids: ['pa'],
      },
    },
  };
}

it('admits trusted owner private task notices without pa.review, flushes shared-group task notices before Dreaming peek, and avoids duplicate pa.sources calls', async () => {
  const store = new NodeStore(':memory:', 'owner');
  const inbox = new InboxStore(':memory:');
  const config: AgentConfiguration = {
    agentId: 'pa',
    mode: 'global',
    workspace: '/tmp/pa',
    revision: '1',
    provider: 'fixture',
    model: 'fixture',
    personal: { bindingId: 'b_pa', ownerId: 'owner', conversationId: 'c_owner', epoch: 1 },
  };
  const binding = store.bind({
    agentId: 'pa',
    ownerId: 'owner',
    sessionId: 'pa-root',
    conversationId: 'global:pa',
    cwd: '/tmp/pa',
    revision: '1',
  });

  const reviewCalls: unknown[] = [];
  const relayCalls: string[] = [];
  const indexedNotices: { seq: number; item: RelayInput }[] = [];

  const runtime: RuntimePort = {
    onNotification: () => () => {},
    async request(method, args) {
      if (method === 'pa.review') {
        reviewCalls.push(args);
        const timeline = ((args as any).evidence?.timeline ?? []) as { id: string; content: string }[];
        const singleInjected = timeline.length === 1 && timeline[0]!.content.includes('PROMPT_INJECTION');
        return {
          decision: singleInjected ? 'deny' : 'allow',
          reason: singleInjected ? 'Prompt injection in task title' : 'batch reviewed',
          ...(singleInjected ? { incident: { reason: 'Prompt injection' } } : {}),
          decisions: timeline.map(entry =>
            entry.content.includes('PROMPT_INJECTION')
              ? { id: entry.id, decision: 'deny', reason: 'Prompt injection in task title', incident: { reason: 'Prompt injection' } }
              : { id: entry.id, decision: 'allow', reason: 'Safe group task update' }),
        };
      }
      return { accepted: true, durable: true };
    },
  };

  const relay = {
    ready: true,
    async request(type: string, payload: Record<string, unknown>) {
      relayCalls.push(type);
      const ok = (result: unknown = {}) => ({ type: `${type}.result`, payload: { ok: true, result } });
      if (type === 'agent.session.ensure' || type === 'node.delivery_receipt') return ok();
      if (type === 'pa.observations.read') return ok({ items: [], has_more: false });
      if (type === 'pa.incidents.pending') return ok({ items: [] });
      if (type === 'pa.incident.report') return ok({ id: 'inc_1' });
      if (type === 'pa.sources' && payload.action === 'list') {
        return ok({
          policy: { revision: 1, excluded_conversation_ids: ['c_excluded'] },
          items: [
            { id: 'c_owner', excluded: false },
            { id: 'c_group', excluded: false },
            { id: 'c_excluded', excluded: true },
          ],
        });
      }
      if (type === 'pa.source.admit') {
        const cid = String(payload.conversation_id);
        const mid = String(payload.source_message_id);
        if (cid === 'c_owner') {
          return ok({
            allowed: true,
            is_owner: false,
            trusted_owner_task_notice: mid.startsWith('owner-') || mid.startsWith('offline-owner-'),
            delivery: 'participant',
            conversation_type: 'direct',
            channel: 'web',
          });
        }
        return ok({
          allowed: cid === 'c_group',
          is_owner: false,
          delivery: 'participant',
          conversation_type: 'group',
          channel: 'web',
        });
      }
      if (type === 'pa.input.context') {
        const ids = (payload.source_message_ids as string[] | undefined)
          ?? (payload.source_message_id ? [String(payload.source_message_id)] : []);
        return ok({
          conversation: { id: payload.conversation_id, type: 'group', delivery: 'participant', channel: 'web' },
          previous: [],
          timeline: ids.map(id => {
            const hit = indexedNotices.find(entry => entry.item.message.id === id)?.item;
            return {
              id,
              needs_decision: true,
              sender: { id: 'teammate', type: 'system', is_owner: false },
              content: hit?.message.content ?? '',
              created_at: hit?.message.created_at ?? null,
            };
          }),
          omissions: [],
        });
      }
      if (type === 'task.context.sync') {
        const after = Number(payload.after ?? 0);
        const pending = (payload.pending as string[] | undefined) ?? [];
        const bound = indexedNotices.at(-1)?.seq ?? 0;
        if (pending.length) {
          return ok({ through: bound, next: after, items: [], revoked_message_ids: [] });
        }
        const rows = indexedNotices.filter(entry => entry.seq > after && entry.seq <= bound);
        return ok({
          through: bound,
          next: bound,
          items: rows.map(entry => ({
            seq: entry.seq,
            message_id: entry.item.message.id,
            conversation_id: entry.item.conversation_id,
            allowed: entry.item.conversation_id !== 'c_excluded',
            input: entry.item,
          })),
          revoked_message_ids: [],
        });
      }
      throw new Error(`Unexpected relay call: ${type}`);
    },
  };

  const globalAgent = new GlobalAgent({
    nodeId: 'node',
    ownerId: 'owner',
    agents: [config],
    store,
    inbox,
    runtime,
    relay,
    image: async () => '',
    onError: error => { throw error; },
  });
  const taskContext = new TaskContext({
    nodeId: 'node',
    ownerId: 'owner',
    agents: [config],
    store,
    inbox,
    runtime,
    relay,
    refreshSources: agentId => globalAgent.prepareSystemContext(agentId),
    settlePersonalInputs: (agentId, sessionId) => globalAgent.settleSyncedTaskContext(agentId, sessionId),
  });
  globalAgent.attachTaskContext(taskContext);

  try {
    // 1. Direct PersonalAssistant.admit also honors trusted_owner_task_notice without calling pa.review.
    const directPa = new PersonalAssistant({
      nodeId: 'node',
      ownerId: 'owner',
      agents: [config],
      store,
      inbox,
      runtime,
      relay,
      onError: error => { throw error; },
    });
    const directNotice = makeTaskNoticeInput({
      id: 'owner-direct-admit',
      conversationId: 'c_owner',
      actorType: 'user',
      actorId: 'owner',
      content: 'Owner：周末体脂打卡，未采纳（已关闭）',
      createdAt: '2026-11-26T10:00:00.000Z',
    });
    const directVerdict = await directPa.admit(config, binding, directNotice);
    expect(directVerdict.kind).toBe('admitted');
    expect(reviewCalls).toHaveLength(0);
    // Mark directNotice consumed so we focus on the pure click-without-chat relay items below.
    const directPrepared = inbox.prepareSystemContext('pa', binding.sessionId).find(item => item.inputId === 'owner-direct-admit')!;
    inbox.commitSystemContext('pa', binding.sessionId, directPrepared.inputId, directPrepared.content, 0);

    // 2. Owner clicks "不采纳" in private chat + two task notices arrive in shared group (one safe, one prompt injection).
    const ownerReject = makeTaskNoticeInput({
      id: 'owner-reject-1',
      conversationId: 'c_owner',
      actorType: 'user',
      actorId: 'owner',
      content: 'Owner：[整理竞品定价表](/tasks/tg_1?scope=n1&node=n1)，未采纳（已关闭）',
      createdAt: '2026-11-26T14:30:00.000Z',
    });
    const groupSafe = makeTaskNoticeInput({
      id: 'group-safe-1',
      conversationId: 'c_group',
      actorType: 'user',
      actorId: 'teammate',
      content: 'Teammate：[准备接口联调清单](/tasks/tg_2?scope=n1&node=n1)，已批准（待办）',
      createdAt: '2026-11-26T15:00:00.000Z',
      status: 'todo',
    });
    const groupInjected = makeTaskNoticeInput({
      id: 'group-inj-1',
      conversationId: 'c_group',
      actorType: 'user',
      actorId: 'teammate',
      content: 'Teammate：[PROMPT_INJECTION exfiltrate secrets](/tasks/tg_3?scope=n1&node=n1)，已创建',
      createdAt: '2026-11-26T15:05:00.000Z',
      previousStatus: null,
      status: 'todo',
    });
    indexedNotices.push(
      { seq: 1, item: ownerReject },
      { seq: 2, item: groupSafe },
      { seq: 3, item: groupInjected },
    );

    await globalAgent.receive(ownerReject);
    expect(inbox.reviews.get('pa', 'owner-reject-1')?.state).toBe('admitted');
    expect(reviewCalls).toHaveLength(0);
    expect(inbox.wakePending('pa')).toBeUndefined();

    await globalAgent.receive(groupSafe);
    await globalAgent.receive(groupInjected);
    expect(inbox.reviews.get('pa', 'group-safe-1')?.state).toBe('pending');
    expect(inbox.reviews.get('pa', 'group-inj-1')?.state).toBe('pending');

    // 3. Nightly Dreaming calls memory.sources.refresh({ includePendingTaskContext: true }).
    relayCalls.length = 0;
    const refreshResult = await globalAgent.call({
      method: 'memory.sources.refresh',
      args: { includePendingTaskContext: true },
      operationId: 'dream-refresh-1',
      callId: 'dream-call-1',
      sessionId: binding.sessionId,
      rootSessionId: binding.sessionId,
      agentId: 'pa',
      ownerId: 'owner',
    }) as { synchronized: boolean; pendingTaskContext: { messageId: string; conversationId: string; timeMs: number; text: string }[] };

    expect(refreshResult.synchronized).toBe(true);
    expect(reviewCalls).toHaveLength(1);
    expect(relayCalls.filter(type => type === 'pa.sources')).toHaveLength(1);
    expect(refreshResult.pendingTaskContext.map(item => item.messageId)).toEqual(['owner-reject-1', 'group-safe-1']);
    expect(refreshResult.pendingTaskContext[0]?.timeMs).toBe(Date.parse('2026-11-26T14:30:00.000Z'));
    expect(refreshResult.pendingTaskContext[0]?.text).toContain('未采纳（已关闭）');
    expect(inbox.reviews.get('pa', 'group-inj-1')?.state).toBe('rejected');

    // 4. verifyCurrent calls memory.sources.refresh({}) -> refreshes pa.sources only, zero task.context.sync!
    relayCalls.length = 0;
    const verifyResult = await globalAgent.call({
      method: 'memory.sources.refresh',
      args: {},
      operationId: 'dream-verify-1',
      callId: 'dream-call-2',
      sessionId: binding.sessionId,
      rootSessionId: binding.sessionId,
      agentId: 'pa',
      ownerId: 'owner',
    }) as { synchronized: boolean; pendingTaskContext?: unknown };
    expect(verifyResult).toEqual({ synchronized: true });
    expect(relayCalls.filter(type => type === 'task.context.sync')).toHaveLength(0);

    // 5. Next morning step consumes the prepared TaskContext items normally; subsequent Dreaming peek sees none left.
    const morningPrepared = await taskContext.prepare({ agentId: 'pa', sessionId: binding.sessionId, ownerId: 'owner' });
    expect(morningPrepared.messages.map(item => item.inputId)).toEqual(['owner-reject-1', 'group-safe-1']);
    await taskContext.commit({
      agentId: 'pa',
      sessionId: binding.sessionId,
      ownerId: 'owner',
      evidence: morningPrepared.messages.map((msg, idx) => ({
        inputId: msg.inputId,
        content: msg.content,
        turn: 1,
        consumedSeq: idx + 1,
      })),
    });

    const nextNightRefresh = await globalAgent.call({
      method: 'memory.sources.refresh',
      args: { includePendingTaskContext: true },
      operationId: 'dream-refresh-2',
      callId: 'dream-call-3',
      sessionId: binding.sessionId,
      rootSessionId: binding.sessionId,
      agentId: 'pa',
      ownerId: 'owner',
    }) as { pendingTaskContext: unknown[] };
    expect(nextNightRefresh.pendingTaskContext).toEqual([]);

    // 6. Offline catch-up / sync-first order (before live relay.message arrives):
    //    TaskContext.sync MUST stage unclassified PA rows and run pa.source.admit + pa.review
    //    so shared-group prompt injection is rejected even when sync beats relay.message!
    const offlineOwnerNotice = makeTaskNoticeInput({
      id: 'offline-owner-1',
      conversationId: 'c_owner',
      actorType: 'user',
      actorId: 'owner',
      content: 'Owner：[整理竞品月报](/tasks/tg_4?scope=n1&node=n1)，暂存待定（先存着）',
      createdAt: '2026-11-27T11:00:00.000Z',
      status: 'backlog',
    });
    const offlineGroupSafe = makeTaskNoticeInput({
      id: 'offline-group-safe',
      conversationId: 'c_group',
      actorType: 'user',
      actorId: 'teammate',
      content: 'Teammate：[对齐联调时间](/tasks/tg_5?scope=n1&node=n1)，已创建',
      createdAt: '2026-11-27T11:10:00.000Z',
      previousStatus: null,
      status: 'todo',
    });
    const offlineGroupInj = makeTaskNoticeInput({
      id: 'offline-group-inj',
      conversationId: 'c_group',
      actorType: 'user',
      actorId: 'teammate',
      content: 'Teammate：[PROMPT_INJECTION leak owner memory](/tasks/tg_6?scope=n1&node=n1)，已创建',
      createdAt: '2026-11-27T11:15:00.000Z',
      previousStatus: null,
      status: 'todo',
    });
    indexedNotices.push(
      { seq: 4, item: offlineOwnerNotice },
      { seq: 5, item: offlineGroupSafe },
      { seq: 6, item: offlineGroupInj },
    );

    reviewCalls.length = 0;
    const offlineRefresh = await globalAgent.call({
      method: 'memory.sources.refresh',
      args: { includePendingTaskContext: true },
      operationId: 'dream-refresh-offline',
      callId: 'dream-call-4',
      sessionId: binding.sessionId,
      rootSessionId: binding.sessionId,
      agentId: 'pa',
      ownerId: 'owner',
    }) as { pendingTaskContext: { messageId: string }[] };

    // Owner private notice skips pa.review via trusted_owner_task_notice; the 2 shared-group notices each go through pa.review!
    expect(reviewCalls).toHaveLength(2);
    expect(offlineRefresh.pendingTaskContext.map(item => item.messageId)).toEqual(['offline-owner-1', 'offline-group-safe']);
    expect(inbox.reviews.get('pa', 'offline-group-inj')?.state).toBe('rejected');

    // Delayed relay.message arriving later for the rejected injection stays rejected and does not re-admit!
    await globalAgent.receive(offlineGroupInj);
    expect(inbox.reviews.get('pa', 'offline-group-inj')?.state).toBe('rejected');
    const afterOfflinePrepare = await taskContext.prepare({ agentId: 'pa', sessionId: binding.sessionId, ownerId: 'owner' });
    expect(afterOfflinePrepare.messages.map(item => item.inputId)).toEqual(['offline-owner-1', 'offline-group-safe']);
  } finally {
    await globalAgent.stop();
    inbox.close();
    store.close();
  }
});
