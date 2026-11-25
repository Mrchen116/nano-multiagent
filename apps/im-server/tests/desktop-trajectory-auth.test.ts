import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, expect, it } from 'vitest';
import { createServer } from '../src/server.js';

const closers: (() => Promise<void>)[] = [];
afterEach(async () => { for (const close of closers.splice(0)) await close(); });

async function setup() {
  const dir = mkdtempSync(join(tmpdir(), 'nano-desktop-traj-auth-'));
  const app = await createServer({ dbPath: join(dir, 'im.sqlite3'), publicUrl: 'https://nano.example', nodeReleaseDir: dir });
  closers.push(async () => { await app.close(); rmSync(dir, { recursive: true, force: true }); });

  const ownerPair = await app.im.identity.register('alice', 'password1', 'Alice');
  app.im.identity.initializeCompany(ownerPair.user.id);
  const strangerPair = await app.im.identity.register('bob', 'password2', 'Bob');

  const owner = ownerPair.user.owner_id;
  const now = new Date().toISOString();
  app.im.db.prepare("UPDATE users SET personal_space_enabled=1, membership_status='active' WHERE id=?").run(ownerPair.user.id);
  app.im.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status,last_heartbeat_at,agent_count,version) VALUES('node-1',?,'Air-Studio','online',?,2,'2.4.0')").run(owner, now);
  app.im.db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch,runtime_token_hash) VALUES('node-1',?,5,'hash')").run(owner);

  app.im.db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,space_id,node_id,display_name,work_mode,is_stale,created_at,updated_at) VALUES('e1',?,'company:default','node-1','Engineer','global',0,?,?)").run(owner, now, now);
  app.im.db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,space_id,node_id,display_name,work_mode,is_stale,created_at,updated_at) VALUES('pa-alice',?,?,'node-1','PA','global',0,?,?)").run(owner, `personal:${owner}`, now, now);
  app.im.db.prepare("INSERT INTO conversations(id,type,title,space_id,created_at) VALUES('conv-pa','direct','PA',?,?)").run(`personal:${owner}`, now);
  app.im.db.prepare("INSERT INTO personal_agent_bindings VALUES('bind-1',?,?, 'pa-alice','node-1',5,'conv-pa','PA','req-1','active',NULL,?)")
    .run(owner, ownerPair.user.id, now);

  return {
    app,
    now,
    ownerUser: ownerPair.user,
    ownerHeaders: { authorization: 'Bearer ' + ownerPair.access_token },
    strangerUser: strangerPair.user,
    strangerHeaders: { authorization: 'Bearer ' + strangerPair.access_token },
  };
}

it('authorizes local trajectory read even when >16MiB blocked WorkSync from syncing child session_id, while enforcing space and PA boundaries', async () => {
  const { app, ownerHeaders, strangerHeaders, strangerUser } = await setup();

  // Child session `unsynced-subagent-session` does NOT exist in agent_work_sessions at all.
  const ok = await app.inject({
    method: 'POST',
    url: '/im/v1/agents/e1/trajectory/authorize',
    headers: ownerHeaders,
    payload: { session_id: 'unsynced-subagent-session' },
  });
  expect(ok.statusCode).toBe(200);
  expect(ok.json()).toMatchObject({
    authorized: true,
    node_id: 'node-1',
    node_epoch: 5,
  });

  // Pending/non-company member cannot authorize company:default agent.
  app.im.db.prepare("UPDATE users SET membership_status='pending' WHERE id=?").run(strangerUser.id);
  const deniedStranger = await app.inject({
    method: 'POST',
    url: '/im/v1/agents/e1/trajectory/authorize',
    headers: strangerHeaders,
    payload: { session_id: 'unsynced-subagent-session' },
  });
  expect(deniedStranger.statusCode).toBe(404);

  // Active company member can authorize shared e1, but CANNOT authorize Alice's Personal Agent.
  app.im.db.prepare("UPDATE users SET membership_status='active' WHERE id=?").run(strangerUser.id);
  const colleagueSharedOk = await app.inject({
    method: 'POST',
    url: '/im/v1/agents/e1/trajectory/authorize',
    headers: strangerHeaders,
    payload: { session_id: 'unsynced-subagent-session' },
  });
  expect(colleagueSharedOk.statusCode).toBe(200);

  const colleaguePaDenied = await app.inject({
    method: 'POST',
    url: '/im/v1/agents/pa-alice/trajectory/authorize',
    headers: strangerHeaders,
    payload: { session_id: 'pa-session' },
  });
  expect(colleaguePaDenied.statusCode).toBe(404);
});

it('validates workspace vs chat attachment sources against conversation membership', async () => {
  const { app, ownerUser, ownerHeaders, strangerHeaders, strangerUser, now } = await setup();
  app.im.db.prepare("UPDATE users SET membership_status='active' WHERE id=?").run(strangerUser.id);

  // Create a private conversation owned only by Alice with an image attachment.
  app.im.db.prepare("INSERT INTO conversations(id,type,title,space_id,created_at) VALUES('priv-conv','direct','Private',?,?)").run(`personal:${ownerUser.owner_id}`, now);
  app.im.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('priv-conv',?)").run(ownerUser.id);
  const imgUrl = '/im/v1/conversations/priv-conv/images/img-1';
  app.im.db.prepare("INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,attachments_json,delivery_status,created_at) VALUES('msg-1','priv-conv',?,'user','pic',?,'completed',?)")
    .run(ownerUser.id, JSON.stringify([{ url: imgUrl, content_type: 'image/png' }]), now);
  app.im.db.prepare("INSERT INTO message_images(image_id,conversation_id,source_key,sha256,content_type,file_name,byte_size,storage_name) VALUES('img-1','priv-conv','src-1',?,'image/png','pic.png',10,'stored-1')")
    .run('a'.repeat(64));

  const wsAllowed = await app.inject({
    method: 'POST',
    url: '/im/v1/agents/e1/trajectory/authorize-attachment',
    headers: strangerHeaders,
    payload: { sources: [{ kind: 'workspace', path: 'charts/plot.png' }] },
  });
  expect(wsAllowed.json()).toEqual({ allowed: true });

  const chatDenied = await app.inject({
    method: 'POST',
    url: '/im/v1/agents/e1/trajectory/authorize-attachment',
    headers: strangerHeaders,
    payload: { sources: [{ kind: 'chat', conversationId: 'priv-conv', messageId: 'msg-1', url: imgUrl }] },
  });
  expect(chatDenied.json()).toEqual({ allowed: false });

  const chatOwnerAllowed = await app.inject({
    method: 'POST',
    url: '/im/v1/agents/e1/trajectory/authorize-attachment',
    headers: ownerHeaders,
    payload: { sources: [{ kind: 'chat', conversationId: 'priv-conv', messageId: 'msg-1', url: imgUrl }] },
  });
  expect(chatOwnerAllowed.json()).toEqual({ allowed: true });
});
