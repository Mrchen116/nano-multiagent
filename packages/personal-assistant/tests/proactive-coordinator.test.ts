import { describe, expect, it } from 'vitest';
import {
  ProactiveCoordinator,
  formatZonedIso,
  isProactivePlanningEnabled,
  nightlyCycleSlotKey,
  renderProactiveNightlyWake,
  renderProactiveReviewWake,
  type AgentConfiguration,
  type RuntimePort,
} from '../src/index.js';
import { InboxStore } from '../src/inbox.js';
import { NodeStore } from '../src/store.js';

function makePaConfig(overrides: Partial<AgentConfiguration> = {}): AgentConfiguration {
  return {
    agentId: 'pa',
    mode: 'global',
    workspace: '/tmp/pa',
    revision: '1',
    provider: 'fixture',
    model: 'fixture',
    personal: { bindingId: 'b1', ownerId: 'owner', conversationId: 'dm-owner', epoch: 1 },
    features: {
      task_graph: true,
      proactive_planning: true,
      cron_scheduling: true,
      dreaming: true,
      memory_curation: true,
    },
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
      agentId: 'worker',
      mode: 'single_thread',
      workspace: '/tmp/worker',
      revision: '1',
      provider: 'fixture',
      model: 'fixture',
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
          submissions.push({
            inputId: input.inputId,
            channel: input.source.channel,
            onlyIfIdle: input.onlyIfIdle,
            text: input.content[0]?.text ?? '',
          });
          return { accepted: acceptSubmit };
        }
        return {};
      },
    };

    let nowMs = Date.parse('2027-03-15T20:00:00+08:00');
    const binding = { agentId: 'pa', sessionId: 'pa-root', conversationId: 'global:pa', ownerId: 'owner', cwd: '/tmp/pa', revision: '1' };
    store.bind(binding);

    const coordinator = new ProactiveCoordinator({
      ownerId: 'owner',
      agents: [pa, ordinary],
      store,
      inbox,
      runtime,
      binding: async () => binding,
      available: () => true,
      syncObservations: async () => {},
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
});
