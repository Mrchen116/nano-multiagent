import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type WebSocket from 'ws';
import { describe, expect, it } from 'vitest';
import type { UserStreamNotificationHint } from '@nano/product-contracts';
import type { Connection } from '../src/gateway.js';
import { createServer } from '../src/server.js';

interface RecordedFrame {
  op?: string;
  event_type?: string;
  event_id?: number;
  conversation_id?: string;
  data?: Record<string, unknown>;
  notification_hint?: UserStreamNotificationHint;
}

function attachFakeBrowser(
  app: Awaited<ReturnType<typeof createServer>>,
  userId: string,
  sessionId: string,
): { frames: RecordedFrame[] } {
  const frames: RecordedFrame[] = [];
  const socket = {
    readyState: 1,
    bufferedAmount: 0,
    send(raw: string) {
      frames.push(JSON.parse(raw) as RecordedFrame);
    },
    close() {},
  } as unknown as WebSocket;
  app.im.gateway.browsers.add({
    socket,
    userId,
    sessionId,
    ready: true,
    cursor: 0,
  });
  return { frames };
}

describe('im-server cross-platform notification_hint and unread parity', () => {
  it('distinguishes external peer inbound from owner mirror, deduplicates dual events, syncs read/mute, and avoids N+1 or delta bloat', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'nano-im-notif-parity-'));
    const app = await createServer({
      dbPath: join(dir, 'im.sqlite3'),
      uploadDir: join(dir, 'uploads'),
      publicUrl: 'http://127.0.0.1',
      jwtSecret: 'notif-parity-secret',
    });

    try {
      const { db } = app.im;
      const now = new Date().toISOString();
      const expiresAt = Math.floor(Date.now() / 1000) + 3600;

      for (const [id, name] of [
        ['owner', 'Owner Alice'],
        ['bob', 'Colleague Bob'],
        ['carol', 'Colleague Carol'],
      ] as const) {
        db.prepare(
          `INSERT INTO users(id,username,display_name,owner_id,password_hash,created_at,membership_status,personal_space_enabled,auth_epoch)
           VALUES(?,?,?,?, 'hash', ?, 'active', 1, 1)`,
        ).run(id, id, name, id, now);
        db.prepare(
          "INSERT INTO auth_sessions(session_id,user_id,epoch,refresh_hash,expires_at,revoked) VALUES(?,?,1,'rhash',?,0)",
        ).run(`sess-${id}`, id, expiresAt);
      }

      db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('node-1','owner','Mac','online')").run();
      db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch) VALUES('node-1','owner',1)").run();
      const fakeConn: Connection = {
        node_id: 'node-1',
        owner_id: 'owner',
        node_epoch: 1,
        token: 'gw-token',
        lastSeen: Date.now(),
        socket: { readyState: 1, bufferedAmount: 0, send() {}, close() {} } as unknown as WebSocket,
      };
      app.im.gateway.nodes.set('node-1', fakeConn);

      db.prepare(
        `INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,workspace_root,work_mode,collaboration_scope,space_id,created_at,updated_at)
         VALUES('pa_main','owner','node-1','PA · 小助','/ws','global','team','personal:owner',?,?)`,
      ).run(now, now);
      db.prepare(
        `INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,workspace_root,work_mode,collaboration_scope,space_id,created_at,updated_at)
         VALUES('team_bot','owner','node-1','团队助手','/ws2','global','team','company:default',?,?)`,
      ).run(now, now);
      app.im.messaging.agentUser('pa_main');
      app.im.messaging.agentUser('team_bot');

      db.prepare(
        "INSERT INTO conversations(id,title,type,owner_id,space_id,config_agent_id,created_at) VALUES('owner-chat','PA','direct','owner','personal:owner','pa_main',?)",
      ).run(now);
      db.prepare(
        "INSERT INTO conversation_participants(conversation_id,user_id) VALUES('owner-chat','owner'),('owner-chat',?)",
      ).run(app.im.messaging.agentUser('pa_main').id);
      db.prepare(
        "INSERT INTO personal_agent_bindings VALUES('bind-1','owner','owner','pa_main','node-1',1,'owner-chat','PA','create','active',NULL,?)",
      ).run(now);
      db.prepare("INSERT INTO pa_policies(binding_id) VALUES('bind-1')").run();

      // External Feishu shadow chat bound to owner_open_id = 'ou_owner_self'
      db.prepare(
        `INSERT INTO agent_channels(channel_id,owner_id,agent_id,node_id,provider,enabled,config_json,provider_identity_fingerprint,provider_identity_revision,provider_runtime_json,credential_envelope_json,credential_key_id,credential_revision,channel_revision,created_at,updated_at)
         VALUES('ch-fs','owner','pa_main','node-1','feishu',1,'{"app_id":"cli_1"}','fp1',1,'{"owner_open_id":"ou_owner_self"}','{}','k1',1,1,?,?)`,
      ).run(now, now);
      db.prepare(
        `INSERT INTO conversations(id,title,type,owner_id,space_id,config_agent_id,external_source,external_chat_id,created_at)
         VALUES('ext-fs-group','客户沟通群 · feishu','group','owner','personal:owner','pa_main','feishu','feishu:cli_1:group:oc_1',?)`,
      ).run(now);
      db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('ext-fs-group','owner')").run();

      // Shared team group chat with owner, bob, carol
      db.prepare(
        "INSERT INTO conversations(id,title,type,owner_id,creator_id,space_id,visibility,created_at) VALUES('team-grp','研发群','group','owner','owner','company:default','public',?)",
      ).run(now);
      for (const uid of ['owner', 'bob', 'carol']) {
        db.prepare('INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,?)').run('team-grp', uid);
      }

      const ownerStream = attachFakeBrowser(app, 'owner', 'sess-owner');
      const bobStream = attachFakeBrowser(app, 'bob', 'sess-bob');
      const carolStream = attachFakeBrowser(app, 'carol', 'sess-carol');

      // 1) Owner's own Feishu mirror message: unread stays 0 and eligible === false
      app.im.messaging.insertMessage('ext-fs-group', 'owner', 'user', '我在飞书里自己发的话', [], 'shadow:self-1', 'completed', {
        sender_source_id: 'ou_owner_self',
        sender_display_name: 'Owner Feishu',
      });
      const selfMirrorFrame = ownerStream.frames.find(
        f => f.event_type === 'message.created' && f.conversation_id === 'ext-fs-group',
      )!;
      expect(selfMirrorFrame.notification_hint?.eligible).toBe(false);
      expect(app.im.messaging.conversation('ext-fs-group', 'owner').unread_count).toBe(0);

      // 2) External peer inbound message in Feishu shadow: unread increments to 1, eligible === true, kind === 'human_message'
      ownerStream.frames.length = 0;
      const peerMsg = app.im.messaging.insertMessage(
        'ext-fs-group',
        'owner',
        'user',
        '你好，请问下周版本什么时候发？',
        [],
        'shadow:peer-1',
        'completed',
        {
          sender_source_id: 'ou_customer_99',
          sender_display_name: '外部客户王总',
        },
      );
      const peerFrame = ownerStream.frames.find(f => f.event_type === 'message.created')!;
      expect(peerFrame.notification_hint).toMatchObject({
        eligible: true,
        kind: 'human_message',
        dedupe_key: `message:${peerMsg.id}`,
        sender_name: '外部客户王总',
        conversation_unread: 1,
        target_route: '/chat/ext-fs-group',
      });
      expect(app.im.messaging.conversation('ext-fs-group', 'owner').unread_count).toBe(1);

      // 3) POST /read emits `conversation.read` with unread_count: 0; PATCH mute emits `conversation.preference_updated`
      app.im.identity.authenticateRequest = () => app.im.identity.user('owner')!;
      ownerStream.frames.length = 0;
      const readRes = await app.inject({
        method: 'POST',
        url: '/im/v1/conversations/ext-fs-group/read',
        payload: { last_read_message_id: peerMsg.id },
      });
      expect(readRes.statusCode).toBe(200);
      expect(ownerStream.frames.find(f => f.event_type === 'conversation.read')?.data).toMatchObject({
        conversation_id: 'ext-fs-group',
        unread_count: 0,
        is_muted: false,
      });

      ownerStream.frames.length = 0;
      const muteRes = await app.inject({
        method: 'PATCH',
        url: '/im/v1/conversations/team-grp',
        payload: { is_muted: true },
      });
      expect(muteRes.statusCode).toBe(200);
      expect(ownerStream.frames.find(f => f.event_type === 'conversation.preference_updated')?.data).toMatchObject({
        conversation_id: 'team-grp',
        is_muted: true,
      });

      // 4) Group message with @mention to muted owner vs unmentioned unmuted carol (per-recipient independent hints, bounded SQL)
      ownerStream.frames.length = 0;
      bobStream.frames.length = 0;
      carolStream.frames.length = 0;

      let prepareCount = 0;
      const origPrepare = db.prepare.bind(db);
      db.prepare = ((sql: string) => {
        prepareCount += 1;
        return origPrepare(sql);
      }) as typeof db.prepare;
      try {
        app.im.messaging.insertMessage(
          'team-grp',
          'bob',
          'user',
          '请看一下 <mention type="user" target_id="owner" /> 这个指标',
          [],
          'msg-bob-mention',
          'completed',
        );
      } finally {
        db.prepare = origPrepare;
      }
      // Constant-bounded SQL even with 3 connected recipients
      expect(prepareCount).toBeLessThanOrEqual(25);

      const ownerMention = ownerStream.frames.find(f => f.event_type === 'message.created')!;
      const bobSelf = bobStream.frames.find(f => f.event_type === 'message.created')!;
      const carolNormal = carolStream.frames.find(f => f.event_type === 'message.created')!;

      expect(ownerMention.notification_hint).toMatchObject({
        eligible: true,
        kind: 'mention',
        is_muted: true,
        mentions_viewer: true,
        preview_text: '请看一下 @Owner Alice 这个指标',
      });
      expect(bobSelf.notification_hint?.eligible).toBe(false);
      expect(carolNormal.notification_hint).toMatchObject({
        eligible: true,
        kind: 'human_message',
        is_muted: false,
        mentions_viewer: false,
      });

      // 5) publishAgent dual-event shares identical dedupe_key and backfills slim message.completed
      ownerStream.frames.length = 0;
      const pubReceipt = app.im.messaging.publishAgent(
        { ...fakeConn, kind: 'gateway' },
        'pa_main',
        'op-card-1',
        {
          to: 'conversation:owner-chat',
          text: '',
          interactive: {
            format: 'openui',
            catalog_version: 'nano-iui-1',
            source: 'root = Title("请确认发布窗口")',
          },
        },
      );
      const pubCreated = ownerStream.frames.find(f => f.event_type === 'message.created')!;
      const pubCompleted = ownerStream.frames.find(f => f.event_type === 'message.completed')!;
      expect(pubCreated.notification_hint).toMatchObject({
        eligible: true,
        kind: 'message_completed',
        dedupe_key: `message:${pubReceipt.message_id}`,
        sender_name: 'PA · 小助',
        has_interactive_card: true,
      });
      expect(pubCompleted.notification_hint).toMatchObject({
        eligible: true,
        kind: 'message_completed',
        dedupe_key: `message:${pubReceipt.message_id}`,
        sender_name: 'PA · 小助',
        has_interactive_card: true,
      });

      // 6) WorkerPermissionCards: carrier message.created & resolved message.completed are eligible:false; permission.request is chat_permission
      ownerStream.frames.length = 0;
      const permReceipt = app.im.messaging.workerPermissions.create(fakeConn, {
        kind: 'worker_permission_request',
        agent_id: 'pa_main',
        session_id: 'sess-w1',
        run_id: 'run-w1',
        lifecycle_revision: 1,
        expires_at: Date.now() + 60_000,
        worker: { runtime: 'codex', task_label: 'Deploy check' },
        permission_request: {
          request_id: 'req-perm-1',
          call_id: 'call-1',
          tool_name: 'Bash',
          question: '允许运行迁移脚本吗？',
          tool_input: { cmd: 'migrate' },
        },
      });
      expect(ownerStream.frames.find(f => f.event_type === 'message.created')?.notification_hint?.eligible).toBe(false);
      expect(ownerStream.frames.find(f => f.event_type === 'permission.request')?.notification_hint).toMatchObject({
        eligible: true,
        kind: 'chat_permission',
        dedupe_key: 'perm:req-perm-1',
        tool_name: 'Bash',
        target_route: '/chat/owner-chat',
      });

      ownerStream.frames.length = 0;
      app.im.messaging.workerPermissions.finish(app.im.messaging.message(permReceipt.message_id!), 'deny');
      expect(ownerStream.frames.find(f => f.event_type === 'permission.resolved')?.notification_hint).toBeUndefined();
      expect(ownerStream.frames.find(f => f.event_type === 'message.completed')?.notification_hint?.eligible).toBe(false);

      // 7) Stream delta / process frames carry zero notification_hint
      ownerStream.frames.length = 0;
      app.im.gateway.broadcast('conversation-readers', {
        op: 'event',
        event_id: 99999,
        conversation_id: 'owner-chat',
        event_type: 'message.delta',
        data: { delta: 'hi', delta_text: 'hi' },
      });
      const deltaFrame = ownerStream.frames.find(f => f.event_type === 'message.delta')!;
      expect('notification_hint' in deltaFrame).toBe(false);

      // 8) agent.work.updated: non-waiting_permission emits eligible:false; waiting_permission emits work_permission ONLY for owner
      db.prepare(
        `INSERT INTO agent_work_sessions(session_id,root_agent_id,node_id,scope,parent_session_id,payload)
         VALUES('main-s1','team_bot','node-1','global_main',NULL,?)`,
      ).run(JSON.stringify({ session_id: 'main-s1', scope: 'global_main', retired: false }));
      db.prepare(
        `INSERT INTO agent_work_turns(session_id,turn_id,seq,payload)
         VALUES('main-s1','turn-1',1,?)`,
      ).run(JSON.stringify({ turn_id: 'turn-1', status: 'running' }));

      ownerStream.frames.length = 0;
      bobStream.frames.length = 0;
      app.im.gateway.broadcast(['owner', 'bob'], {
        op: 'event',
        event_type: 'agent.work.updated',
        data: { agent_id: 'team_bot', revision: 1 },
      });
      expect(ownerStream.frames[0]?.notification_hint).toMatchObject({
        eligible: false,
        target_route: '/settings/agents/team_bot?view=work',
      });
      expect(bobStream.frames[0]?.notification_hint?.eligible).toBe(false);

      db.prepare("UPDATE agent_work_turns SET payload=? WHERE session_id='main-s1' AND turn_id='turn-1'").run(
        JSON.stringify({ turn_id: 'turn-1', status: 'waiting_permission' }),
      );
      ownerStream.frames.length = 0;
      bobStream.frames.length = 0;
      app.im.gateway.broadcast(['owner', 'bob'], {
        op: 'event',
        event_type: 'agent.work.updated',
        data: { agent_id: 'team_bot', revision: 2 },
      });
      expect(ownerStream.frames[0]?.notification_hint).toMatchObject({
        eligible: true,
        kind: 'work_permission',
        dedupe_key: 'work-perm:team_bot:main-s1:turn-1',
        sender_name: '团队助手',
        target_route: '/settings/agents/team_bot?view=work',
      });
      // Colleague Bob can view team agent Work, so receives the frame, but eligible MUST be false (not owner!)
      expect(bobStream.frames[0]?.notification_hint?.eligible).toBe(false);
    } finally {
      await app.close();
      await rm(dir, { recursive: true, force: true });
    }
  });
});
