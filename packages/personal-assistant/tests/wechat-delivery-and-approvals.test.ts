import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import type { ProtocolFrame } from '@nano/channels';
import type { RelayInput } from '@nano/product-contracts';
import { ExternalChannels } from '../src/external.js';
import { NodeStore } from '../src/store.js';

const SAMPLE_PNG_BASE64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';

async function createSamplePng(filePath: string): Promise<Buffer> {
  const bytes = Buffer.from(SAMPLE_PNG_BASE64, 'base64');
  await writeFile(filePath, bytes);
  return bytes;
}

it('stages local outbound images for offline WeChat delivery and syncs shadow attachments once IM reconnects', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'nano-wx-outbound-img-'));
  const store = new NodeStore(join(dir, 'node.sqlite3'), 'owner-1');
  const sentToWeChat: { chatId: string; text: string; operationId: string; images?: { data: Buffer; mediaType: string }[] }[] = [];
  const imUploads: { path: string; bytes: number }[] = [];
  const streamFrames: Record<string, unknown>[] = [];
  let relayReady = false;

  const external = new ExternalChannels(join(dir, 'external.sqlite3'), {
    nodeId: 'node-1',
    ownerId: 'owner-1',
    store,
    relay: {
      get ready() { return relayReady; },
      async request(type, payload): Promise<ProtocolFrame> {
        if (type === 'node.streaming_delta') {
          streamFrames.push(payload);
          if (payload.kind === 'turn_start') {
            return { type: 'ack', payload: { message_type: type, message_id: `im_msg_${streamFrames.length}`, conversation_id: 'c_wx_shadow' } };
          }
        }
        return { type: 'ack', payload: { message_type: type } };
      },
    },
    im: async (path, options) => {
      if (path.startsWith('/im/v1/conversations/external/find-or-create')) {
        return { id: 'c_wx_shadow' };
      }
      if (path.includes('/images?')) {
        const body = options?.body as Uint8Array;
        imUploads.push({ path, bytes: body.byteLength });
        return {
          url: `/im/v1/conversations/c_wx_shadow/images/img_${imUploads.length}`,
          content_type: 'image/png',
          file_name: 'chart.png',
        };
      }
      return { id: `im_in_${Date.now()}` };
    },
    receive: async () => {},
    permission: async () => {},
    onError: () => {},
  });

  try {
    external.add('eng-1', {
      supportsReactions: false,
      supportsCards: false,
      config: { appId: 'bot_1', botOpenId: 'bot_1', ownerOpenId: 'wxid_owner' },
      send: async (chatId, text, operationId, _card, images) => {
        sentToWeChat.push({ chatId, text, operationId, ...(images?.length ? { images } : {}) });
        return `wx_out_${sentToWeChat.length}`;
      },
      reaction: async () => undefined,
      image: async () => ({ data: Buffer.alloc(0), mediaType: 'image/png' }),
      updateCard: async () => {},
    }, 'wechat');

    // Inbound establishes WeChat chat while IM is offline!
    await external.receive('eng-1', {
      messageId: 'wx_in_1',
      chatId: 'wxid_owner',
      senderId: 'wxid_owner',
      isGroup: false,
      mentioned: true,
      time: '1700000010000',
      parts: [{ type: 'text', text: '发我最新的统计图' }],
      plainSingleText: true,
    }, 'wechat');

    const localPngPath = join(dir, 'chart.png');
    const pngBytes = await createSamplePng(localPngPath);

    // Stage local image offline & publish explicit `agent.message` while IM is still offline!
    const staged = await external.stageOutboundImage({
      agentId: 'eng-1',
      conversationId: 'external:eng-1:wechat:bot_1:dm:wxid_owner',
      operationId: 'op_img_1',
      index: 0,
      path: localPngPath,
      lifecycleRevision: 1,
      signal: new AbortController().signal,
    });
    expect(staged.url).toBe('external:out:op_img_1:0');

    const pubAck = await external.request('agent.message', {
      node_id: 'node-1',
      from_session_id: 'eng-1|tool_call:op_img_1',
      to: 'conversation:external:eng-1:wechat:bot_1:dm:wxid_owner',
      text: '这是统计图',
      attachments: [staged],
      lifecycle_revision: 1,
    });
    expect(pubAck.payload.message_id).toBe('wx_out_1');
    // Delivered immediately to WeChat with real PNG bytes despite IM being offline!
    expect(sentToWeChat).toHaveLength(1);
    expect(sentToWeChat[0]!.images).toHaveLength(1);
    expect(sentToWeChat[0]!.images![0]!.data.equals(pngBytes)).toBe(true);
    expect(imUploads).toHaveLength(0);

    // Also test inline data:image/png;base64,... extraction on normal assistant turn completion!
    const inlineTurn = await external.request('node.streaming_delta', {
      kind: 'turn_start',
      agent_id: 'eng-1',
      conversation_id: 'external:eng-1:wechat:bot_1:dm:wxid_owner',
      idempotency_key: 'turn_inline_1',
      external_reply: 'external:eng-1:wechat:bot_1:wx_in_1',
    });
    await external.request('node.streaming_delta', {
      kind: 'message_completed',
      message_id: String(inlineTurn.payload.message_id),
      final_content: `内联截图如下：\n![preview](data:image/png;base64,${pngBytes.toString('base64')})`,
      delivery_status: 'completed',
    });
    expect(sentToWeChat).toHaveLength(2);
    expect(sentToWeChat[1]!.images).toHaveLength(1);
    expect(sentToWeChat[1]!.images![0]!.data.equals(pngBytes)).toBe(true);

    // Now IM comes online -> recover() flushes inbound mirror + uploads staged outbound images + completes shadow frames!
    relayReady = true;
    await external.recover();
    expect(imUploads).toHaveLength(2);
    const completedFrames = streamFrames.filter(f => f.kind === 'message_completed');
    expect(completedFrames).toHaveLength(2);
    expect(completedFrames[0]!.attachments).toEqual([
      { url: '/im/v1/conversations/c_wx_shadow/images/img_1', content_type: 'image/png', file_name: 'chart.png' },
    ]);
  } finally {
    await external.stop();
    store.close();
    await rm(dir, { recursive: true, force: true });
  }
});

it('arbitrates SingleThread WeChat plain-text tool approvals mutually exclusively with IM cards and clears stale approvals on turn end', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'nano-wx-approvals-'));
  const store = new NodeStore(join(dir, 'node.sqlite3'), 'owner-1');
  const sentToWeChat: string[] = [];
  const admittedTurns: RelayInput[] = [];
  const permissions: Record<string, unknown>[] = [];

  const external = new ExternalChannels(join(dir, 'external.sqlite3'), {
    nodeId: 'node-1',
    ownerId: 'owner-1',
    store,
    relay: {
      ready: true,
      async request(type, payload): Promise<ProtocolFrame> {
        if (type === 'node.streaming_delta' && payload.kind === 'turn_start') {
          return { type: 'ack', payload: { message_type: type, message_id: 'im_turn_1', conversation_id: 'c_wx_st' } };
        }
        return { type: 'ack', payload: { message_type: type } };
      },
    },
    im: async path => (path.startsWith('/im/v1/conversations/external/find-or-create') ? { id: 'c_wx_st' } : { id: `m_${Date.now()}` }),
    receive: async input => { admittedTurns.push(input); },
    permission: async payload => { permissions.push(payload); },
    onError: () => {},
  });

  try {
    external.add('st-1', {
      supportsReactions: false,
      supportsCards: false,
      config: { appId: 'bot_st', botOpenId: 'bot_st', ownerOpenId: 'wxid_owner' },
      send: async (_chatId, text) => {
        sentToWeChat.push(text);
        return `wx_sent_${sentToWeChat.length}`;
      },
      reaction: async () => undefined,
      image: async () => ({ data: Buffer.alloc(0), mediaType: 'image/png' }),
      updateCard: async () => {},
    }, 'wechat');

    // 1. Initial user message starts turn 1
    await external.receive('st-1', {
      messageId: 'm1',
      chatId: 'wxid_owner',
      senderId: 'wxid_owner',
      isGroup: false,
      mentioned: true,
      time: '1700000001000',
      parts: [{ type: 'text', text: '部署测试环境' }],
      plainSingleText: true,
    }, 'wechat');
    expect(admittedTurns).toHaveLength(1);

    const turnStart = await external.request('node.streaming_delta', {
      kind: 'turn_start',
      agent_id: 'st-1',
      conversation_id: 'external:st-1:wechat:bot_st:dm:wxid_owner',
      idempotency_key: 'turn_1',
      external_reply: 'external:st-1:wechat:bot_st:m1',
    });
    const outMsgId = String(turnStart.payload.message_id);

    // 2. SingleThread requests tool approval -> WeChat receives prompt
    await external.request('node.streaming_delta', {
      kind: 'permission_request',
      message_id: outMsgId,
      run_id: 'sess_1',
      agent_id: 'st-1',
      permission_request: {
        request_id: 'req_1',
        tool_name: 'bash',
        reason: '执行 ./deploy.sh',
      },
    });
    expect(sentToWeChat.at(-1)).toContain('【待确认操作】bash');

    // 3. Forwarded/XML text (`plainSingleText: false`) with "1" MUST NOT trigger approval!
    await external.receive('st-1', {
      messageId: 'm_forwarded_1',
      chatId: 'wxid_owner',
      senderId: 'wxid_owner',
      isGroup: false,
      mentioned: true,
      time: '1700000002000',
      parts: [{ type: 'text', text: '1' }],
      plainSingleText: false,
    }, 'wechat');
    expect(permissions).toHaveLength(0);
    expect(admittedTurns).toHaveLength(2);

    // 4. Plain single text "1" approves req_1 without creating a model turn!
    await external.receive('st-1', {
      messageId: 'm_approve_1',
      chatId: 'wxid_owner',
      senderId: 'wxid_owner',
      isGroup: false,
      mentioned: true,
      time: '1700000003000',
      parts: [{ type: 'text', text: '1' }],
      plainSingleText: true,
    }, 'wechat');
    expect(permissions).toEqual([
      { request_id: 'req_1', decision: 'allow_once', agent_id: 'st-1', lifecycle_revision: 1 },
    ]);
    expect(admittedTurns).toHaveLength(2);
    expect(sentToWeChat.at(-1)).toContain('已允许');

    // 5. Duplicate "允许" while turn is still running returns idempotent notice without re-invoking permission()
    await external.receive('st-1', {
      messageId: 'm_dup_approve',
      chatId: 'wxid_owner',
      senderId: 'wxid_owner',
      isGroup: false,
      mentioned: true,
      time: '1700000004000',
      parts: [{ type: 'text', text: '允许' }],
      plainSingleText: true,
    }, 'wechat');
    expect(permissions).toHaveLength(1);
    expect(admittedTurns).toHaveLength(2);
    expect(sentToWeChat.at(-1)).toContain('已处理');

    // 6. Second tool approval in same turn settled from IM card first -> notifies WeChat, then turn completes
    await external.request('node.streaming_delta', {
      kind: 'permission_request',
      message_id: outMsgId,
      run_id: 'sess_1',
      agent_id: 'st-1',
      permission_request: {
        request_id: 'req_2',
        tool_name: 'bash',
        reason: '重启服务',
      },
    });
    await external.request('node.streaming_delta', {
      kind: 'permission_resolved',
      message_id: outMsgId,
      request_id: 'req_2',
      decision: 'deny',
    });
    expect(sentToWeChat.at(-1)).toContain('内部 IM 处理');

    await external.request('node.streaming_delta', {
      kind: 'message_completed',
      message_id: outMsgId,
      final_content: '操作已结束，请选择后续方案 1 或 2。',
      delivery_status: 'completed',
    });

    // 7. After turn completion, user replying "1" is NOT swallowed by closed approvals!
    await external.receive('st-1', {
      messageId: 'm_normal_choice',
      chatId: 'wxid_owner',
      senderId: 'wxid_owner',
      isGroup: false,
      mentioned: true,
      time: '1700000006000',
      parts: [{ type: 'text', text: '1' }],
      plainSingleText: true,
    }, 'wechat');
    expect(admittedTurns).toHaveLength(3);
    expect(admittedTurns[2]!.message.content).toBe('1');
  } finally {
    await external.stop();
    store.close();
    await rm(dir, { recursive: true, force: true });
  }
});
