import { generateKeyPairSync } from 'node:crypto';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { ExternalChannels } from '../../../packages/personal-assistant/src/external.js';
import { GlobalAgent } from '../../../packages/personal-assistant/src/global-agent.js';
import { InboxStore } from '../../../packages/personal-assistant/src/inbox.js';
import { NodeStore } from '../../../packages/personal-assistant/src/store.js';
import { requestIm } from '../../node/src/im-http.js';
import type { Connection } from '../src/gateway.js';
import { createServer } from '../src/server.js';

function testPublicKeyBase64(): string {
  const { publicKey } = generateKeyPairSync('x25519');
  const jwk = publicKey.export({ format: 'jwk' });
  return Buffer.from(jwk.x!, 'base64url').toString('base64');
}

it('tracks sent -> received -> read double-checkmark receipts on owner 1:1 WeChat shadow chats for PA and Global Agent while excluding groups, non-owners, and SingleThread', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'nano-im-wechat-receipts-'));
  const app = await createServer({
    dbPath: join(dir, 'im.sqlite3'),
    uploadDir: join(dir, 'uploads'),
    publicUrl: 'http://127.0.0.1',
    jwtSecret: 'isolated-wechat-receipts-secret',
  });
  const store = new NodeStore(join(dir, 'node.sqlite3'), 'owner');
  const inbox = new InboxStore(join(dir, 'inbox.sqlite3'));
  let external: ExternalChannels | undefined;
  let globalProduct: GlobalAgent | undefined;

  try {
    const { db } = app.im;
    const now = new Date().toISOString();
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status,personal_space_enabled) VALUES('owner','owner','Owner','owner',?,'active',1)").run(now);
    app.im.identity.authenticateRequest = () => app.im.identity.user('owner')!;
    db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('node','owner','Node','online')").run();
    db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch) VALUES('node','owner',1)").run();
    db.prepare("INSERT INTO node_credential_keys(node_id,owner_id,key_id,algorithm,public_key,updated_at) VALUES('node','owner','key-1','X25519-HKDF-SHA256-AES-256-GCM',?,?)").run(testPublicKeyBase64(), now);

    for (const [id, displayName, mode, space] of [
      ['pa_main', 'PA · 个人助手', 'global', 'personal:owner'],
      ['global_bot', '周报助手', 'global', 'company:default'],
      ['single_bot', 'SingleBot', 'single_thread', 'company:default'],
    ] as const) {
      db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,workspace_root,work_mode,collaboration_scope,space_id,created_at,updated_at) VALUES(?,?,?,?, '/ws',?,'team',?,?,?)")
        .run(id, 'owner', 'node', displayName, mode, space, now, now);
      app.im.messaging.agentUser(id);
    }

    db.prepare("INSERT INTO conversations(id,title,type,owner_id,space_id,config_agent_id,created_at) VALUES('owner-chat','PA','direct','owner','personal:owner','pa_main',?)").run(now);
    db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('owner-chat','owner')").run();
    db.prepare("INSERT INTO personal_agent_bindings VALUES('binding','owner','owner','pa_main','node',1,'owner-chat','PA','create','active',NULL,?)").run(now);
    db.prepare("INSERT INTO pa_policies(binding_id) VALUES('binding')").run();

    for (const [cid, aid, provider, cfg] of [
      ['ch_pa', 'pa_main', 'wechat', { bot_id: 'wxbot_pa@im.bot', owner_user_id: 'wxid_owner@im.wechat', base_url: 'https://ilinkai.weixin.qq.com' }],
      ['ch_global', 'global_bot', 'wechat', { bot_id: 'wxbot_g@im.bot', owner_user_id: 'wxid_owner@im.wechat', base_url: 'https://ilinkai.weixin.qq.com' }],
      ['ch_single', 'single_bot', 'wechat', { bot_id: 'wxbot_s@im.bot', owner_user_id: 'wxid_owner@im.wechat', base_url: 'https://ilinkai.weixin.qq.com' }],
      ['ch_feishu', 'global_bot', 'feishu', { app_id: 'cli_fs', owner_open_id: 'ou_owner' }],
    ] as const) {
      db.prepare(`INSERT INTO agent_channels(channel_id,owner_id,agent_id,node_id,provider,enabled,config_json,provider_identity_fingerprint,provider_identity_revision,provider_runtime_json,credential_envelope_json,credential_key_id,credential_revision,channel_revision,created_at,updated_at)
        VALUES(?,'owner',?,'node',?,1,?,?,1,'{}','{}','key-1',1,1,?,?)`).run(cid, aid, provider, JSON.stringify(cfg), `fp_${cid}`, now, now);
    }

    const fakeConn = {
      node_id: 'node',
      owner_id: 'owner',
      node_epoch: 1,
      token: 'gateway-token',
      socket: { readyState: 1, bufferedAmount: 0, send() {}, close() {} },
    } as unknown as Connection;
    app.im.gateway.nodes.set('node', fakeConn);

    const base = await app.listen({ host: '127.0.0.1', port: 0 });
    const relayBridge = {
      ready: true,
      async request(type: string, payload: Record<string, unknown>) {
        return await app.im.gateway.handle(fakeConn, type, payload) as { type: string; payload: Record<string, unknown> };
      },
    };

    const wakeInputs: string[] = [];
    external = new ExternalChannels(join(dir, 'external.sqlite3'), {
      nodeId: 'node',
      ownerId: 'owner',
      store,
      relay: relayBridge,
      agentName: id => ({ pa_main: 'PA · 个人助手', global_bot: '周报助手', single_bot: 'SingleBot' } as Record<string, string>)[id],
      personalAgent: id => id === 'pa_main',
      globalAgent: id => id === 'global_bot',
      im: (path, init) => requestIm(base, 'gateway-token', path, init),
      receive: async input => {
        if (input.agent_id === 'global_bot') await globalProduct!.receive(input);
      },
      permission: async () => {},
      onError: err => { throw err; },
    });

    globalProduct = new GlobalAgent({
      nodeId: 'node',
      ownerId: 'owner',
      store,
      inbox,
      agents: [
        {
          agentId: 'pa_main',
          workspace: dir,
          revision: '1',
          provider: 'openai',
          model: 'gpt-5',
          mode: 'global',
          personal: { bindingId: 'binding', ownerId: 'owner', conversationId: 'owner-chat', epoch: 1 },
        },
        {
          agentId: 'global_bot',
          workspace: dir,
          revision: '1',
          provider: 'openai',
          model: 'gpt-5',
          mode: 'global',
        },
      ],
      relay: external,
      runtime: {
        onNotification: () => () => {},
        async request(method, args: Record<string, unknown>) {
          if (method === 'session.ensure') return { sessionId: args.sessionId };
          if (method === 'session.lookup') return { accepted: false };
          if (method === 'session.submit') {
            wakeInputs.push(String(args.inputId));
            return { accepted: true, durable: true };
          }
          if (method === 'session.work.children') return { children: [] };
          return { durable: true, events: [], status: 'idle' };
        },
      },
      image: async () => '',
      onError: err => { throw err; },
    });

    for (const [aid, botId] of [
      ['pa_main', 'wxbot_pa@im.bot'],
      ['global_bot', 'wxbot_g@im.bot'],
      ['single_bot', 'wxbot_s@im.bot'],
    ] as const) {
      external.add(aid, {
        supportsReactions: false,
        supportsCards: false,
        config: { appId: botId, botOpenId: botId, ownerOpenId: 'wxid_owner@im.wechat' },
        async send() { return 'ok'; },
        async reaction() { return undefined; },
        async image() { return { data: Buffer.alloc(0), mediaType: 'image/png' }; },
        async updateCard() {},
      }, 'wechat');
    }
    external.add('global_bot', {
      config: { appId: 'cli_fs', botOpenId: 'ou_bot', ownerOpenId: 'ou_owner' },
      async send() { return 'ok'; },
      async reaction() { return 'r1'; },
      async image() { return { data: Buffer.alloc(0), mediaType: 'image/png' }; },
      async updateCard() {},
    }, 'feishu');

    const readShadowMessages = async (shadowId: string) => {
      const res = await app.inject({
        method: 'GET',
        url: `/im/v1/conversations/${shadowId}/messages`,
      });
      expect(res.statusCode).toBe(200);
      return res.json().items.map((item: { message: Record<string, unknown> }) => item.message);
    };

    // 1) PA WeChat 1:1 owner message: sent (1 check) -> received (gray 2 checks) -> read (blue 2 checks)
    await external.receive('pa_main', {
      messageId: 'wx_pa_1',
      chatId: 'wxid_owner@im.wechat',
      senderId: 'wxid_owner@im.wechat',
      isGroup: false,
      mentioned: true,
      time: '1760000010000',
      parts: [{ type: 'text', text: '帮我看下今天的安排' }],
    }, 'wechat');

    const paShadow = db.prepare("SELECT id FROM conversations WHERE config_agent_id='pa_main' AND external_source='wechat'").get() as { id: string };
    const paConvRes = await app.inject({ method: 'GET', url: `/im/v1/conversations/${paShadow.id}` });
    expect(paConvRes.json().title).toBe('PA · 个人助手 · wechat');
    // Legacy raw-ID shadow titles also project to the Agent's current display_name when not custom-renamed
    db.prepare("UPDATE conversations SET title='pa_main · wechat' WHERE id=?").run(paShadow.id);
    expect((await app.inject({ method: 'GET', url: `/im/v1/conversations/${paShadow.id}` })).json().title).toBe('PA · 个人助手 · wechat');
    expect((await readShadowMessages(paShadow.id))[0]?.receipts).toMatchObject([{ status: 'sent' }]);

    await globalProduct.recoverPersonalObservations();
    const paSession = store.bindings('pa_main')[0]!.sessionId;
    const paWakeId = wakeInputs.find(id => id.includes('pa_main'))!;
    inbox.deliverNotifications('pa_main', paSession, [paWakeId]);
    globalProduct.scheduleReceipts();
    await expect.poll(async () => (await readShadowMessages(paShadow.id))[0]?.receipts).toMatchObject([{ status: 'received' }]);

    const paPage = inbox.read('pa_main', paSession, 'call-pa-read', { target: paShadow.id });
    expect(inbox.commitRead(paSession, 'call-pa-read', [{ type: 'text', text: JSON.stringify(paPage) }], false, 1)).toBe(true);
    inbox.projectReadReceipts([{ sessionId: paSession, callId: 'call-pa-read' }]);
    globalProduct.scheduleReceipts();
    await expect.poll(async () => (await readShadowMessages(paShadow.id))[0]?.receipts).toMatchObject([{ status: 'read' }]);

    const paEvents = db.prepare("SELECT count(*) AS n FROM conversation_events WHERE conversation_id=? AND event_type='message.receipts_changed'").get(paShadow.id) as { n: number };
    expect(paEvents.n).toBe(2);

    // 2) Ordinary Global Agent WeChat 1:1 owner message: sent -> received -> read
    await external.receive('global_bot', {
      messageId: 'wx_g_1',
      chatId: 'wxid_owner@im.wechat',
      senderId: 'wxid_owner@im.wechat',
      isGroup: false,
      mentioned: true,
      time: '1760000020000',
      parts: [{ type: 'text', text: '总结一下周报' }],
    }, 'wechat');

    let globalShadow: { id: string } | undefined;
    await expect.poll(() => {
      globalShadow = db.prepare("SELECT id FROM conversations WHERE config_agent_id='global_bot' AND external_source='wechat'").get() as { id: string } | undefined;
      return globalShadow?.id;
    }).toBeTruthy();
    expect((await readShadowMessages(globalShadow!.id))[0]?.receipts).toMatchObject([{ status: 'sent' }]);

    const gSession = store.bindings('global_bot')[0]!.sessionId;
    const gWakeId = wakeInputs.find(id => id.includes('global_bot'))!;
    inbox.deliverNotifications('global_bot', gSession, [gWakeId]);
    globalProduct.scheduleReceipts();
    await expect.poll(async () => (await readShadowMessages(globalShadow!.id))[0]?.receipts).toMatchObject([{ status: 'received' }]);

    const gPage = inbox.read('global_bot', gSession, 'call-g-read', { target: 'external:global_bot:wechat:wxbot_g@im.bot:dm:wxid_owner@im.wechat' });
    expect(inbox.commitRead(gSession, 'call-g-read', [{ type: 'text', text: JSON.stringify(gPage) }], false, 1)).toBe(true);
    inbox.projectReadReceipts([{ sessionId: gSession, callId: 'call-g-read' }]);
    globalProduct.scheduleReceipts();
    await expect.poll(async () => (await readShadowMessages(globalShadow!.id))[0]?.receipts).toMatchObject([{ status: 'read' }]);

    // 3) Negative boundaries: SingleThread WeChat, Feishu group, and Feishu non-owner DM have no receipts
    await external.receive('single_bot', {
      messageId: 'wx_s_1',
      chatId: 'wxid_owner@im.wechat',
      senderId: 'wxid_owner@im.wechat',
      isGroup: false,
      mentioned: true,
      time: '1760000030000',
      parts: [{ type: 'text', text: 'single thread hello' }],
    }, 'wechat');
    await external.receive('global_bot', {
      messageId: 'fs_grp_1',
      chatId: 'oc_group_1',
      senderId: 'ou_owner',
      isGroup: true,
      mentioned: true,
      time: '1760000040000',
      parts: [{ type: 'text', text: 'group hello' }],
    }, 'feishu');
    await external.receive('global_bot', {
      messageId: 'fs_peer_1',
      chatId: 'ou_stranger',
      senderId: 'ou_stranger',
      isGroup: false,
      mentioned: true,
      time: '1760000050000',
      parts: [{ type: 'text', text: 'stranger dm' }],
    }, 'feishu');

    await expect.poll(() =>
      (db.prepare("SELECT count(*) AS n FROM conversations WHERE external_source IN ('wechat','feishu')").get() as { n: number }).n,
    ).toBe(5);

    for (const row of db.prepare("SELECT id FROM conversations WHERE config_agent_id='single_bot' OR external_source='feishu'").all() as { id: string }[]) {
      const msgs = await readShadowMessages(row.id);
      expect(msgs[0]?.receipts).toBeUndefined();
    }
  } finally {
    await external?.stop();
    await globalProduct?.stop();
    inbox.close();
    store.close();
    await app.close();
    await rm(dir, { recursive: true, force: true });
  }
});
