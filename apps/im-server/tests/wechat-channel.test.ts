import { generateKeyPairSync } from 'node:crypto';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { expect, it } from 'vitest';
import { ExternalChannels } from '../../../packages/personal-assistant/src/external.js';
import { NodeStore } from '../../../packages/personal-assistant/src/store.js';
import { requestIm } from '../../node/src/im-http.js';
import { ownerDirect } from '../src/collaboration.js';
import { openDatabase } from '../src/db.js';
import type { Connection } from '../src/gateway.js';
import { createServer } from '../src/server.js';

function testPublicKeyBase64(): string {
  const { publicKey } = generateKeyPairSync('x25519');
  const jwk = publicKey.export({ format: 'jwk' });
  return Buffer.from(jwk.x!, 'base64url').toString('base64');
}

it('enforces interactive WeChat setup, seals bot_token without browser echo, and upgrades existing owner_direct_agent_messages view for PA', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'nano-im-wechat-'));
  const dbPath = join(dir, 'im.sqlite3');

  // Simulate an existing pre-feat-794 database with a legacy Feishu-only owner_direct_agent_messages view!
  const preDb = openDatabase(dbPath);
  preDb.exec(`
    DROP VIEW IF EXISTS owner_direct_agent_messages;
    CREATE VIEW owner_direct_agent_messages AS
      SELECT m.id AS message_id, a.agent_id
      FROM messages m
      JOIN conversations c ON c.id=m.conversation_id AND c.type='direct'
      JOIN agent_profiles a ON a.agent_id=c.config_agent_id
      WHERE m.sender_type='user' AND c.external_source='feishu';
    DELETE FROM schema_migrations WHERE version='owner-direct-wechat-view-v1';
  `);
  preDb.close();

  const app = await createServer({
    dbPath,
    uploadDir: join(dir, 'uploads'),
    publicUrl: 'http://127.0.0.1',
    jwtSecret: 'isolated-wechat-im-test-secret',
  });
  const store = new NodeStore(join(dir, 'node.sqlite3'), 'owner');
  let external: ExternalChannels | undefined;

  try {
    const { db } = app.im;
    const now = new Date().toISOString();
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status,personal_space_enabled) VALUES('owner','owner','Owner','owner',?,'active',1)").run(now);
    db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('node','owner','Node','online')").run();
    db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch) VALUES('node','owner',1)").run();
    db.prepare("INSERT INTO node_credential_keys(node_id,owner_id,key_id,algorithm,public_key,updated_at) VALUES('node','owner','key-1','X25519-HKDF-SHA256-AES-256-GCM',?,?)").run(testPublicKeyBase64(), now);
    db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,workspace_root,collaboration_scope,space_id,created_at,updated_at) VALUES('pa_main','owner','node','Personal Assistant','/pa','owner_only','personal:owner',?,?)").run(now, now);
    db.prepare("INSERT INTO conversations(id,title,type,owner_id,space_id,config_agent_id,created_at) VALUES('owner-chat','PA','direct','owner','personal:owner','pa_main',?)").run(now);
    db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('owner-chat','owner')").run();
    db.prepare("INSERT INTO personal_agent_bindings VALUES('binding','owner','owner','pa_main','node',1,'owner-chat','PA','create','active',NULL,?)").run(now);
    db.prepare("INSERT INTO pa_policies(binding_id) VALUES('binding')").run();

    const sentFrames: { type: string; payload: Record<string, unknown> }[] = [];
    const fakeConn = {
      node_id: 'node',
      owner_id: 'owner',
      node_epoch: 1,
      token: 'gateway-token',
      socket: {
        readyState: 1,
        send(raw: string) {
          const frame = JSON.parse(raw) as { type: string; payload: Record<string, unknown> };
          sentFrames.push(frame);
          if (frame.type === 'node.wechat.setup.request') {
            const reqId = frame.payload.request_id;
            const action = frame.payload.action;
            const rpc = (app.im.gateway as unknown as { rpc: { accept(c: Connection, t: string, p: unknown): boolean } }).rpc;
            queueMicrotask(() => {
              if (action === 'start') {
                rpc.accept(fakeConn, 'node.wechat.setup.result', {
                  request_id: reqId,
                  setup_id: 'setup_1',
                  state: 'waiting_scan',
                  qr_svg: '<svg>qr</svg>',
                });
              } else if (action === 'verify_code') {
                rpc.accept(fakeConn, 'node.wechat.setup.result', {
                  request_id: reqId,
                  setup_id: 'setup_1',
                  state: 'confirmed',
                  binding: {
                    bot_token: 'super_secret_wechat_bot_token',
                    bot_id: 'wxbot_pa_1',
                    owner_user_id: 'wxid_owner_real',
                    base_url: 'https://ilinkai.weixin.qq.com',
                  },
                });
              }
            });
          }
        },
        close() {},
      },
    } as unknown as Connection;
    app.im.gateway.nodes.set('node', fakeConn);

    app.im.identity.authenticateRequest = () => app.im.identity.user('owner')!;
    const authHeaders = { 'Content-Type': 'application/json' };

    // 1. Direct REST POST with plaintext WeChat secret MUST be rejected (422)
    const directCreate = await app.inject({
      method: 'POST',
      url: '/im/v1/agents/pa_main/channels',
      headers: authHeaders,
      payload: {
        provider: 'wechat',
        enabled: true,
        config: { bot_id: 'wxbot_pa_1', owner_user_id: 'wxid_owner_real', base_url: 'https://ilinkai.weixin.qq.com' },
        credentials: { mode: 'replace', bot_token: 'plaintext_attempt' },
      },
    });
    expect(directCreate.statusCode).toBe(422);
    expect(directCreate.json()).toMatchObject({ detail: { code: 'channel_interactive_setup_required' } });

    // 2. Feishu channel can be created and coexist on the same PA
    const feishuCreate = await app.inject({
      method: 'POST',
      url: '/im/v1/agents/pa_main/channels',
      headers: authHeaders,
      payload: {
        provider: 'feishu',
        enabled: true,
        config: { app_id: 'cli_feishu_1' },
        credentials: { mode: 'replace', app_secret: 'fs_secret' },
      },
    });
    expect(feishuCreate.statusCode).toBe(201);

    // 3. Interactive WeChat setup: start -> verify_code -> confirmed (seals token, never echoes bot_token)
    const startRes = await app.inject({
      method: 'POST',
      url: '/im/v1/agents/pa_main/channels/wechat/setup',
      headers: authHeaders,
      payload: { action: 'start' },
    });
    expect(startRes.statusCode).toBe(200);
    expect(startRes.json()).toMatchObject({ setup_id: 'setup_1', state: 'waiting_scan', qr_svg: '<svg>qr</svg>' });

    const confirmRes = await app.inject({
      method: 'POST',
      url: '/im/v1/agents/pa_main/channels/wechat/setup',
      headers: authHeaders,
      payload: { action: 'verify_code', setup_id: 'setup_1', code: '482916' },
    });
    expect(confirmRes.statusCode).toBe(200);
    expect(confirmRes.body).not.toContain('super_secret_wechat_bot_token');
    const confirmedJson = confirmRes.json();
    expect(confirmedJson.state).toBe('confirmed');
    expect(confirmedJson.channel).toMatchObject({
      provider: 'wechat',
      enabled: true,
      secret_configured: true,
      config: {
        bot_id: 'wxbot_pa_1',
        owner_user_id: 'wxid_owner_real',
        base_url: 'https://ilinkai.weixin.qq.com',
      },
    });

    const wxChannelId = confirmedJson.channel.channel_id as string;

    // 4. PATCH keep-credentials toggle works, but PATCH secret replacement is rejected
    const badPatch = await app.inject({
      method: 'PATCH',
      url: `/im/v1/agents/pa_main/channels/${wxChannelId}`,
      headers: authHeaders,
      payload: {
        channel_revision: 1,
        enabled: true,
        config: confirmedJson.channel.config,
        credentials: { mode: 'replace', bot_token: 'hack' },
      },
    });
    expect(badPatch.statusCode).toBe(422);

    const disablePatch = await app.inject({
      method: 'PATCH',
      url: `/im/v1/agents/pa_main/channels/${wxChannelId}`,
      headers: authHeaders,
      payload: {
        channel_revision: 1,
        enabled: false,
        config: confirmedJson.channel.config,
        credentials: { mode: 'keep' },
      },
    });
    expect(disablePatch.statusCode).toBe(200);
    expect(disablePatch.json().enabled).toBe(false);

    const enablePatch = await app.inject({
      method: 'PATCH',
      url: `/im/v1/agents/pa_main/channels/${wxChannelId}`,
      headers: authHeaders,
      payload: {
        channel_revision: 2,
        enabled: true,
        config: confirmedJson.channel.config,
        credentials: { mode: 'keep' },
      },
    });
    expect(enablePatch.statusCode).toBe(200);

    // 5. Mirror owner WeChat DM into Personal Agent (with collaboration_scope = 'owner_only'!)
    const baseUrl = await app.listen({ host: '127.0.0.1', port: 0 });
    external = new ExternalChannels(join(dir, 'external.sqlite3'), {
      nodeId: 'node',
      ownerId: 'owner',
      store,
      personalAgent: () => true,
      relay: { ready: true, request: async () => ({ type: 'ack', payload: {} }) },
      im: (path, init) => requestIm(baseUrl, 'gateway-token', path, init),
      receive: async () => {},
      permission: async () => {},
      onError: err => { throw err; },
    });
    external.add('pa_main', {
      supportsReactions: false,
      supportsCards: false,
      config: { appId: 'wxbot_pa_1', botOpenId: 'wxbot_pa_1', ownerOpenId: 'wxid_owner_real' },
      send: async () => 'wx_msg_out',
      reaction: async () => undefined,
      image: async () => ({ data: Buffer.alloc(0), mediaType: 'image/png' }),
      updateCard: async () => {},
    }, 'wechat');

    await external.receive('pa_main', {
      messageId: 'wx_pa_msg_1',
      chatId: 'wxid_owner_real',
      senderId: 'wxid_owner_real',
      isGroup: false,
      mentioned: true,
      time: '1700000005000',
      parts: [{ type: 'text', text: '提醒我下午三点开会' }],
    }, 'wechat');

    const msgRow = db.prepare("SELECT id, conversation_id FROM messages WHERE caller_idempotency_key=?").get(
      'shadow:external:pa_main:wechat:wxbot_pa_1:wx_pa_msg_1',
    ) as { id: string; conversation_id: string } | undefined;
    expect(msgRow).toBeDefined();
    expect(ownerDirect(db, 'pa_main', msgRow!.id)).toBe(true);

    const observations = app.im.personal!.observations(
      { node_id: 'node', owner_id: 'owner', node_epoch: 1 },
      { agent_id: 'pa_main', binding_id: 'binding', epoch: 1 },
    );
    expect(observations.items.some((item: { message_id: string; is_owner?: boolean; owner_direct?: boolean; channel?: string }) =>
      item.message_id === msgRow!.id && item.is_owner === true && item.owner_direct === true && item.channel === 'wechat')).toBe(true);

    const binding = app.im.personal!.binding('owner')!;
    expect(app.im.personal!.ownerConversation(binding, msgRow!.conversation_id)).toBe(true);

    const transportProposal = await app.im.personal!.handle(
      { node_id: 'node', owner_id: 'owner', node_epoch: 1 },
      'pa.action.prepare',
      {
        agent_id: 'pa_main',
        request_key: 'wx_reply_1',
        conversation_id: msgRow!.conversation_id,
        content: '好的，已为你记下下午三点的会议提醒。',
        attachments: [{ url: 'external:out:wx_reply_1:0', content_type: 'image/png', file_name: 'chart.png' }],
        transport: {
          kind: 'wechat',
          destination: {
            bot_id: 'wxbot_pa_1',
            chat_id: 'wxid_owner_real',
            source_id: 'wechat:wxbot_pa_1:dm:wxid_owner_real',
          },
        },
      },
    );
    expect(transportProposal).toMatchObject({ owner_private: true, conversation_id: msgRow!.conversation_id });

    // Uploaded shadow outbound image attaches cleanly onto message_completed in shadow chat.
    const png1x1 = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
      'base64',
    );
    const uploadRes = await app.inject({
      method: 'POST',
      url: `/im/v1/conversations/${msgRow!.conversation_id}/images?agent_id=pa_main&file_name=chart.png&screenshot=1`,
      headers: {
        authorization: 'Bearer gateway-token',
        'content-type': 'image/png',
        'idempotency-key': 'shadow-out:1',
      },
      payload: png1x1,
    });
    expect(uploadRes.statusCode).toBe(201);
    const uploadedAtt = uploadRes.json() as { url: string; content_type: string; file_name: string };

    const turnStart = app.im.gateway.streaming(
      { node_id: 'node', owner_id: 'owner', node_epoch: 1 },
      { kind: 'turn_start', agent_id: 'pa_main', conversation_id: msgRow!.conversation_id, idempotency_key: 'wx-out-img-1' },
    );
    app.im.gateway.streaming(
      { node_id: 'node', owner_id: 'owner', node_epoch: 1 },
      {
        kind: 'message_completed',
        message_id: turnStart.message_id!,
        final_content: '已发送图表',
        attachments: [uploadedAtt],
        delivery_status: 'completed',
      },
    );
    const completedMsg = app.im.messaging.message(turnStart.message_id!);
    expect(completedMsg.attachments).toEqual([uploadedAtt]);
  } finally {
    await external?.stop();
    store.close();
    await app.close();
    await rm(dir, { recursive: true, force: true });
  }
});
