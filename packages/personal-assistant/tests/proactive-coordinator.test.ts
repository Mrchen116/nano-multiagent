import { describe, expect, it } from 'vitest';
import {
  ProactiveCoordinator, formatZonedIso, isProactivePlanningEnabled,
  nightlyCycleSlotKey, renderProactiveNightlyWake, renderProactiveReviewWake,
  type AgentConfiguration, type RuntimePort,
} from '../src/index.js';
import { InboxStore } from '../src/inbox.js';
import { NodeStore } from '../src/store.js';
import { GlobalAgent } from '../src/global-agent.js';
import { TaskContext } from '../src/task-context.js';

function makePaConfig(overrides: Partial<AgentConfiguration> = {}): AgentConfiguration {
  return {
    agentId: 'pa', mode: 'global', workspace: '/tmp/pa', revision: '1', provider: 'fixture', model: 'fixture',
    personal: { bindingId: 'b1', ownerId: 'owner', conversationId: 'dm-owner', epoch: 1 },
    features: { task_graph: true, proactive_planning: true, cron_scheduling: true, dreaming: true, memory_curation: true },
    ...overrides,
  };
}

describe('ProactiveCoordinator', () => {
  it('computes natural-day 03:00 cycle slots and zoned ISO timestamps under explicit ownerTimezone', () => {
    const before3am = Date.parse('2027-03-16T02:45:00+08:00');
    const after3am = Date.parse('2027-03-16T03:05:00+08:00');
    expect(nightlyCycleSlotKey(before3am, 'Asia/Shanghai', 3)).toBe('2027-03-15');
    expect(nightlyCycleSlotKey(after3am, 'Asia/Shanghai', 3)).toBe('2027-03-16');
    expect(formatZonedIso(after3am, 'Asia/Shanghai')).toBe('2027-03-16T03:05:00+08:00');
    expect(renderProactiveReviewWake({ localTime: '2027-03-15T20:15:00+08:00', quietMinutes: 15, quietHours: false })).toContain('<proactive-review-wake');
    expect(renderProactiveNightlyWake({ localTime: '2027-03-16T03:05:00+08:00', quietMinutes: 45, quietHours: true })).toContain('<proactive-nightly-wake');
  });

  it('advances watermarks on quiet review and 03:00-06:00 nightly windows, preserving watermarks when busy', async () => {
    const store = new NodeStore(':memory:', 'owner');
    const inbox = new InboxStore(':memory:');
    store.setOwnerTimezone('Asia/Shanghai');
    const pa = makePaConfig({ features: { task_graph: true, proactive_planning: true, dreaming: false } });
    const ordinary: AgentConfiguration = {
      agentId: 'worker', mode: 'single_thread', workspace: '/tmp/worker', revision: '1', provider: 'fixture', model: 'fixture',
      features: { task_graph: true, proactive_planning: true },
    };
    expect(isProactivePlanningEnabled(pa)).toBe(true);
    expect(isProactivePlanningEnabled(ordinary)).toBe(false);

    const submissions: { inputId: string; channel: string; onlyIfIdle?: boolean; text: string }[] = [];
    let acceptSubmit = false;
    const runtime: RuntimePort = {
      onNotification: () => () => {},
      async request(method, value) {
        if (method === 'session.lookup') return { accepted: false };
        if (method === 'session.submit') {
          const input = value as { inputId: string; onlyIfIdle?: boolean; content: { text: string }[]; source: { channel: string } };
          submissions.push({ inputId: input.inputId, channel: input.source.channel, onlyIfIdle: input.onlyIfIdle, text: input.content[0]?.text ?? '' });
          return { accepted: acceptSubmit };
        }
        return {};
      },
    };

    let nowMs = Date.parse('2027-03-15T20:00:00+08:00');
    const binding = { agentId: 'pa', sessionId: 'pa-root', conversationId: 'global:pa', ownerId: 'owner', cwd: '/tmp/pa', revision: '1' };
    store.bind(binding);

    const coordinator = new ProactiveCoordinator({
      ownerId: 'owner', agents: [pa, ordinary], store, inbox, runtime,
      binding: async () => binding, available: () => true, syncObservations: async () => {},
      onError: error => { throw error; },
    });
    coordinator.useClock(() => nowMs);

    try {
      // Non-personal agents never record proactive activity.
      coordinator.recordActivity('worker', nowMs);
      expect(store.proactiveState('worker').lastActivitySeq).toBe(0);

      // Owner activity at 20:00; < 12m quiet does not trigger review.
      coordinator.recordActivity('pa', nowMs);
      expect(store.proactiveState('pa').lastActivitySeq).toBe(1);
      nowMs = Date.parse('2027-03-15T20:10:00+08:00');
      await coordinator.tick(nowMs);
      expect(submissions).toHaveLength(0);

      // At 20:13 (>= 12m quiet), busy session (accepted=false) preserves lastReviewedSeq for retry.
      nowMs = Date.parse('2027-03-15T20:13:00+08:00');
      await coordinator.tick(nowMs);
      expect(submissions).toHaveLength(1);
      expect(submissions[0]).toMatchObject({ channel: 'proactive_review', onlyIfIdle: true });
      expect(store.proactiveState('pa').lastReviewedSeq).toBe(0);

      // Once idle (accepted=true), retry succeeds and advances lastReviewedSeq without touching lastNightlySeq.
      acceptSubmit = true;
      nowMs = Date.parse('2027-03-15T20:14:00+08:00');
      await coordinator.tick(nowMs);
      expect(submissions).toHaveLength(2);
      expect(store.proactiveState('pa')).toMatchObject({ lastReviewedSeq: 1, lastNightlySeq: 0 });

      // Subsequent daytime ticks without new activity stay silent.
      nowMs = Date.parse('2027-03-15T21:00:00+08:00');
      await coordinator.tick(nowMs);
      expect(submissions).toHaveLength(2);

      // Late-night owner activity at 02:50; at 03:05 only 15m quiet (< 30m nightly gate) -> waits!
      nowMs = Date.parse('2027-03-16T02:50:00+08:00');
      coordinator.recordActivity('pa', nowMs);
      expect(store.proactiveState('pa').lastActivitySeq).toBe(2);

      nowMs = Date.parse('2027-03-16T03:05:00+08:00');
      await coordinator.tick(nowMs);
      expect(submissions).toHaveLength(2);

      // At 03:21 (>= 30m quiet inside 03:00-06:00), proactive_nightly fires once for cycle 2027-03-16, even with dreaming=false!
      nowMs = Date.parse('2027-03-16T03:21:00+08:00');
      await coordinator.tick(nowMs);
      expect(submissions).toHaveLength(3);
      expect(submissions[2]).toMatchObject({ channel: 'proactive_nightly', onlyIfIdle: true });
      expect(store.proactiveState('pa')).toMatchObject({
        lastActivitySeq: 2,
        lastReviewedSeq: 2,
        lastNightlySeq: 2,
        lastNightlyCycle: '2027-03-16',
      });

      // Another tick in the same 03:00-06:00 slot does not re-fire proactive_nightly.
      nowMs = Date.parse('2027-03-16T04:30:00+08:00');
      await coordinator.tick(nowMs);
      expect(submissions).toHaveLength(3);

      // Disabling proactive_planning or holding for configuration suppresses wakes immediately.
      nowMs = Date.parse('2027-03-16T10:00:00+08:00');
      coordinator.recordActivity('pa', nowMs);
      expect(coordinator.hold('pa', 'op-1')).toBe(true);
      nowMs = Date.parse('2027-03-16T10:20:00+08:00');
      await coordinator.tick(nowMs);
      expect(submissions).toHaveLength(3);
      coordinator.release('pa', 'op-1');
      pa.features!.proactive_planning = false;
      await coordinator.tick(nowMs);
      expect(submissions).toHaveLength(3);
    } finally {
      await coordinator.stop();
      inbox.close();
      store.close();
    }
  });

  it('synchronizes unread personal observations into Inbox before scheduled PA execution', async () => {
    const store = new NodeStore(':memory:', 'owner');
    const inbox = new InboxStore(':memory:');
    store.setOwnerTimezone('Asia/Shanghai');
    const pa = makePaConfig();
    const binding = { agentId: 'pa', sessionId: 'pa-root', conversationId: 'global:pa', ownerId: 'owner', cwd: '/tmp/pa', revision: '1' };
    store.bind(binding);

    const coordinator = new ProactiveCoordinator({
      ownerId: 'owner',
      agents: [pa],
      store,
      inbox,
      runtime: { onNotification: () => () => {}, request: async () => ({}) },
      binding: async () => binding,
      available: () => true,
      syncObservations: async () => {
        inbox.receive({
          agent_id: 'pa',
          conversation_id: 'grp-trip',
          conversation_type: 'group',
          relay_task_id: 'obs-1',
          idempotency_key: 'obs-1',
          metadata: { conversation_title: '周末出行群' },
          message: {
            id: 'msg-1',
            content: '明早改到 9 点半集合',
            sender_type: 'user',
            sender_user_id: 'friend-1',
            sender_display_name: 'Alice',
            created_at: '2027-03-16T07:30:00Z',
            attachments: [],
          },
        }, false);
      },
      onError: error => { throw error; },
    });

    try {
      const synced = await coordinator.syncObservations({
        agentId: 'pa',
        sessionId: 'pa-root',
        ownerId: 'owner',
      });
      expect(synced.synced_count).toBe(1);
      expect(synced.unread_conversations).toEqual([
        expect.objectContaining({ title: '周末出行群', count: 1 }),
      ]);
    } finally {
      await coordinator.stop();
      inbox.close();
      store.close();
    }
  });

  it('drives non-PA global digital employees with role-calibrated wakes, user-message watermarks, and stateless pendingTaskContext refresh', async () => {
    const store = new NodeStore(':memory:', 'owner');
    const inbox = new InboxStore(':memory:');
    store.setOwnerTimezone('Asia/Shanghai');

    const globalEmp: AgentConfiguration = { agentId: 'q', mode: 'global', workspace: '/tmp/q', revision: '1', provider: 'fixture', model: 'fixture', features: { task_graph: true } };
    expect(isProactivePlanningEnabled(globalEmp)).toBe(true);
    expect(isProactivePlanningEnabled({ ...globalEmp, features: { task_graph: false } })).toBe(false);
    expect(isProactivePlanningEnabled({ ...globalEmp, toolAllowlist: ['read'] })).toBe(false);

    const reviewText = renderProactiveReviewWake({ localTime: '2027-03-15T20:15:00+08:00', quietMinutes: 15, quietHours: false, personal: false });
    const nightlyText = renderProactiveNightlyWake({ localTime: '2027-03-16T03:15:00+08:00', quietMinutes: 45, quietHours: true, personal: false });
    expect(reviewText).toContain('ROLE.md');
    expect(reviewText).toContain('originating conversation');
    expect(nightlyText).toContain('[Pending Proactive Handoff: <target>]');
    expect(nightlyText).toContain('0 morning greetings');
    expect(nightlyText).toContain('proposed_for_user_id');
    expect(nightlyText).not.toContain('[Pending Morning Brief]');

    const binding = { agentId: 'q', sessionId: 'q-root', conversationId: 'global:q', ownerId: 'owner', cwd: '/tmp/q', revision: '1' };
    store.bind(binding);
    const coordinator = new ProactiveCoordinator({
      ownerId: 'owner', agents: [globalEmp], store, inbox,
      runtime: { onNotification: () => () => {}, request: async () => ({ accepted: true }) },
      binding: async () => binding, available: () => true, syncObservations: async () => {}, onError: error => { throw error; },
    });

    const rawConv = 'conv-bob-q-00000000000000000001';
    const rawBob = '00000000-0000-4000-8000-000000000099';
    const mockRelay = {
      async request(type: string) {
        if (type === 'task.context.sync') {
          return {
            type: 'result',
            payload: {
              ok: true,
              result: {
                through: 1, next: 1, revoked_message_ids: [],
                items: [{
                  message_id: 'msg-click-1', conversation_id: rawConv, allowed: true,
                  input: {
                    agent_id: 'q', conversation_id: rawConv, relay_task_id: 'rt-1', idempotency_key: 'rt-1',
                    metadata: { conversation_type: 'direct', task_context: true },
                    message: {
                      id: 'msg-click-1', content: 'Bob rejected card', sender_type: 'system', created_at: '2027-03-15T18:00:00Z', attachments: [],
                      system_notice: { kind: 'task_graph', conversation_id: rawConv, previous_status: 'proposed', status: 'closed', actor: { type: 'user', id: rawBob } },
                    },
                  },
                }],
              },
            },
          };
        }
        if (type === 'conversation.query') return { type: 'result', payload: { ok: true, result: { conversations: [] } } };
        return { type: 'ack', payload: {} };
      },
    };
    const mockRuntime = {
      onNotification: () => () => {},
      request: async (method: string) => method === 'session.work.children' ? { children: [] } : { events: [], durable: true, status: 'idle', accepted: true },
    };
    const product = new GlobalAgent({
      nodeId: 'node-1', ownerId: 'owner', agents: [globalEmp], store, inbox,
      onProactiveActivity: agentId => coordinator.recordActivity(agentId),
      runtime: mockRuntime, relay: mockRelay, image: async () => '', onError: error => { throw error; },
    });
    product.attachTaskContext(new TaskContext({ nodeId: 'node-1', ownerId: 'owner', agents: [globalEmp], store, inbox, runtime: mockRuntime, relay: mockRelay, refreshSources: async () => {} }));

    try {
      await product.ingest({
        agent_id: 'q', conversation_id: rawConv, relay_task_id: 'chat-1', idempotency_key: 'chat-1',
        metadata: { conversation_type: 'direct' },
        message: { id: 'chat-1', content: '帮我看下脚本超时', sender_type: 'user', sender_user_id: rawBob, attachments: [] },
      });
      expect(store.proactiveState('q').lastActivitySeq).toBe(1);

      const refreshed = await product.call({
        method: 'memory.sources.refresh', args: { includePendingTaskContext: true },
        agentId: 'q', ownerId: 'owner', sessionId: 'q-root', rootSessionId: 'q-root', callId: 'ref-1', operationId: 'q-root:ref-1',
      }) as { synchronized: boolean; pendingTaskContext?: Array<{ messageId: string; conversationId: string; conversationRef?: string; text: string }> };

      expect(refreshed.synchronized).toBe(true);
      expect(refreshed.pendingTaskContext).toHaveLength(1);
      expect(refreshed.pendingTaskContext![0]!.messageId).toBe('msg-click-1');
      expect(refreshed.pendingTaskContext![0]!.conversationId).toBe(rawConv);
      expect(refreshed.pendingTaskContext![0]!.conversationRef).toMatch(/^c_[a-f0-9]{6}$/);
      expect(refreshed.pendingTaskContext![0]!.text).toMatch(/"id":"u_[a-f0-9]{6}"/);
      expect(refreshed.pendingTaskContext![0]!.text).not.toContain(rawBob);
    } finally {
      await coordinator.stop();
      await product.stop();
      inbox.close();
      store.close();
    }
  });

  it('projects PA knowledge.sources.sync allowed/excluded IDs to short c_xxxxxx refs matching pendingTaskContext', async () => {
    const store = new NodeStore(':memory:', 'owner');
    const inbox = new InboxStore(':memory:');
    const rawOwnerDm = 'conv-personal-owner-long-id-000000001';
    const rawAllowedGrp = 'conv-shared-group-long-id-00000000002';
    const rawExcludedGrp = 'conv-excluded-group-long-id-000000003';
    const paCfg: AgentConfiguration = {
      agentId: 'pa', revision: '1', provider: 'test', model: 'test', mode: 'global',
      personal: { bindingId: 'bind-1', ownerId: 'owner', conversationId: rawOwnerDm, epoch: 1 },
    };
    store.bind({ agentId: 'pa', sessionId: 'pa-root', ownerId: 'owner', conversationId: 'global:pa', cwd: '/tmp', revision: '1' });

    const syncedSnapshots: Array<{ allowed: string[]; excluded: string[] }> = [];
    const mockRuntime = {
      onNotification: () => () => {},
      request: async (method: string, args: any) => {
        if (method === 'knowledge.sources.sync') syncedSnapshots.push(args.snapshot);
        return method === 'session.work.children' ? { children: [] } : { events: [], durable: true, status: 'idle', accepted: true };
      },
    };
    const mockRelay = {
      ready: true,
      async request(type: string) {
        if (type === 'pa.source.admit') {
          return { type: 'result', payload: { ok: true, result: { allowed: true, is_owner: true, delivery: 'participant', conversation_type: 'direct', channel: 'web' } } };
        }
        if (type === 'pa.sources') {
          return {
            type: 'result',
            payload: {
              ok: true,
              result: {
                policy: { revision: 2 },
                items: [
                  { id: rawAllowedGrp, excluded: false },
                  { id: rawExcludedGrp, excluded: true },
                ],
              },
            },
          };
        }
        if (type === 'task.context.sync') {
          return {
            type: 'result',
            payload: {
              ok: true,
              result: {
                through: 1, next: 1, revoked_message_ids: [],
                items: [{
                  message_id: 'pa-click-1', conversation_id: rawOwnerDm, allowed: true,
                  input: {
                    agent_id: 'pa', conversation_id: rawOwnerDm, relay_task_id: 'rt-pa-1', idempotency_key: 'rt-pa-1',
                    metadata: { conversation_type: 'direct', task_context: true },
                    message: {
                      id: 'pa-click-1', content: 'Owner closed proposed card', sender_type: 'system', created_at: '2027-03-15T19:00:00Z', attachments: [],
                      system_notice: { kind: 'task_graph', conversation_id: rawOwnerDm, previous_status: 'proposed', status: 'closed', actor: { type: 'user', id: 'owner' } },
                    },
                  },
                }],
              },
            },
          };
        }
        return { type: 'result', payload: { ok: true, result: { items: [] } } };
      },
    };
    const product = new GlobalAgent({
      nodeId: 'node-1', ownerId: 'owner', agents: [paCfg], store, inbox,
      runtime: mockRuntime, relay: mockRelay, image: async () => '', onError: error => { throw error; },
    });
    product.attachTaskContext(new TaskContext({
      nodeId: 'node-1', ownerId: 'owner', agents: [paCfg], store, inbox, runtime: mockRuntime, relay: mockRelay,
      refreshSources: agentId => product.prepareSystemContext(agentId),
      settlePersonalInputs: (agentId, sessionId) => product.settleSyncedTaskContext(agentId, sessionId),
    }));

    try {
      const res = await product.call({
        method: 'memory.sources.refresh', args: { includePendingTaskContext: true },
        agentId: 'pa', ownerId: 'owner', sessionId: 'pa-root', rootSessionId: 'pa-root', callId: 'ref-pa', operationId: 'pa-root:ref-pa',
      }) as { synchronized: boolean; pendingTaskContext?: Array<{ conversationId: string; conversationRef?: string }> };

      expect(syncedSnapshots.length).toBeGreaterThanOrEqual(1);
      const snap = syncedSnapshots.at(-1)!;
      const expectedOwnerRef = store.toolReferences.conversationRef('pa', rawOwnerDm);
      const expectedGrpRef = store.toolReferences.conversationRef('pa', rawAllowedGrp);
      const expectedExclRef = store.toolReferences.conversationRef('pa', rawExcludedGrp);
      expect(snap.allowed).toEqual(expect.arrayContaining([expectedOwnerRef, expectedGrpRef]));
      expect(snap.excluded).toEqual([expectedExclRef]);
      expect(res.pendingTaskContext).toHaveLength(1);
      expect(res.pendingTaskContext![0]!.conversationRef).toBe(expectedOwnerRef);
    } finally {
      await product.stop();
      inbox.close();
      store.close();
    }
  });
});
