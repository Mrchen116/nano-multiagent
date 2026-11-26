import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { AgentConfiguration } from '@nano/product-contracts';
import { expect, it } from 'vitest';
import { ExternalChannels } from '../src/external.js';
import { GlobalAgent, type ProductCall } from '../src/global-agent.js';
import { InboxStore } from '../src/inbox.js';
import { NodeStore } from '../src/store.js';
import { TaskExecution } from '../src/task-execution.js';

const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64',
);

it('keeps Web-IM-shadow replies inside IM for PA and GlobalAgent, supports Feishu/WeChat local_images + receipt_of, and cleans up WeChat stops & approvals', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'nano-wx-routing-'));
  const imgPath = join(dir, 'plot.png');
  await writeFile(imgPath, TINY_PNG);

  const store = new NodeStore(':memory:', 'owner');
  const inbox = new InboxStore(':memory:');
  const wechatSent: { text: string; images?: number }[] = [];
  const feishuSent: { text: string; images?: number }[] = [];
  const shadowFrames: Record<string, unknown>[] = [];
  const runtimeBlocks: boolean[] = [];
  const permissions: Record<string, unknown>[] = [];
  let failNextWeChatSend = false;

  const paCfg: AgentConfiguration = {
    agentId: 'pa',
    mode: 'global',
    workspace: dir,
    revision: '1',
    provider: 'mock',
    model: 'mock-1',
    personal: { bindingId: 'b1', ownerId: 'owner', conversationId: 'c_pa_main', epoch: 1 },
  };
  const singleCfg: AgentConfiguration = {
    agentId: 'single',
    mode: 'single_thread',
    workspace: dir,
    revision: '1',
    provider: 'mock',
    model: 'mock-1',
    features: { task_graph: false },
  };

  let external!: ExternalChannels;
  const tasks = new TaskExecution({
    nodeId: 'n1',
    ownerId: 'owner',
    agents: [paCfg, singleCfg],
    store,
    runtime: {
      onNotification: () => () => {},
      request: async (method, params) => {
        if (method === 'task.execution.block') runtimeBlocks.push(Boolean((params as { blocked: boolean }).blocked));
        if (method === 'session.cancel') return { wasRunning: true };
        return {};
      },
    },
    relay: { request: (t, p) => external.request(t, p) },
    drain: async () => {},
    context: async () => ({ messages: [], revoked: [] }),
  });

  const global = new GlobalAgent({
    nodeId: 'n1',
    ownerId: 'owner',
    agents: [paCfg, singleCfg],
    store,
    inbox,
    runtime: {
      onNotification: () => () => {},
      request: async method => (method === 'session.work.children' ? { children: [] } : { events: [], durable: true, status: 'idle' }),
    },
    relay: { ready: true, request: (t, p) => external.request(t, p) },
    image: async () => '',
    stageExternalImage: input => external.stageOutboundImage(input),
    taskStop: (binding, input) => tasks.stop(binding, input),
    onError: err => { throw err; },
  });

  external = new ExternalChannels(':memory:', {
    nodeId: 'n1',
    ownerId: 'owner',
    store,
    personalAgent: id => id === 'pa',
    personalDelivery: delivery => delivery.dispatch(delivery.text, delivery.card),
    relay: {
      ready: true,
      request: async (type, payload) => {
        if (type === 'node.streaming_delta') {
          shadowFrames.push(payload);
          return { type: 'ack', payload: { message_type: type, message_id: `im_stream_${shadowFrames.length}`, conversation_id: String(payload.conversation_id ?? 'c_wx_shadow') } };
        }
        if (type === 'pa.source.admit') {
          const isWeb = String(payload.source_message_id).startsWith('m_web_');
          return { type: 'pa.source.admit.result', payload: { ok: true, result: { allowed: true, is_owner: true, delivery: 'participant', conversation_type: 'direct', channel: isWeb ? 'web' : 'wechat', owner_direct: true, addressed_to_agent: true } } };
        }
        if (type === 'pa.observations.read' || type === 'pa.incidents.pending') {
          return { type: `${type}.result`, payload: { ok: true, result: { items: [] } } };
        }
        if (type === 'task.execution.pause') {
          return { type: 'task.execution.pause.result', payload: { request_id: payload.request_id, ok: true, result: { paused: 0 } } };
        }
        return { type: 'ack', payload: { message_type: type, ok: true, result: {} } };
      },
    },
    im: async (path, options) => {
      if (path.endsWith('find-or-create')) return { id: String(options?.body ?? '').includes('feishu') ? 'c_fs_shadow' : 'c_wx_shadow' };
      if (path.includes('/images?')) return { url: '/im/v1/conversations/c_wx_shadow/images/img_1', content_type: 'image/png', file_name: 'plot.png' };
      return { id: 'm_wx_mirrored' };
    },
    receive: async () => {},
    permission: async payload => { permissions.push(payload); },
    onError: () => {},
  });

  external.add('pa', {
    supportsReactions: false,
    supportsCards: false,
    config: { appId: 'wxbot_pa', botOpenId: 'wxbot_pa', ownerOpenId: 'wxid_owner' },
    send: async (_chatId, text, _op, _card, images) => {
      if (failNextWeChatSend) {
        failNextWeChatSend = false;
        throw new Error('network timeout after send');
      }
      wechatSent.push({ text, images: images?.length });
      return `wx_msg_${wechatSent.length}`;
    },
    reaction: async () => undefined,
    image: async () => ({ data: TINY_PNG, mediaType: 'image/png' }),
    updateCard: async () => {},
  }, 'wechat');

  external.add('pa', {
    config: { appId: 'cli_pa', botOpenId: 'ou_bot', ownerOpenId: 'ou_owner' },
    send: async (_chatId, text, _op, _card, images) => {
      feishuSent.push({ text, images: images?.length });
      return `fs_msg_${feishuSent.length}`;
    },
    reaction: async () => undefined,
    image: async () => ({ data: TINY_PNG, mediaType: 'image/png' }),
    updateCard: async () => {},
  }, 'feishu');

  external.add('single', {
    supportsReactions: false,
    supportsCards: false,
    config: { appId: 'wxbot_single', botOpenId: 'wxbot_single', ownerOpenId: 'wxid_owner' },
    send: async (_chatId, text) => {
      wechatSent.push({ text });
      return `wx_single_${wechatSent.length}`;
    },
    reaction: async () => undefined,
    image: async () => ({ data: TINY_PNG, mediaType: 'image/png' }),
    updateCard: async () => {},
  }, 'wechat');

  try {
    await external.receive('pa', {
      messageId: 'wx_in_1',
      chatId: 'wxid_owner',
      senderId: 'wxid_owner',
      isGroup: false,
      mentioned: true,
      time: '1760000001000',
      parts: [{ type: 'text', text: '微信发来的问题' }],
      plainSingleText: true,
    }, 'wechat');
    await external.receive('pa', {
      messageId: 'fs_in_1',
      chatId: 'oc_owner',
      senderId: 'ou_owner',
      isGroup: false,
      mentioned: true,
      time: '1760000001500',
      parts: [{ type: 'text', text: '飞书发来的问题' }],
    }, 'feishu');

    const paBinding = store.bind({
      agentId: 'pa',
      sessionId: 'sess-pa',
      conversationId: 'global:pa',
      ownerId: 'owner',
      cwd: dir,
      revision: '1',
    });
    const sendCall = (operationId: string, args: Record<string, unknown>): ProductCall => ({
      method: 'send_message',
      args,
      operationId,
      callId: operationId,
      sessionId: paBinding.sessionId,
      rootSessionId: paBinding.sessionId,
      agentId: 'pa',
      ownerId: 'owner',
    });

    // PJ-F2: Owner sends inside Web IM shadow chat c_wx_shadow -> PA reply stays in IM ONLY!
    await global.receive({
      agent_id: 'pa',
      conversation_id: 'c_wx_shadow',
      relay_task_id: 'obs-web-1',
      idempotency_key: 'obs-web-1',
      metadata: { pa_observation: true, owner_direct: true, addressed_to_agent: true, conversation_type: 'direct', channel: 'web' },
      message: { id: 'm_web_1', content: '在网页端影子会话追问', sender_type: 'user', sender_user_id: 'owner', attachments: [] },
    });
    const page1 = inbox.read('pa', paBinding.sessionId, 'read-web-1', { target: 'c_wx_shadow' });
    inbox.commitRead(paBinding.sessionId, 'read-web-1', [{ type: 'text', text: JSON.stringify(page1) }], false, 1);

    const webShadowReply = await global.call(sendCall('sess-pa:web-only', { target: 'c_wx_shadow', text: '仅网页端可见回复' }));
    expect(webShadowReply).toMatchObject({ status: 'sent' });
    expect(wechatSent).toHaveLength(0);
    expect(shadowFrames.some(f => f.kind === 'message_completed' && f.final_content === '仅网页端可见回复')).toBe(true);

    // Next, owner sends from WeChat -> PA reply with local_images goes to WeChat + shadow!
    await global.receive({
      agent_id: 'pa',
      conversation_id: 'c_wx_shadow',
      relay_task_id: 'obs-wx-2',
      idempotency_key: 'obs-wx-2',
      metadata: { pa_observation: true, owner_direct: true, addressed_to_agent: true, conversation_type: 'direct', channel: 'wechat' },
      message: { id: 'm_wx_2', content: '发张图给我', sender_type: 'user', sender_user_id: 'wxid_owner', attachments: [] },
    });
    const page2 = inbox.read('pa', paBinding.sessionId, 'read-wx-2', { target: 'c_wx_shadow' });
    inbox.commitRead(paBinding.sessionId, 'read-wx-2', [{ type: 'text', text: JSON.stringify(page2) }], false, 2);

    // CR-F1 & CR-F2: unknown local_images receipt + confirmed receipt_of recovery on WeChat & Feishu
    failNextWeChatSend = true;
    const unknownRes = await global.call(sendCall('sess-pa:wx-img-unknown', {
      target: 'c_wx_shadow', text: '这是趋势图', local_images: [imgPath],
    })) as { status: string; operation_id: string };
    expect(unknownRes.status).toBe('unknown');

    const stillUnknown = await global.call(sendCall('sess-pa:wx-img-check', {
      target: 'c_wx_shadow', receipt_of: unknownRes.operation_id,
    })) as { status: string };
    expect(stillUnknown.status).toBe('unknown');

    const wxSentRes = await global.call(sendCall('sess-pa:wx-img-ok', {
      target: 'c_wx_shadow', text: '微信附图成功', local_images: [imgPath],
    }));
    expect(wxSentRes).toMatchObject({ status: 'sent' });
    expect(wechatSent).toEqual([{ text: '微信附图成功', images: 1 }]);

    const wxReceipt = await global.call(sendCall('sess-pa:wx-img-receipt', {
      target: 'c_wx_shadow', receipt_of: 'sess-pa:wx-img-ok',
    }));
    expect(wxReceipt).toMatchObject({ status: 'sent' });
    expect(wechatSent).toHaveLength(1);

    const fsSentRes = await global.call(sendCall('sess-pa:fs-img-ok', {
      target: store.toolReferences.conversationRef('pa', 'external:pa:feishu:cli_pa:dm:ou_owner'),
      text: '飞书附图成功',
      local_images: [imgPath],
    }));
    expect(fsSentRes).toMatchObject({ status: 'sent' });
    expect(feishuSent).toEqual([{ text: '飞书附图成功', images: 1 }]);

    // PJ-F1: SingleThread /stop with task_graph: false completes cleanly and releases execution block!
    const singleBinding = store.bind({
      agentId: 'single',
      sessionId: 'sess-single',
      conversationId: 'external:single:wechat:wxbot_single:dm:wxid_owner',
      ownerId: 'owner',
      cwd: dir,
      revision: '1',
    });
    const stopRes = await tasks.stop(singleBinding, {
      agent_id: 'single',
      conversation_id: singleBinding.conversationId,
      relay_task_id: 'ext-stop-1',
      idempotency_key: 'ext-stop-1',
      metadata: { channel: 'wechat', owner_direct: true },
      message: { id: 'external:single:wechat:wxbot_single:stop_1', content: '/stop', sender_type: 'user', sender_user_id: 'wxid_owner', attachments: [] },
    });
    expect(stopRes).toEqual({ wasRunning: true, paused: 0 });
    expect(runtimeBlocks).toEqual([true, false]);

    // CR-F3, CR-F4 & CR-F9: tool_input summary, cancelAgent approval cleanup, and inline data URI stripping
    await external.receive('single', {
      messageId: 'wx_s_1',
      chatId: 'wxid_owner',
      senderId: 'wxid_owner',
      isGroup: false,
      mentioned: true,
      time: '1760000003000',
      parts: [{ type: 'text', text: '跑一下部署脚本' }],
      plainSingleText: true,
    }, 'wechat');
    const turn = await external.request('node.streaming_delta', {
      kind: 'turn_start',
      agent_id: 'single',
      conversation_id: 'external:single:wechat:wxbot_single:dm:wxid_owner',
      idempotency_key: 'turn-s-1',
      external_reply: 'external:single:wechat:wxbot_single:wx_s_1',
    });
    await external.request('node.streaming_delta', {
      kind: 'permission_request',
      run_id: 'run-s-1',
      message_id: String(turn.payload.message_id),
      permission_request: {
        request_id: 'perm-1',
        tool_name: 'bash',
        reason: 'Permission required for bash',
        tool_input: { command: 'rm -rf ./dist && pnpm build' },
      },
    });
    expect(wechatSent.at(-1)?.text).toContain('command: rm -rf ./dist && pnpm build');

    external.cancelAgent('single');
    let normalTurnInputs = 0;
    (external as unknown as { options: { receive: () => Promise<void> } }).options.receive = async () => { normalTurnInputs++; };
    await external.receive('single', {
      messageId: 'wx_s_2',
      chatId: 'wxid_owner',
      senderId: 'wxid_owner',
      isGroup: false,
      mentioned: true,
      time: '1760000004000',
      parts: [{ type: 'text', text: '1' }],
      plainSingleText: true,
    }, 'wechat');
    expect(permissions).toHaveLength(0);
    expect(normalTurnInputs).toBe(1);

    await external.request('node.streaming_delta', {
      kind: 'message_completed',
      message_id: String(turn.payload.message_id),
      external_reply: 'external:single:wechat:wxbot_single:wx_s_1',
      final_content: `结果如下：\n\n![chart](data:image/png;base64,${TINY_PNG.toString('base64')})`,
      delivery_status: 'completed',
    });
    await new Promise(r => setTimeout(r, 50));
    const mirroredComplete = shadowFrames.findLast(f => f.kind === 'message_completed' && String(f.final_content ?? '').includes('结果如下'));
    expect(String(mirroredComplete?.final_content)).not.toContain('data:image/');
  } finally {
    await external.stop();
    await global.stop();
    inbox.close();
    store.close();
    await rm(dir, { recursive: true, force: true });
  }
});
