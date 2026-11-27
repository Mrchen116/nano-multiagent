import { expect, it } from 'vitest';
import type { AgentConfiguration } from '@nano/product-contracts';
import { ExternalChannels } from '../src/external.js';
import { SingleThread } from '../src/single-thread.js';
import { NodeStore } from '../src/store.js';
import { prepareLocalAttachments } from '../src/screenshot-delivery.js';

it('admits project_allowed SingleThread chats while isolating revokeConversations per conversation and scoping local_path to PA review', async () => {
  const store = new NodeStore(':memory:', 'owner');
  const config: AgentConfiguration = {
    agentId: 'proj',
    revision: '1',
    model: 'test',
    provider: 'test',
    mode: 'single_thread',
    workspace: '/tmp',
    collaborationScope: 'project',
  };
  const submissions: Array<{ sessionId: string; inputId: string }> = [];
  const receipts: Array<Record<string, unknown>> = [];
  let releaseGroup1!: () => void;
  const group1Gate = new Promise<void>(resolve => { releaseGroup1 = resolve; });
  let group1Blocked = true;

  const product = new SingleThread({
    nodeId: 'n',
    ownerId: 'owner',
    store,
    agents: [config],
    onError: error => { throw error; },
    image: async () => 'img',
    relay: {
      async request(type, frame) {
        if (type === 'node.delivery_receipt') receipts.push(frame);
        return { type: 'ack', payload: { message_id: 'm' } };
      },
    },
    runtime: {
      onNotification: () => () => {},
      async request(method, params) {
        if (method === 'session.ensure' && group1Blocked) {
          group1Blocked = false;
          await group1Gate;
        }
        if (method === 'session.submit') submissions.push(params as any);
        if (method === 'session.lookup') return { accepted: submissions.some(item => item.inputId === (params as { inputId: string }).inputId) };
        return { durable: true, events: [] };
      },
    },
  });

  try {
    await product.receive({
      agent_id: 'proj',
      conversation_id: 'c_outsider_dm',
      relay_task_id: 'r-outsider',
      idempotency_key: 'r-outsider',
      message: { id: 'm-outsider', content: 'Hi from outsider', sender_type: 'user', sender_user_id: 'charlie', attachments: [], created_at: '2026-11-27T10:00:00Z' },
      metadata: { conversation_type: 'direct', owner_direct: false, owner_internal: false, project_allowed: false },
    });
    expect(submissions).toHaveLength(0);
    expect(receipts.at(-1)).toMatchObject({ relay_task_id: 'r-outsider', delivery_status: 'skipped' });

    const inFlightGroup1 = product.receive({
      agent_id: 'proj',
      conversation_id: 'c_group_1',
      relay_task_id: 'r-g1-first',
      idempotency_key: 'r-g1-first',
      message: { id: 'm-g1-first', content: '<mention type="user" target_id="u-proj"/> status', sender_type: 'user', sender_user_id: 'bob', attachments: [], created_at: '2026-11-27T10:01:00Z' },
      metadata: { conversation_type: 'group', owner_direct: false, owner_internal: false, project_allowed: true, addressed_to_agent: true, agent_user_id: 'u-proj' },
    });
    const queuedGroup1Second = product.receive({
      agent_id: 'proj',
      conversation_id: 'c_group_1',
      relay_task_id: 'r-g1-second',
      idempotency_key: 'r-g1-second',
      message: { id: 'm-g1-second', content: '<mention type="user" target_id="u-proj"/> follow-up', sender_type: 'user', sender_user_id: 'bob', attachments: [], created_at: '2026-11-27T10:01:05Z' },
      metadata: { conversation_type: 'group', owner_direct: false, owner_internal: false, project_allowed: true, addressed_to_agent: true, agent_user_id: 'u-proj' },
    });

    product.revokeConversations('proj', ['c_group_2']);
    releaseGroup1();
    await Promise.all([inFlightGroup1, queuedGroup1Second]);
    expect(submissions.map(s => s.inputId)).toEqual(['proj:m-g1-first', 'proj:m-g1-second']);

    const defaultPrepared = await prepareLocalAttachments(
      async ({ path }) => ({ url: '/im/v1/conversations/c/images/img1', content_type: 'image/png', file_name: path.split('/').pop()! }),
      async ({ path }) => ({ url: '/im/v1/conversations/c/attachments/file1', content_type: 'application/pdf', file_name: path.split('/').pop()! }),
      { agentId: 'pa', conversationId: 'c', operationId: 'op-0', lifecycleRevision: 1, signal: new AbortController().signal },
      ['/Users/owner/diagram.png'],
      ['/Users/owner/spec.pdf'],
      undefined,
    );
    expect(defaultPrepared).toEqual([
      { url: '/im/v1/conversations/c/images/img1', content_type: 'image/png', file_name: 'diagram.png' },
      { url: '/im/v1/conversations/c/attachments/file1', content_type: 'application/pdf', file_name: 'spec.pdf' },
    ]);
    const prepared = await prepareLocalAttachments(
      async ({ path }) => ({ url: '/im/v1/conversations/c/images/img1', content_type: 'image/png', file_name: path.split('/').pop()! }),
      async ({ path }) => ({ url: '/im/v1/conversations/c/attachments/file1', content_type: 'application/pdf', file_name: path.split('/').pop()! }),
      { agentId: 'pa', conversationId: 'c', operationId: 'op-1', lifecycleRevision: 1, signal: new AbortController().signal },
      ['/Users/owner/diagram.png'],
      ['/Users/owner/spec.pdf'],
      undefined,
      { includeLocalPath: true },
    );
    expect(prepared).toEqual([
      { url: '/im/v1/conversations/c/images/img1', content_type: 'image/png', file_name: 'diagram.png', local_path: '/Users/owner/diagram.png' },
      { url: '/im/v1/conversations/c/attachments/file1', content_type: 'application/pdf', file_name: 'spec.pdf', local_path: '/Users/owner/spec.pdf' },
    ]);
  } finally {
    await product.stop();
    store.close();
  }
});

it('surfaces Project scope rather than Private in ExternalChannels outbound restriction errors', async () => {
  const store = new NodeStore(':memory:', 'owner');
  let scope: 'team' | 'project' | 'owner_only' = 'project';
  const external = new ExternalChannels(':memory:', {
    nodeId: 'n',
    ownerId: 'owner',
    store,
    collaborationScope: () => scope,
    relay: { ready: true, request: async () => ({ type: 'ack', payload: {} } as never) },
    im: async () => ({}),
    receive: async () => {},
    permission: async () => {},
    onError: () => {},
  });
  try {
    await expect(
      external.request('agent.message', {
        node_id: 'n',
        from_session_id: 'proj|tool_call:op-ext-1',
        to: 'external:proj:app1:oc_group',
        text: 'hello external group',
      }),
    ).rejects.toThrow(/Project scope/);
    scope = 'owner_only';
    await expect(
      external.request('agent.message', {
        node_id: 'n',
        from_session_id: 'proj|tool_call:op-ext-2',
        to: 'external:proj:app1:oc_group',
        text: 'hello external group',
      }),
    ).rejects.toThrow(/set to Private/);
  } finally {
    await external.stop();
    store.close();
  }
});
