import { createHash } from 'node:crypto';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { ChannelKey, type ProtocolFrame } from '@nano/channels';
import type { AgentConfiguration, RelayInput, RuntimePort } from '@nano/product-contracts';
import { chatDelivery } from '../src/attention.js';
import { ExternalChannels } from '../src/external.js';
import { ManagedChannels, type ChannelManifest, type ManagedChannel } from '../src/managed-channels.js';
import { SingleThread } from '../src/single-thread.js';
import { NodeStore } from '../src/store.js';

it('coexists Feishu and WeChat on the same Agent, awaits async runtime stop before restart, and purges disabled channels on removal', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'nano-managed-wx-'));
  const key = await ChannelKey.load(join(dir, 'key'));
  const dbPath = join(dir, 'channels.sqlite3');
  const events: string[] = [];
  const frames: ProtocolFrame[] = [];
  const purged: { channelId: string; agentId: string; provider: string }[] = [];
  let ready = true;

  const manager = new ManagedChannels(dbPath, {
    nodeId: 'node-1',
    ownerId: 'owner-1',
    key,
    hasAgent: id => id === 'pa-1',
    remove: (agentId, provider) => { events.push(`remove:${provider ?? 'all'}:${agentId}`); },
    purgeChannel: async info => { purged.push(info); events.push(`purge:${info.provider}:${info.channelId}`); },
    onError: () => {},
    relay: {
      get ready() { return ready; },
      async request(type, payload) {
        frames.push({ type, payload });
        return {
          type: 'result',
          payload: type === 'channel.reconcile.result'
            ? { head_outcome: 'accepted', removal_token_outcomes: [] }
            : { outcome: 'accepted' },
        };
      },
    },
    create: (item, secret, callbacks) => {
      if (item.provider === 'feishu') {
        expect(secret.app_secret).toBe('fs_sec');
      } else {
        expect(secret.bot_token).toBe('wx_tok');
      }
      return {
        async start() {
          events.push(`start:${item.provider}:${item.channel_revision}`);
          if (item.provider === 'wechat' && item.channel_revision === 2) {
            callbacks.status({
              state: 'failed',
              code: 'wechat_token_revoked',
              message: '微信登录已失效，请点击「重新扫码」恢复绑定',
            });
          } else {
            callbacks.status('ready');
          }
        },
        async stop() {
          events.push(`stopping:${item.provider}:${item.channel_revision}`);
          await new Promise(r => setTimeout(r, 25));
          events.push(`stopped:${item.provider}:${item.channel_revision}`);
        },
      };
    },
  });

  const feishuItem = (rev = 1): ManagedChannel => ({
    channel_id: 'ch_fs',
    agent_id: 'pa-1',
    node_id: 'node-1',
    provider: 'feishu',
    enabled: true,
    config: { app_id: 'cli_1' },
    provider_runtime: {},
    credential_key_id: key.registration.credential_key_id,
    credential_revision: rev,
    channel_revision: rev,
    provider_identity_revision: 1,
    provider_identity_fingerprint: createHash('sha256').update('feishu\0cli_1').digest('hex'),
    credential_envelope: key.seal({ app_secret: 'fs_sec' }, {
      owner_id: 'owner-1', node_id: 'node-1', agent_id: 'pa-1', channel_id: 'ch_fs', provider: 'feishu', credential_revision: rev,
    }),
  });

  const wechatItem = (rev = 1, enabled = true): ManagedChannel => ({
    channel_id: 'ch_wx',
    agent_id: 'pa-1',
    node_id: 'node-1',
    provider: 'wechat',
    enabled,
    config: { bot_id: 'wxbot_1', owner_user_id: 'wxid_owner', base_url: 'https://ilinkai.weixin.qq.com' },
    provider_runtime: {},
    credential_key_id: key.registration.credential_key_id,
    credential_revision: rev,
    channel_revision: rev,
    provider_identity_revision: 1,
    provider_identity_fingerprint: createHash('sha256').update('wechat\0wxbot_1\0wxid_owner').digest('hex'),
    credential_envelope: key.seal({ bot_token: 'wx_tok' }, {
      owner_id: 'owner-1', node_id: 'node-1', agent_id: 'pa-1', channel_id: 'ch_wx', provider: 'wechat', credential_revision: rev,
    }),
  });

  const reconcile = (rev: number, channels: ManagedChannel[], removals: ChannelManifest['removals'] = []) =>
    manager.handle({
      type: 'channel.reconcile',
      payload: {
        request_id: `req_${rev}`,
        node_id: 'node-1',
        owner_id: 'owner-1',
        manifest_revision: rev,
        channels,
        removals,
      } as unknown as Record<string, unknown>,
    });

  try {
    await reconcile(1, [feishuItem(1), wechatItem(1)]);
    expect(events).toEqual(['start:feishu:1', 'start:wechat:1']);

    // Rebind WeChat: old poller MUST finish async stop() before rev 2 starts, and Feishu stays untouched!
    events.length = 0;
    await reconcile(2, [feishuItem(1), wechatItem(2)]);
    expect(events).toEqual([
      'remove:wechat:pa-1',
      'stopping:wechat:1',
      'stopped:wechat:1',
      'start:wechat:2',
    ]);

    await manager.flush();
    const wxFailed = frames.find(f => f.type === 'channel.status' && f.payload.status_code === 'wechat_token_revoked');
    expect(wxFailed?.payload).toMatchObject({
      channel_id: 'ch_wx',
      connection_state: 'failed',
      status_code: 'wechat_token_revoked',
    });

    // Disable WeChat first (no longer in this.instances), then remove it: purgeChannel MUST still fire!
    await reconcile(3, [feishuItem(1), wechatItem(3, false)]);
    purged.length = 0;
    await reconcile(4, [feishuItem(1)], [
      { removal_token: 'rm_wx', channel_id: 'ch_wx', agent_id: 'pa-1', provider: 'wechat', deletion_manifest_revision: 4 },
    ]);
    expect(purged).toEqual([{ channelId: 'ch_wx', agentId: 'pa-1', provider: 'wechat' }]);
  } finally {
    ready = false;
    await manager.stop();
    await rm(dir, { recursive: true, force: true });
  }
});

it('routes WeChat shadow sessions, SingleThread source attribution, plain-text runtime footer, typing, and Global receipt gating', async () => {
  const store = new NodeStore(':memory:', 'owner-1');
  const submitted: unknown[] = [];
  const shadowCalls: { path: string; body: Record<string, unknown> }[] = [];
  const wechatSent: string[] = [];
  const typingStates: boolean[] = [];
  let reactionCalls = 0;

  const agentConfig: AgentConfiguration = {
    agentId: 'writer',
    displayName: 'Writer',
    workspace: '/tmp/writer',
    mode: 'single_thread',
    collaborationScope: 'owner_only',
    revision: 'rev1',
    provider: 'openai',
    model: 'gpt-5',
    modelFallbacks: [],
    features: {},
    approval: { rules: 'codex' },
  };

  let singleThread!: SingleThread;
  const external = new ExternalChannels(':memory:', {
    nodeId: 'node-1',
    ownerId: 'owner-1',
    store,
    runtimeFooter: provider => provider === 'wechat',
    ownerOnly: () => true,
    globalAgent: id => id === 'global-1',
    relay: {
      ready: true,
      async request(_type, payload) {
        return { type: 'ack', payload: { message_id: `im_${String(payload.idempotency_key ?? 'msg')}` } };
      },
    },
    im: async (path, init) => {
      const parsed = init?.body && typeof init.body === 'string' ? JSON.parse(init.body) as Record<string, unknown> : {};
      shadowCalls.push({ path, body: parsed });
      return { id: path.endsWith('find-or-create') ? 'shadow_wx_writer' : 'im_msg_1' };
    },
    receive: async input => {
      if (input.agent_id === 'writer') await singleThread.receive(input);
    },
    permission: async () => {},
    onError: err => { throw err; },
  });

  const runtime: RuntimePort = {
    onNotification: () => () => {},
    async request(method, params) {
      if (method === 'session.submit') submitted.push(params);
      if (method === 'session.lookup') return { accepted: false };
      if (method === 'session.observe') return { durable: true, events: [], modelRuns: [] };
      return {};
    },
  };

  singleThread = new SingleThread({
    nodeId: 'node-1',
    ownerId: 'owner-1',
    agents: [agentConfig],
    store,
    runtime,
    relay: external,
    image: async () => '',
    onError: err => { throw err; },
  });

  external.add('writer', {
    supportsReactions: false,
    supportsCards: false,
    config: { appId: 'wxbot_1', botOpenId: 'wxbot_1', ownerOpenId: 'wxid_owner' },
    async send(_chatId, text) { wechatSent.push(text); return 'wx_out_1'; },
    async setTyping(_chatId, active) { typingStates.push(active); },
    async reaction() { reactionCalls++; return 'unexpected'; },
    async image() { return { data: Buffer.alloc(0), mediaType: 'image/png' }; },
    async updateCard() {},
  }, 'wechat');

  external.add('global-1', {
    supportsReactions: false,
    supportsCards: false,
    config: { appId: 'wxbot_g', botOpenId: 'wxbot_g', ownerOpenId: 'wxid_owner' },
    async send() { return 'wx_out_g'; },
    async reaction() { reactionCalls++; return 'unexpected'; },
    async image() { return { data: Buffer.alloc(0), mediaType: 'image/png' }; },
    async updateCard() {},
  }, 'wechat');

  try {
    await external.receive('writer', {
      messageId: 'wx_in_1',
      chatId: 'wxid_owner',
      senderId: 'wxid_owner',
      isGroup: false,
      mentioned: true,
      time: String(Date.parse('2026-11-26T10:00:00Z')),
      parts: [{ type: 'text', text: '帮我总结今天重点' }],
    }, 'wechat');

    expect(reactionCalls).toBe(0);
    expect(typingStates).toContain(true);
    expect(shadowCalls[0]?.body).toMatchObject({
      external_source: 'wechat',
      external_chat_id: 'wechat:wxbot_1:dm:wxid_owner',
      title: 'writer · wechat',
    });

    // SingleThread source attribution & owner roleAccountId
    expect(submitted).toHaveLength(1);
    const submitCall = submitted[0] as { source: Record<string, unknown>; content: { type: string; text?: string }[] };
    expect(submitCall.source).toMatchObject({
      channel: 'wechat',
      roleAccountId: 'owner-1',
    });
    expect(String(submitCall.source.contextEnvelope)).toContain('source: WeChat.');

    // Complete reply: appends plain-text runtime footer on WeChat and stops typing
    const convId = 'external:writer:wechat:wxbot_1:dm:wxid_owner';
    const turnStart = await external.request('node.streaming_delta', {
      kind: 'turn_start',
      agent_id: 'writer',
      conversation_id: convId,
      idempotency_key: 'turn-wx-1',
      external_reply: 'external:writer:wechat:wxbot_1:wx_in_1',
    });
    await external.request('node.streaming_delta', {
      kind: 'message_completed',
      message_id: turnStart.payload.message_id,
      final_content: '这里是总结内容。',
      resolved_model: 'gpt-5',
      token_usage: { context_used: 20_000, context_window: 100_000 },
      delivery_status: 'completed',
    });

    expect(wechatSent).toEqual(['这里是总结内容。\n\n—\ngpt-5 · ctx 20%']);
    expect(typingStates.at(-1)).toBe(false);

    // Global Agent WeChat owner DM opts into IM agent_receipt without calling WeChat reactions,
    // and stages offline sent/read receipts until the shadow message is mirrored on reconnect.
    let globalInput: RelayInput | undefined;
    let online = false;
    const imReceiptFrames: Record<string, unknown>[] = [];
    const globalExternal = new ExternalChannels(':memory:', {
      nodeId: 'node-1',
      ownerId: 'owner-1',
      store,
      globalAgent: () => true,
      relay: {
        get ready() { return online; },
        async request(type, payload) {
          if (!online) throw new Error('offline');
          if (type === 'node.delivery_receipt') imReceiptFrames.push(payload);
          return { type: 'ack', payload: {} };
        },
      },
      im: async path => {
        if (!online) throw new Error('offline');
        return { id: path.endsWith('find-or-create') ? 'shadow_wx_global' : 'im_wx_g_1' };
      },
      receive: async input => { globalInput = input; },
      permission: async () => {},
      onError: () => {},
    });
    globalExternal.add('global-1', {
      supportsReactions: false,
      supportsCards: false,
      config: { appId: 'wxbot_g', botOpenId: 'wxbot_g', ownerOpenId: 'wxid_owner' },
      async send() { return 'ok'; },
      async reaction() { reactionCalls++; return 'unexpected'; },
      async image() { return { data: Buffer.alloc(0), mediaType: 'image/png' }; },
      async updateCard() {},
    }, 'wechat');
    await globalExternal.receive('global-1', {
      messageId: 'wx_g_1',
      chatId: 'wxid_owner',
      senderId: 'wxid_owner',
      isGroup: false,
      mentioned: true,
      time: '1700000000000',
      parts: [{ type: 'text', text: 'hi global' }],
    }, 'wechat');
    expect(globalInput?.metadata.agent_receipt).toBe(true);
    expect(reactionCalls).toBe(0);
    expect(chatDelivery(globalInput!, agentConfig, 'owner-1')).not.toBe('skip');

    await globalExternal.request('node.delivery_receipt', {
      relay_task_id: globalInput!.relay_task_id,
      delivery_status: 'sent',
    });
    await globalExternal.request('node.delivery_receipt', {
      relay_task_id: globalInput!.relay_task_id,
      delivery_status: 'read',
    });
    expect(reactionCalls).toBe(0);
    expect(imReceiptFrames).toEqual([]);

    online = true;
    await globalExternal.recover('global-1');
    expect(imReceiptFrames).toEqual([{
      node_id: 'node-1',
      agent_id: 'global-1',
      external_source_message_id: 'im_wx_g_1',
      delivery_status: 'read',
    }]);
    await globalExternal.stop();
  } finally {
    await singleThread.stop?.();
    await external.stop();
    store.close();
  }
});
