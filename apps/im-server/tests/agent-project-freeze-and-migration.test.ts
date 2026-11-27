import { EventEmitter } from 'node:events';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { afterEach, expect, it, vi } from 'vitest';
import { openDatabase } from '../src/db.js';
import { createServer } from '../src/server.js';
import type { Connection } from '../src/gateway.js';

const cleanups: Array<() => unknown | Promise<unknown>> = [];
afterEach(async () => {
  for (const close of cleanups.splice(0).reverse()) await close();
});

async function createThreeUserEnv() {
  const dir = mkdtempSync(join(tmpdir(), 'im-proj-freeze-'));
  cleanups.push(() => rmSync(dir, { recursive: true, force: true }));
  const app = await createServer({ dbPath: join(dir, 'im.db'), publicUrl: 'http://localhost', jwtSecret: 'proj-freeze-secret' });
  cleanups.push(() => app.close());

  const alice = await app.im.identity.register('alice', 'password-123', 'Alice');
  app.im.identity.initializeCompany(alice.user.id);
  const bob = await app.im.identity.register('bob', 'password-123', 'Bob');
  const charlie = await app.im.identity.register('charlie', 'password-123', 'Charlie');
  app.im.db.prepare("UPDATE users SET membership_status='active' WHERE id IN (?,?)").run(bob.user.id, charlie.user.id);

  const request = (token: string, method: any, url: string, payload?: any) =>
    app.inject({ method, url, payload, headers: { authorization: `Bearer ${token}` } });

  const attachOnlineNode = (nodeId: string, ownerId: string, epoch = 1) => {
    const now = new Date().toISOString();
    app.im.db.prepare(
      "INSERT OR REPLACE INTO nodes(node_id,owner_id,node_name,status,last_heartbeat_at,agent_count,version) VALUES(?,?,?,'online',?,2,'2.5.0')",
    ).run(nodeId, ownerId, nodeId, now);
    app.im.db.prepare("INSERT OR REPLACE INTO node_binding_state(node_id,owner_id,node_epoch) VALUES(?,?,?)").run(nodeId, ownerId, epoch);
    const sentFrames: Array<{ type: string; payload: any }> = [];
    const socket = Object.assign(new EventEmitter(), {
      readyState: 1,
      send: (raw: string) => { sentFrames.push(JSON.parse(raw)); },
      close: vi.fn(),
    });
    const connection = { node_id: nodeId, owner_id: ownerId, node_epoch: epoch, socket: socket as any, agent_lifecycle_v1: true } as Connection;
    app.im.gateway.nodes.set(nodeId, connection);
    return { connection, sentFrames };
  };

  return { app, db: app.im.db, dir, alice, bob, charlie, request, attachOnlineNode };
}

it('migrates legacy agent_profiles CHECK constraint without cascading child deletions and passes foreign_key_check', () => {
  const dir = mkdtempSync(join(tmpdir(), 'im-proj-db-mig-'));
  cleanups.push(() => rmSync(dir, { recursive: true, force: true }));
  const dbPath = join(dir, 'legacy.db');

  const seedDb = openDatabase(dbPath);
  seedDb.exec('PRAGMA foreign_keys=OFF');
  seedDb.exec(`
    DROP VIEW IF EXISTS owner_direct_agent_messages;
    DROP TRIGGER IF EXISTS agent_lifecycle_created;
    DROP TABLE agent_profiles;
    CREATE TABLE agent_profiles (
      agent_id TEXT PRIMARY KEY,
      avatar_variant INTEGER CHECK (avatar_variant BETWEEN 0 AND 23),
      space_id TEXT NOT NULL DEFAULT 'company:default',
      owner_id TEXT NOT NULL,
      node_id TEXT,
      display_name TEXT NOT NULL,
      description TEXT NOT NULL DEFAULT '',
      skills_json TEXT NOT NULL DEFAULT '[]',
      skills_selection_mode TEXT,
      tool_allowlist_json TEXT NOT NULL DEFAULT '[]',
      collaboration_scope TEXT NOT NULL DEFAULT 'team' CHECK(collaboration_scope IN ('team','owner_only')),
      default_model TEXT,
      model_fallbacks_json TEXT NOT NULL DEFAULT '[]',
      reasoning_effort TEXT,
      approval_mode TEXT CHECK (approval_mode IS NULL OR approval_mode IN ('cc', 'codex')),
      work_mode TEXT NOT NULL DEFAULT 'single_thread',
      workspace_root TEXT,
      workspace_is_default INTEGER,
      registration_seed INTEGER NOT NULL DEFAULT 0,
      pending_create_operation_id TEXT,
      profile_version INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      is_stale INTEGER NOT NULL DEFAULT 0,
      staled_at TEXT,
      features_json TEXT NOT NULL DEFAULT '{}',
      heartbeat_json TEXT
    );
    CREATE TRIGGER agent_lifecycle_created AFTER INSERT ON agent_profiles BEGIN
      INSERT OR IGNORE INTO agent_lifecycle(agent_id,requested_at) VALUES(NEW.agent_id,NEW.created_at);
    END;
  `);
  seedDb.exec('PRAGMA foreign_keys=ON');
  seedDb.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES('u1','alice','Alice','u1','2026-01-01','active')").run();
  seedDb.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,collaboration_scope,created_at,updated_at) VALUES('legacy-bot','u1','n1','Legacy Bot','owner_only','2026-01-01','2026-01-01')").run();
  seedDb.prepare("INSERT INTO agent_settings_snapshots VALUES('legacy-bot','configuration','u1','n1',1,'/ws',1,'2026-01-01','{\"ok\":true}')").run();
  seedDb.prepare("INSERT INTO agent_lifecycle_requests VALUES('legacy-bot','req-1','enabled',1)").run();

  const rawCheck = new DatabaseSync(dbPath);
  expect(() => rawCheck.prepare("UPDATE agent_profiles SET collaboration_scope='project' WHERE agent_id='legacy-bot'").run()).toThrow();
  rawCheck.close();
  seedDb.close();

  const upgraded = openDatabase(dbPath);
  cleanups.push(() => upgraded.close());
  expect(upgraded.prepare('PRAGMA foreign_keys').get()).toEqual({ foreign_keys: 1 });
  expect(upgraded.prepare('PRAGMA foreign_key_check').all()).toEqual([]);
  expect(upgraded.prepare("SELECT * FROM agent_settings_snapshots WHERE agent_id='legacy-bot'").get()).toBeTruthy();
  expect(upgraded.prepare("SELECT * FROM agent_lifecycle WHERE agent_id='legacy-bot'").get()).toBeTruthy();
  expect(upgraded.prepare("SELECT * FROM agent_lifecycle_requests WHERE agent_id='legacy-bot'").get()).toBeTruthy();
  expect(upgraded.prepare("SELECT name FROM sqlite_master WHERE type='view' AND name='owner_direct_agent_messages'").get()).toBeTruthy();
  upgraded.prepare("UPDATE agent_profiles SET collaboration_scope='project' WHERE agent_id='legacy-bot'").run();
  expect(upgraded.prepare("SELECT collaboration_scope FROM agent_profiles WHERE agent_id='legacy-bot'").get()).toEqual({ collaboration_scope: 'project' });
});

it('atomically freezes and unfreezes lost external 1:1 DMs on group membership changes and team -> project tightening', async () => {
  const { app, db, alice, bob, charlie, request, attachOnlineNode } = await createThreeUserEnv();
  const { sentFrames } = attachOnlineNode('node-alice', alice.user.owner_id, 1);

  const taskTools = ['send_message', 'task_graph', 'schedule_create', 'schedule_list', 'schedule_update', 'schedule_delete', 'schedule_run', 'schedule_history'];
  const taskFeatures = { task_graph: true, cron_scheduling: true, dreaming: false, plugin_management: false, intelligent_ui: false };

  vi.spyOn(app.im.gateway, 'request').mockImplementation(async (_node, method, payload: any) => {
    if (method === 'node.capabilities.resolve' || method === 'agent.capabilities.resolve') {
      return {
        capabilities: {
          models: [{ name: 'gpt-5.4', provider: 'openai' }],
          tools: taskTools.map(name => ({ name, default_on: true })),
          skills: [{ name: 'nano-ongoing-work', default_on: true }],
          features: [],
          commands: [],
        },
      };
    }
    if (method === 'agent.create' || method === 'agent.config.apply') {
      return {
        status: 'applied',
        operation_id: payload.operation_id,
        candidate_fingerprint: payload.candidate_fingerprint,
        agent: { ...payload.agent, workspace_root: payload.agent.workspace_root ?? `/ws/${payload.agent.agent_id}`, workspace_is_default: true },
      };
    }
    return null;
  });

  const createProj = await request(alice.access_token, 'POST', '/im/v1/nodes/node-alice/agents', {
    agent_id: 'family-health',
    display_name: '家庭健康助手',
    work_mode: 'global',
    collaboration_scope: 'project',
    skills: ['nano-ongoing-work'],
    tool_allowlist: taskTools,
    features: taskFeatures,
  });
  expect(createProj.statusCode, createProj.body).toBe(201);
  const now = new Date().toISOString();
  db.prepare(
    `INSERT INTO agent_work_sessions(session_id,root_agent_id,node_id,scope,parent_session_id,payload)
     VALUES('root-family-health','family-health','node-alice','global_main',NULL,?)`,
  ).run(JSON.stringify({ runtime: 'dsh', status: 'idle', title: 'Main', updated_at: now }));
  const familyUserId = app.im.messaging.agentUser('family-health').id;

  const famGroup = (await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: '相亲相爱一家人',
    type: 'group',
    participants: [{ type: 'user', id: bob.user.id }, { type: 'agent', id: 'family-health' }],
  })).json();

  const bobDm = (await request(bob.access_token, 'POST', '/im/v1/conversations', {
    title: 'Bob <-> 家庭健康助手',
    type: 'direct',
    participants: [{ type: 'agent', id: 'family-health' }],
  })).json();

  const agentReply = app.im.messaging.publishAgent({ kind: 'gateway', node_id: 'node-alice', owner_id: alice.user.owner_id }, 'family-health', 'op-proj-1', {
    to: `conversation:${bobDm.id}`,
    text: 'Logged!',
    from_session_id: 'root-family-health',
  } as any);

  const bobGraph = (await request(bob.access_token, 'POST', '/im/v1/task-graphs', {
    request_key: 'tg-bob-proj',
    conversation_id: bobDm.id,
    title: 'Weekly BP check',
    status: 'doing',
    assignee: { type: 'agent', id: 'family-health' },
  })).json();

  const bobTokenPayload = JSON.parse(Buffer.from(bob.access_token.split('.')[1]!, 'base64url').toString());
  (app.im.gateway.browsers as Set<any>).add({ user_id: bob.user.id, session_id: bobTokenPayload.sid, socket: { readyState: 1, close: vi.fn() } });
  const prep = await request(bob.access_token, 'POST', '/im/v1/agents/family-health/trajectory/prepare', { session_id: 'root-family-health' });
  expect(prep.statusCode, prep.body).toBe(200);
  const trajClose = vi.fn();
  app.im.gateway.trajectory.browser(Object.assign(new EventEmitter(), { readyState: 1, send: vi.fn(), close: trajClose }) as any, prep.json().ticket, 'family-health', 'root-family-health');
  const runningDmBubble = app.im.messaging.insertMessage(bobDm.id, familyUserId, 'agent', '', [], 'prov-dm-1', 'running');

  // 1. Remove Bob from famGroup -> atomic bidirectional freeze!
  sentFrames.length = 0;
  expect((await request(alice.access_token, 'DELETE', `/im/v1/conversations/${famGroup.id}/participants/${bob.user.id}`)).statusCode).toBe(204);

  expect(trajClose).toHaveBeenCalledWith(1008, expect.any(String));
  expect(db.prepare('SELECT 1 FROM messages WHERE id=?').get(runningDmBubble.id)).toBeUndefined();
  expect(sentFrames.find(f => f.type === 'agent.scope.revoked')?.payload.conversation_ids).toContain(bobDm.id);
  expect(db.prepare("SELECT 1 FROM task_context_index WHERE agent_id='family-health' AND conversation_id=? AND projection_kind='revoked'").get(bobDm.id)).toBeTruthy();

  expect((await request(bob.access_token, 'GET', `/im/v1/contacts/${familyUserId}`)).statusCode).toBe(404);
  expect((await request(bob.access_token, 'GET', '/im/v1/agents/family-health/work')).statusCode).toBe(404);
  expect((await request(bob.access_token, 'GET', `/im/v1/conversations/${bobDm.id}`)).json()).toMatchObject({
    can_write: false,
    write_blocked_reason: 'agent_project_restricted',
  });
  expect((await request(bob.access_token, 'GET', `/im/v1/conversations/${bobDm.id}/messages`)).statusCode).toBe(200);

  expect((await request(bob.access_token, 'POST', `/im/v1/conversations/${bobDm.id}/messages`, {
    sender_user_id: bob.user.id,
    content: 'Can I still write?',
  })).json()).toMatchObject({ detail: { code: 'agent_project_restricted' } });

  expect((await request(bob.access_token, 'POST', `/im/v1/conversations/${bobDm.id}/fork`, {
    fork_message_id: agentReply.message_id,
  })).json()).toMatchObject({ detail: { code: 'agent_project_restricted' } });

  expect((await request(bob.access_token, 'POST', `/im/v1/task-graphs/${bobGraph.graph_id}/apply`, {
    request_key: 'bob-blocked-apply',
    base_revision: bobGraph.revision,
    change_note: '',
    operations: [{ op: 'update_task', node_id: 'n1', patch: { title: 'Blocked' } }],
  })).json().detail).toMatchObject({ code: 'agent_project_restricted' });

  expect(() => app.im.messaging.publishAgent({ kind: 'gateway', node_id: 'node-alice', owner_id: alice.user.owner_id }, 'family-health', 'op-proj-blocked', {
    to: `conversation:${bobDm.id}`,
    text: 'Agent attempt after Bob left',
    from_session_id: 'root-family-health',
  } as any)).toThrow(expect.objectContaining({ statusCode: 403, detail: expect.objectContaining({ code: 'collaboration_scope_restricted' }) }));
  expect(() => app.im.messaging.resolveTarget('family-health', `user:${bob.user.id}`)).toThrow(
    expect.objectContaining({ statusCode: 403, detail: expect.objectContaining({ code: 'collaboration_scope_restricted' }) }),
  );

  const pinRes = await request(bob.access_token, 'PATCH', `/im/v1/conversations/${bobDm.id}`, { is_pinned: true, is_muted: true });
  expect(pinRes.statusCode, pinRes.body).toBe(200);
  expect(pinRes.json()).toMatchObject({ is_pinned: true, is_muted: true });

  // 2. Re-adding Bob to famGroup automatically unfreezes bobDm!
  expect((await request(alice.access_token, 'POST', `/im/v1/conversations/${famGroup.id}/participants`, {
    participants: [{ type: 'user', id: bob.user.id }],
  })).statusCode).toBe(200);
  expect((await request(bob.access_token, 'GET', `/im/v1/conversations/${bobDm.id}`)).json()).toMatchObject({
    can_write: true,
    write_blocked_reason: null,
  });

  // 3. Widen family-health -> 'team', put it in a public group + Charlie 1:1 DM, then tighten 'team' -> 'project':
  // Exits public group, freezes Charlie's DM, while keeping famGroup & Bob's DM writable!
  expect((await request(alice.access_token, 'PATCH', '/im/v1/agents/family-health/config', {
    profile_version: 1,
    display_name: '家庭健康助手',
    collaboration_scope: 'team',
    skills: ['nano-ongoing-work'],
    tool_allowlist: taskTools,
    features: taskFeatures,
  })).statusCode).toBe(200);

  const pubTownhall = (await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: 'Townhall',
    type: 'group',
    visibility: 'public',
    participants: [{ type: 'user', id: charlie.user.id }, { type: 'agent', id: 'family-health' }],
  })).json();
  const charlieDm = (await request(charlie.access_token, 'POST', '/im/v1/conversations', {
    title: 'Charlie <-> 家庭健康助手',
    type: 'direct',
    participants: [{ type: 'agent', id: 'family-health' }],
  })).json();
  expect(charlieDm.can_write).toBe(true);

  sentFrames.length = 0;
  // Enqueue messages in famGroup and bobDm while still in 'team' scope (and inject a legacy relay_task lacking project_allowed)
  const preTightenGroupMsg = (await request(bob.access_token, 'POST', `/im/v1/conversations/${famGroup.id}/messages`, {
    sender_user_id: bob.user.id,
    content: 'Before team->project tighten in group',
  })).json();
  expect(sentFrames.find(f => f.type === 'relay.message' && f.payload.message?.id === preTightenGroupMsg.id)?.payload.metadata?.project_allowed).toBe(true);
  const preTightenDmMsg = (await request(bob.access_token, 'POST', `/im/v1/conversations/${bobDm.id}/messages`, {
    sender_user_id: bob.user.id,
    content: 'Before team->project tighten in DM',
  })).json();
  // Simulate an undelivered legacy relay_task enqueued without metadata.project_allowed before tightening to 'project'
  const legacyRelay = db.prepare('SELECT * FROM relay_tasks WHERE message_id=?').get(preTightenDmMsg.id) as { relay_task_id: string; payload_json: string };
  const strippedPayload = JSON.parse(legacyRelay.payload_json);
  delete strippedPayload.metadata.project_allowed;
  db.prepare("UPDATE relay_tasks SET status='queued',receipt_status=NULL,payload_json=? WHERE relay_task_id=?").run(
    JSON.stringify(strippedPayload),
    legacyRelay.relay_task_id,
  );

  sentFrames.length = 0;
  expect((await request(alice.access_token, 'PATCH', '/im/v1/agents/family-health/config', {
    profile_version: 2,
    display_name: '家庭健康助手',
    collaboration_scope: 'project',
    skills: ['nano-ongoing-work'],
    tool_allowlist: taskTools,
    features: taskFeatures,
  })).statusCode).toBe(200);

  const delivery = (app.im.messaging as unknown as { delivery: { disconnect: (node: string) => void; drain: (node?: string) => boolean } }).delivery;
  delivery.disconnect('node-alice');
  delivery.drain('node-alice');
  const redrainedDmFrame = sentFrames.find(f => f.type === 'relay.message' && f.payload.message?.id === preTightenDmMsg.id);
  expect(redrainedDmFrame?.payload.metadata?.project_allowed).toBe(true);

  expect(db.prepare('SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?').get(pubTownhall.id, familyUserId)).toBeUndefined();
  expect(db.prepare('SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?').get(famGroup.id, familyUserId)).toBeTruthy();
  expect((await request(charlie.access_token, 'GET', `/im/v1/conversations/${charlieDm.id}`)).json()).toMatchObject({
    can_write: false,
    write_blocked_reason: 'agent_project_restricted',
  });
  expect((await request(bob.access_token, 'GET', `/im/v1/conversations/${bobDm.id}`)).json()).toMatchObject({
    can_write: true,
    write_blocked_reason: null,
  });
  const projRevoked = sentFrames.find(f => f.type === 'agent.scope.revoked')?.payload.conversation_ids ?? [];
  expect(projRevoked).toEqual(expect.arrayContaining([pubTownhall.id, charlieDm.id]));
  expect(projRevoked).not.toContain(famGroup.id);
  expect(projRevoked).not.toContain(bobDm.id);
});
