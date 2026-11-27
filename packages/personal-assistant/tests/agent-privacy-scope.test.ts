import { afterEach, expect, it, vi } from 'vitest';
import { CHAT_BACKGROUND_DELAY_MS, type AgentConfiguration, type RelayInput, type RuntimePort, type SessionBinding } from '@nano/product-contracts';
import { SingleThread } from '../src/single-thread.js';
import { PersonalAssistant } from '../src/personal-assistant.js';
import { ExternalChannels } from '../src/external.js';
import { NodeStore } from '../src/store.js';
import { InboxStore } from '../src/inbox.js';
import type { ProductCall } from '../src/global-agent.js';

afterEach(() => vi.useRealTimers());

it('keeps SingleThread canonical heartbeat session isolated from owner_internal groups/agent-DMs and flushes 10-min background batches under owner_only', async () => {
  vi.useFakeTimers();
  const store = new NodeStore(':memory:', 'owner');
  const config: AgentConfiguration = {
    agentId: 'a',
    revision: '1',
    model: 'test',
    provider: 'test',
    mode: 'single_thread',
    workspace: '/tmp',
    collaborationScope: 'owner_only',
  };
  const submissions: Array<{ sessionId: string; inputId: string; mode: string; source: Record<string, unknown> }> = [];
  const frames: Array<Record<string, unknown>> = [];
  const product = new SingleThread({
    nodeId: 'n',
    ownerId: 'owner',
    store,
    agents: [config],
    onError: error => { throw error; },
    image: async () => 'img',
    relay: { async request(type, frame) { frames.push({ type, ...frame }); return { type: 'ack', payload: { message_id: 'm' } }; } },
    runtime: {
      onNotification: () => () => {},
      async request(method, params) {
        if (method === 'session.submit') submissions.push(params as any);
        if (method === 'session.lookup') return { accepted: submissions.some(item => item.inputId === (params as { inputId: string }).inputId) };
        return { durable: true, events: [] };
      },
    },
  });

  try {
    // Seed canonical heartbeat placeholder session `owner:owner`.
    const heartbeatSession = store.bind({
      sessionId: 'sess-heartbeat',
      conversationId: 'owner:owner',
      agentId: 'a',
      ownerId: 'owner',
      cwd: '/tmp',
      revision: '1',
    });
    store.markCanonical(heartbeatSession);

    // 1) Same-owner agent-to-agent DM (owner_direct=false, owner_internal=true) runs immediately WITHOUT hijacking `sess-heartbeat`!
    await product.receive({
      agent_id: 'a',
      conversation_id: 'c_agent_dm',
      relay_task_id: 'r-agent-dm',
      idempotency_key: 'r-agent-dm',
      message: { id: 'm-agent-dm', content: 'Peer helper sync', sender_type: 'agent', sender_user_id: 'u-helper', attachments: [], created_at: '2026-11-26T10:00:00Z' },
      metadata: { conversation_type: 'direct', owner_direct: false, owner_internal: true },
    });
    expect(submissions).toHaveLength(1);
    expect(submissions[0]!.sessionId).not.toBe('sess-heartbeat');
    expect(store.canonical('a')?.conversationId).toBe('owner:owner');

    // 2) Same-owner internal group unmentioned message buffers for 10 minutes even under owner_only, then flushes into its own group session!
    await product.receive({
      agent_id: 'a',
      conversation_id: 'c_owner_group',
      relay_task_id: 'r-group-bg',
      idempotency_key: 'r-group-bg',
      message: { id: 'm-group-bg', content: 'Background note in war room', sender_type: 'user', sender_user_id: 'owner', attachments: [], created_at: '2026-11-26T10:01:00Z' },
      metadata: { conversation_type: 'group', owner_direct: false, owner_internal: true, addressed_to_agent: false },
    });
    expect(submissions).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(CHAT_BACKGROUND_DELAY_MS);
    expect(submissions).toHaveLength(2);
    expect(submissions[1]!.inputId).toBe('a:m-group-bg');
    expect(submissions[1]!.sessionId).not.toBe('sess-heartbeat');
    expect(store.canonical('a')?.conversationId).toBe('owner:owner');

    // 3) Human owner 1:1 direct message adopts `sess-heartbeat` as canonical!
    await product.receive({
      agent_id: 'a',
      conversation_id: 'c_human_owner_dm',
      relay_task_id: 'r-owner-dm',
      idempotency_key: 'r-owner-dm',
      message: { id: 'm-owner-dm', content: 'Direct from human owner', sender_type: 'user', sender_user_id: 'owner', attachments: [], created_at: '2026-11-26T10:15:00Z' },
      metadata: { conversation_type: 'direct', owner_direct: true, owner_internal: true },
    });
    expect(submissions).toHaveLength(3);
    expect(submissions[2]!.sessionId).toBe('sess-heartbeat');
    expect(store.canonical('a')?.conversationId).toBe('c_human_owner_dm');

    // 4) Externalization & revocation clear buffered group messages so stale owner_internal=true snapshots never leak after a colleague joins!
    await product.receive({
      agent_id: 'a',
      conversation_id: 'c_owner_group',
      relay_task_id: 'r-stale-bg',
      idempotency_key: 'r-stale-bg',
      message: { id: 'm-stale-bg', content: 'Before external member joined', sender_type: 'user', sender_user_id: 'owner', attachments: [], created_at: '2026-11-26T10:20:00Z' },
      metadata: { conversation_type: 'group', owner_direct: false, owner_internal: true, addressed_to_agent: false },
    });
    const withdrawn = product.revokeConversations('a', ['c_owner_group']);
    product.confirmRestricted(withdrawn);
    await vi.advanceTimersByTimeAsync(CHAT_BACKGROUND_DELAY_MS * 2);
    expect(submissions).toHaveLength(3);
  } finally {
    await product.stop();
    store.close();
  }
});

it('blocks owner_only Feishu outbound sends and streaming turn_start before any platform call or shadow frame while allowing bound ownerOpenId DM', async () => {
  const store = new NodeStore(':memory:', 'owner');
  const accepted: RelayInput[] = [];
  const mirrored: Record<string, unknown>[] = [];
  let platformSends = 0;
  let isPrivate = false;

  const external = new ExternalChannels(':memory:', {
    nodeId: 'node',
    ownerId: 'owner',
    store,
    ownerOnly: () => isPrivate,
    relay: { ready: true, async request(_type, payload) { mirrored.push(payload); return { type: 'ack', payload: { message_id: 'im-msg' } }; } },
    im: async (_path, options) => ({ id: `shadow-${JSON.parse(String(options?.body)).external_chat_id}` }),
    receive: async input => { accepted.push(input); },
    permission: async () => {},
    onError: () => {},
  });
  external.add('a', {
    config: { appId: 'app', ownerOpenId: 'ou-owner' },
    send: async () => { platformSends++; return `plat-${platformSends}`; },
    reaction: async () => undefined,
    image: async () => ({ data: Buffer.alloc(0), mediaType: 'image/png' }),
    updateCard: async () => {},
  });

  try {
    await external.receive('a', { messageId: 'm-owner', chatId: 'chat-owner', senderId: 'ou-owner', isGroup: false, mentioned: false, time: '1000', parts: [{ type: 'text', text: 'hi' }] });
    await external.receive('a', { messageId: 'm-peer', chatId: 'chat-peer', senderId: 'ou-peer', isGroup: false, mentioned: false, time: '1001', parts: [{ type: 'text', text: 'hi' }] });
    await external.receive('a', { messageId: 'm-group', chatId: 'chat-group', senderId: 'ou-owner', isGroup: true, mentioned: true, time: '1002', parts: [{ type: 'text', text: 'hi' }] });
    const [ownerChatId, peerChatId, groupChatId] = accepted.map(x => x.conversation_id);
    await external.recover();
    mirrored.length = 0;
    isPrivate = true;

    // Non-owner Feishu DM & Feishu group are blocked BEFORE platform send and BEFORE shadow turn_start!
    for (const target of [peerChatId!, groupChatId!]) {
      await expect(external.request('agent.message', {
        node_id: 'node',
        to: `conversation:${target}`,
        text: 'Leak attempt',
        from_session_id: 'a|tool_call:op-leak',
      })).rejects.toMatchObject({ code: 'collaboration_scope_restricted' });

      await expect(external.request('node.streaming_delta', {
        node_id: 'node',
        kind: 'turn_start',
        agent_id: 'a',
        conversation_id: target,
        idempotency_key: `turn-${target}`,
      })).rejects.toMatchObject({ code: 'collaboration_scope_restricted' });
    }
    expect(platformSends).toBe(0);
    expect(mirrored.filter(m => m.kind === 'turn_start')).toHaveLength(0);

    // Bound ownerOpenId Feishu DM succeeds under owner_only!
    const ok = await external.request('agent.message', {
      node_id: 'node',
      to: `conversation:${ownerChatId}`,
      text: 'Private report to owner',
      from_session_id: 'a|tool_call:op-owner',
    });
    expect(ok.payload).toMatchObject({ message_id: 'plat-1' });
    expect(platformSends).toBe(1);

    // Switching back to team allows peerChatId send.
    isPrivate = false;
    await expect(external.request('agent.message', {
      node_id: 'node',
      to: `conversation:${peerChatId}`,
      text: 'Team reply',
      from_session_id: 'a|tool_call:op-team',
    })).resolves.toMatchObject({ payload: { message_id: 'plat-2' } });
  } finally {
    await external.stop();
    store.close();
  }
});

it('returns structured collaboration_scope_restricted not_sent in PersonalAssistant.send and retires participant observations while keeping observer ones', async () => {
  const store = new NodeStore(':memory:', 'owner');
  const inbox = new InboxStore(':memory:');
  const config: AgentConfiguration = {
    agentId: 'pa',
    mode: 'global',
    workspace: '/tmp/pa',
    revision: '1',
    provider: 'test',
    model: 'test',
    collaborationScope: 'owner_only',
    personal: { bindingId: 'binding', ownerId: 'owner', conversationId: 'c_owner', epoch: 1 },
  };
  const binding: SessionBinding = store.bind({
    agentId: 'pa',
    ownerId: 'owner',
    sessionId: 'main',
    conversationId: 'global:pa',
    cwd: '/tmp/pa',
    revision: '1',
  });
  const runtime: RuntimePort = { onNotification: () => () => {}, request: async () => ({}) };
  const relay = {
    request: async (type: string, payload: Record<string, unknown>) => {
      if (type === 'agent.message') return { type: 'ack', payload: { message_id: 'm-owner', conversation_id: 'c_owner' } };
      if (type === 'conversation.query' && payload.action === 'resolve_target') {
        if (payload.target === 'user:colleague') {
          return { type: 'conversation.query.result', payload: { ok: false, error: { code: 'collaboration_scope_restricted', message: 'Restricted' } } };
        }
        return { type: 'conversation.query.result', payload: { ok: true, result: { target: null } } };
      }
      if (type === 'pa.action.prepare' || type === 'pa.action.status') {
        return { type: `${type}.result`, payload: { ok: false, error: { code: 'collaboration_scope_restricted', message: 'Restricted' } } };
      }
      return { type: `${type}.result`, payload: { ok: true, result: {} } };
    },
  };
  const pa = new PersonalAssistant({ nodeId: 'node', ownerId: 'owner', agents: [config], store, inbox, runtime, relay, onError: () => {} });

  try {
    // 1) Unresolved colleague, unresolved directory handle, external native conversation, and non-owner Feishu shadow all return structured not_sent and settle 'rejected'.
    store.aliasConversation('pa', 'c_feishu_group', 'external:pa:feishu:app:group:g1');
    for (const [idx, target, method] of [
      [1, 'user:colleague', 'send_message'],
      [2, 'bob_handle', 'send_message'],
      [3, 'conversation:c_external_group', 'send_message'],
      [4, 'conversation:c_external_group', 'send_user_message'],
      [5, 'c_feishu_group', 'send_message'],
    ] as const) {
      const opId = `op-priv-${idx}`;
      const call: ProductCall = {
        method,
        args: { target, text: 'Hello outside' },
        operationId: opId,
        callId: `call-${idx}`,
        sessionId: 'main',
        rootSessionId: 'main',
        agentId: 'pa',
        ownerId: 'owner',
      };
      const res = await pa.send(config, binding, call);
      expect(res).toMatchObject({
        status: 'not_sent',
        target,
        changed_reason: 'collaboration_scope_restricted',
      });
      expect(inbox.publication(opId)?.state).toBe('rejected');
    }

    // 2) Owner private chat still succeeds under owner_only!
    const okRes = await pa.send(config, binding, {
      method: 'send_message',
      args: { target: 'c_owner', text: 'Silent summary for owner' },
      operationId: 'op-owner-ok',
      callId: 'call-ok',
      sessionId: 'main',
      rootSessionId: 'main',
      agentId: 'pa',
      ownerId: 'owner',
    });
    expect(okRes).toMatchObject({ status: 'sent', message_id: 'm-owner' });

    // 3) InboxStore: tightening retires external participant observations while preserving pure observer observations!
    inbox.receive({
      agent_id: 'pa',
      conversation_id: 'c_ext_group',
      relay_task_id: 'obs-part',
      idempotency_key: 'obs-part',
      metadata: { pa_observation: true, personal_delivery: 'participant', conversation_type: 'group', addressed_to_agent: true },
      message: { id: 'm-part', content: '@PA help bob', sender_type: 'user', sender_user_id: 'bob', attachments: [] },
    }, true);
    inbox.receive({
      agent_id: 'pa',
      conversation_id: 'c_ext_group',
      relay_task_id: 'obs-silent',
      idempotency_key: 'obs-silent',
      metadata: { pa_observation: true, personal_delivery: 'observer', conversation_type: 'group', addressed_to_owner: true },
      message: { id: 'm-obs', content: '@Owner check this', sender_type: 'user', sender_user_id: 'bob', attachments: [] },
    }, true);

    inbox.restrict('pa', item => item.metadata.personal_delivery === 'observer' || !!item.metadata.owner_direct || !!item.metadata.owner_internal, true, undefined, snap => JSON.stringify(snap));
    const unread = inbox.check('pa', true);
    const summaryText = JSON.stringify(unread);
    expect(summaryText).toContain('c_ext_group');
    const readBatch = inbox.read('pa', 'main', 'call-read', { target: 'c_ext_group' }) as any;
    expect(JSON.stringify(readBatch.messages)).toContain('@Owner check this');
    expect(JSON.stringify(readBatch.messages)).not.toContain('@PA help bob');
  } finally {
    inbox.close();
    store.close();
  }
});
