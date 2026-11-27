import { EventEmitter } from 'node:events';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, expect, it, vi } from 'vitest';
import { createServer } from '../src/server.js';
import type { Connection } from '../src/gateway.js';

const cleanups: Array<() => unknown | Promise<unknown>> = [];
afterEach(async () => {
  for (const close of cleanups.splice(0).reverse()) await close();
});

async function createTestEnv() {
  const dir = mkdtempSync(join(tmpdir(), 'im-privacy-vis-'));
  cleanups.push(() => rmSync(dir, { recursive: true, force: true }));
  const app = await createServer({ dbPath: join(dir, 'im.db'), publicUrl: 'http://localhost', jwtSecret: 'privacy-test-secret' });
  cleanups.push(() => app.close());

  const alice = await app.im.identity.register('alice', 'password-123', 'Alice');
  app.im.identity.initializeCompany(alice.user.id);
  const bob = await app.im.identity.register('bob', 'password-123', 'Bob');
  app.im.db.prepare("UPDATE users SET membership_status='active' WHERE id=?").run(bob.user.id);

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
    const connection = { node_id: nodeId, owner_id: ownerId, node_epoch: epoch, socket: socket as any } as Connection;
    app.im.gateway.nodes.set(nodeId, connection);
    return { connection, sentFrames };
  };

  return { app, db: app.im.db, alice, bob, request, attachOnlineNode };
}

it('creates PA with team default or owner_only, preserves request_key idempotency, and rejects conflicting scope retries', async () => {
  const { app, alice, bob, request, attachOnlineNode } = await createTestEnv();
  attachOnlineNode('node-alice', alice.user.owner_id);
  attachOnlineNode('node-bob', bob.user.owner_id);

  vi.spyOn(app.im.gateway, 'request').mockImplementation(async (_node, method, payload: any) => {
    if (method === 'node.capabilities.resolve') return { capabilities: { tools: [{ name: 'send_message', default_on: true }] } };
    if (method === 'agent.create') {
      return {
        status: 'applied',
        operation_id: payload.operation_id,
        candidate_fingerprint: payload.candidate_fingerprint,
        agent: { ...payload.agent, workspace_root: `/ws/${payload.agent.agent_id}`, workspace_is_default: true },
      };
    }
    return null;
  });

  // Invalid scope rejected with 422.
  const bad = await request(alice.access_token, 'POST', '/im/v1/personal-agent', {
    request_key: 'pa-bad',
    node_id: 'node-alice',
    display_name: 'Bad PA',
    collaboration_scope: 'secret',
  });
  expect(bad.statusCode).toBe(422);

  // Create Alice PA directly as owner_only.
  const createdPrivate = await request(alice.access_token, 'POST', '/im/v1/personal-agent', {
    request_key: 'pa-alice-priv',
    node_id: 'node-alice',
    display_name: 'Alice Secret PA',
    collaboration_scope: 'owner_only',
  });
  expect(createdPrivate.statusCode, createdPrivate.body).toBe(201);
  expect(createdPrivate.json().binding).toMatchObject({
    collaboration_scope: 'owner_only',
    status: 'active',
  });
  expect((await request(alice.access_token, 'GET', '/im/v1/personal-agent')).json().binding.collaboration_scope).toBe('owner_only');

  // Same request_key omitting scope returns idempotent owner_only; conflicting scope returns 409.
  const idempotent = await request(alice.access_token, 'POST', '/im/v1/personal-agent', {
    request_key: 'pa-alice-priv',
    node_id: 'node-alice',
    display_name: 'Alice Secret PA',
  });
  expect(idempotent.statusCode).toBe(200);
  expect(idempotent.json().binding.collaboration_scope).toBe('owner_only');

  const conflict = await request(alice.access_token, 'POST', '/im/v1/personal-agent', {
    request_key: 'pa-alice-priv',
    node_id: 'node-alice',
    display_name: 'Alice Secret PA',
    collaboration_scope: 'team',
  });
  expect(conflict.statusCode).toBe(409);

  // Bob cannot see or contact Alice's private PA, whereas Bob's default PA is 'team' and visible to Alice.
  const paAliceUserId = app.im.messaging.agentUser(createdPrivate.json().binding.agent_id).id;
  expect((await request(bob.access_token, 'GET', `/im/v1/contacts/${paAliceUserId}`)).statusCode).toBe(404);
  expect((await request(bob.access_token, 'GET', '/im/v1/contacts')).json().items.map((x: any) => x.user_id)).not.toContain(paAliceUserId);
  expect((await request(bob.access_token, 'POST', '/im/v1/conversations', {
    title: 'Intrude PA',
    type: 'direct',
    participants: [{ type: 'agent', id: createdPrivate.json().binding.agent_id }],
  })).statusCode).toBe(404);

  const createdDefault = await request(bob.access_token, 'POST', '/im/v1/personal-agent', {
    request_key: 'pa-bob-default',
    node_id: 'node-bob',
    display_name: 'Bob Public PA',
  });
  expect(createdDefault.statusCode).toBe(201);
  expect(createdDefault.json().binding.collaboration_scope).toBe('team');
  const paBobUserId = app.im.messaging.agentUser(createdDefault.json().binding.agent_id).id;
  expect((await request(alice.access_token, 'GET', `/im/v1/contacts/${paBobUserId}`)).statusCode).toBe(200);
});

it('exposes personal-space active colleague team Agents end-to-end while hiding owner_only Agents and kicking trajectory WS on tightening', async () => {
  const { app, db, alice, bob, request, attachOnlineNode } = await createTestEnv();
  // Enable personal space on Alice (simulating a user who enabled personal space via PA or prior registration).
  db.prepare("UPDATE users SET personal_space_enabled=1 WHERE id=?").run(alice.user.id);
  attachOnlineNode('node-alice', alice.user.owner_id, 3);

  const now = new Date().toISOString();
  // Create two Global Agents in Alice's personal space: one 'team', one 'owner_only'.
  for (const [id, name, scope] of [
    ['alice-team-eng', 'Team Engineer', 'team'],
    ['alice-priv-eng', 'Private Engineer', 'owner_only'],
  ] as const) {
    db.prepare(
      `INSERT INTO agent_profiles(agent_id,owner_id,space_id,node_id,display_name,collaboration_scope,work_mode,workspace_root,skills_json,features_json,is_stale,created_at,updated_at)
       VALUES(?,?,?,?,?,?,'global',?,'["deploy"]','{"intelligent_ui":false,"task_graph":false}',0,?,?)`,
    ).run(id, alice.user.owner_id, `personal:${alice.user.owner_id}`, 'node-alice', name, scope, `/ws/${id}`, now, now);
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES(?,?,?,?,?)")
      .run(`u-${id}`, `agent:${id}`, name, alice.user.owner_id, now);
    db.prepare(
      `INSERT INTO agent_work_sessions(session_id,root_agent_id,node_id,scope,parent_session_id,payload)
       VALUES(?,?,'node-alice','global_main',NULL,?)`,
    ).run(`root-${id}`, id, JSON.stringify({ runtime: 'dsh', status: 'idle', title: 'Main', updated_at: now }));
  }

  // Bob sees alice-team-eng in contacts, slash commands, Work, and native trajectory, NOT alice-priv-eng!
  const bobContacts = (await request(bob.access_token, 'GET', '/im/v1/contacts')).json().items;
  expect(bobContacts.map((c: any) => c.agent_id).filter(Boolean)).toEqual(['alice-team-eng']);
  expect((await request(bob.access_token, 'GET', '/im/v1/contacts/u-alice-priv-eng')).statusCode).toBe(404);
  expect((await request(bob.access_token, 'GET', '/im/v1/agents/alice-team-eng/work')).statusCode).toBe(200);
  expect((await request(bob.access_token, 'GET', '/im/v1/agents/alice-priv-eng/work')).statusCode).toBe(404);

  // Colleague Bob creates a 1:1 chat with Alice's personal-space 'team' Agent -> lands in company:default, slash commands & Agent replies work!
  const bobChatRes = await request(bob.access_token, 'POST', '/im/v1/conversations', {
    title: 'Bob <-> Alice Team Agent',
    type: 'direct',
    participants: [{ type: 'agent', id: 'alice-team-eng' }],
  });
  expect(bobChatRes.statusCode, bobChatRes.body).toBe(201);
  const bobChat = bobChatRes.json();
  expect(bobChat).toMatchObject({ space_id: 'company:default', can_write: true });

  vi.spyOn(app.im.gateway, 'request').mockImplementation(async (_node, cmd, payload: any) => {
    if (cmd === 'agent.config.get') return { agent: { skills: ['deploy'], skills_selection_mode: 'explicit_allowlist' } };
    if (cmd === 'agent.capabilities.resolve' || cmd === 'node.capabilities.resolve') {
      return {
        capabilities: {
          tools: [],
          features: [],
          skills: [{ name: 'deploy', description: 'Deploy release' }],
          commands: [{ name: 'ship', description: 'Ship release' }],
        },
      };
    }
    return {
      status: 'applied',
      operation_id: payload.operation_id,
      candidate_fingerprint: payload.candidate_fingerprint,
      agent: payload.agent,
    };
  });

  const commandsRes = await request(bob.access_token, 'GET', `/im/v1/conversations/${bobChat.id}/commands?agent_id=alice-team-eng`);
  expect(commandsRes.statusCode).toBe(200);
  expect(commandsRes.json().items[0]).toMatchObject({ status: 'available' });
  expect(commandsRes.json().items[0].commands.length).toBeGreaterThan(0);

  // Agent publishes a reply into company:default chat across personal:<alice> space boundary.
  const reply = app.im.messaging.publishAgent({ kind: 'gateway', node_id: 'node-alice', owner_id: alice.user.owner_id }, 'alice-team-eng', 'op-cross-1', {
    to: `conversation:${bobChat.id}`,
    text: 'Cross-space team reply!',
    from_session_id: 'alice-team-eng|sess:1',
  } as any);
  expect(reply.message_id).toBeTruthy();

  // Bob opens a native trajectory observer WebSocket on alice-team-eng; when Alice tightens to owner_only, Bob's WS closes with 1008!
  const prep = await request(bob.access_token, 'POST', '/im/v1/agents/alice-team-eng/trajectory/prepare', { session_id: 'root-alice-team-eng' });
  expect(prep.statusCode, prep.body).toBe(200);
  const closeSpy = vi.fn();
  const browserWs = Object.assign(new EventEmitter(), {
    readyState: 1,
    send: vi.fn(),
    close: closeSpy,
  });
  // Register Bob's browser session in gateway.browsers so browserValid returns true before tightening.
  const bobTokenPayload = JSON.parse(Buffer.from(bob.access_token.split('.')[1]!, 'base64url').toString());
  (app.im.gateway.browsers as Set<any>).add({ user_id: bob.user.id, session_id: bobTokenPayload.session_id, socket: { readyState: 1, close: vi.fn() } });
  app.im.gateway.trajectory.browser(browserWs as any, prep.json().ticket, 'alice-team-eng', 'root-alice-team-eng');
  expect(closeSpy).not.toHaveBeenCalled();

  const tighten = await request(alice.access_token, 'PATCH', '/im/v1/agents/alice-team-eng/config', {
    profile_version: 1,
    display_name: 'Team Engineer',
    collaboration_scope: 'owner_only',
  });
  expect(tighten.statusCode, tighten.body).toBe(200);
  expect(closeSpy).toHaveBeenCalledWith(1008, expect.any(String));
  expect((await request(bob.access_token, 'POST', '/im/v1/agents/alice-team-eng/trajectory/authorize', { session_id: 'root-alice-team-eng' })).statusCode).toBe(404);
  const authAttach = await request(bob.access_token, 'POST', '/im/v1/agents/alice-team-eng/trajectory/authorize-attachment', {
    sources: [{ kind: 'workspace', path: 'out.png' }],
  });
  expect(authAttach.statusCode).toBe(200);
  expect(authAttach.json()).toEqual({ allowed: false });
});

it('aligns TaskGraphService cross-space team visibility, owner_only list/focus safety, frozen DM task write block, and tightening task_context revocations', async () => {
  const { app, db, alice, bob, request, attachOnlineNode } = await createTestEnv();
  db.prepare("UPDATE users SET personal_space_enabled=1 WHERE id=?").run(alice.user.id);
  const { sentFrames } = attachOnlineNode('node-alice', alice.user.owner_id);

  const taskFeatures = { task_graph: true, cron_scheduling: true, dreaming: false, plugin_management: false, intelligent_ui: false };
  const taskTools = ['send_message', 'task_graph', 'schedule_create', 'schedule_list', 'schedule_update', 'schedule_delete', 'schedule_run', 'schedule_history'];

  vi.spyOn(app.im.gateway, 'request').mockImplementation(async (_node, method, payload: any) => {
    if (method === 'node.capabilities.resolve') {
      return {
        capabilities: {
          tools: taskTools.map(name => ({ name, default_on: true })),
          skills: [{ name: 'nano-ongoing-work', default_on: true }],
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

  // 1. Alice (active team + personal_space_enabled=1) creates a team Global Agent (in personal:<alice>) AND a company-space Global Agent.
  const createCrossRes = await request(alice.access_token, 'POST', '/im/v1/nodes/node-alice/agents', {
    agent_id: 'alice-personal-team',
    display_name: 'Cross Space Planner',
    work_mode: 'global',
    collaboration_scope: 'team',
    skills: ['nano-ongoing-work'],
    tool_allowlist: taskTools,
    features: taskFeatures,
  });
  expect(createCrossRes.statusCode, createCrossRes.body).toBe(201);
  expect(createCrossRes.json().space_id).toBe(`personal:${alice.user.owner_id}`);

  const now = new Date().toISOString();
  db.prepare(
    `INSERT INTO agent_profiles(agent_id,owner_id,space_id,node_id,display_name,collaboration_scope,work_mode,skills_json,tool_allowlist_json,features_json,profile_version,is_stale,created_at,updated_at)
     VALUES('alice-company-bot',?,'company:default','node-alice','Company Bot','team','global','["nano-ongoing-work"]',?,?,1,0,?,?)`,
  ).run(alice.user.owner_id, JSON.stringify(taskTools), JSON.stringify(taskFeatures), now, now);
  db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES('u-company-bot','agent:alice-company-bot','Company Bot',?,?)").run(alice.user.owner_id, now);

  // Create a public company group containing Alice, Bob, alice-personal-team, and alice-company-bot, plus a Bob <-> alice-company-bot 1:1 DM, plus an Alice <-> alice-company-bot internal DM.
  const pubGroup = (await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: 'Public Roadmap',
    type: 'group',
    visibility: 'public',
    participants: [
      { type: 'user', id: bob.user.id },
      { type: 'agent', id: 'alice-personal-team' },
      { type: 'agent', id: 'alice-company-bot' },
    ],
  })).json();
  const bobDm = (await request(bob.access_token, 'POST', '/im/v1/conversations', {
    title: 'Bob <-> Company Bot',
    type: 'direct',
    participants: [{ type: 'agent', id: 'alice-company-bot' }],
  })).json();
  const ownerDm = (await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: 'Alice <-> Company Bot',
    type: 'direct',
    participants: [{ type: 'agent', id: 'alice-company-bot' }],
  })).json();

  // Assign a doing task in company:default group to alice-personal-team (cross-space) and tasks in pubGroup + bobDm + ownerDm to alice-company-bot.
  expect((await request(alice.access_token, 'POST', '/im/v1/task-graphs', {
    request_key: 'tg-cross-1',
    conversation_id: pubGroup.id,
    title: 'Cross-space deliverable',
    status: 'doing',
    assignee: { type: 'agent', id: 'alice-personal-team' },
  })).statusCode).toBe(200);
  const bobDmGraph = (await request(bob.access_token, 'POST', '/im/v1/task-graphs', {
    request_key: 'tg-bob-dm-1',
    conversation_id: bobDm.id,
    title: 'External colleague DM task',
    status: 'doing',
    assignee: { type: 'agent', id: 'alice-company-bot' },
  })).json();
  expect((await request(alice.access_token, 'POST', '/im/v1/task-graphs', {
    request_key: 'tg-pub-bot-1',
    conversation_id: pubGroup.id,
    title: 'Public group bot task',
    status: 'doing',
    assignee: { type: 'agent', id: 'alice-company-bot' },
  })).statusCode).toBe(200);
  const ownerDmGraph = (await request(alice.access_token, 'POST', '/im/v1/task-graphs', {
    request_key: 'tg-owner-dm-1',
    conversation_id: ownerDm.id,
    title: 'Owner private task',
    status: 'doing',
    assignee: { type: 'agent', id: 'alice-company-bot' },
  })).json();

  // Cross-space team Global Agent sees its company:default task in list, focus, and executionScopes!
  const crossActor = { kind: 'agent' as const, id: 'alice-personal-team', node_id: 'node-alice', lifecycle_revision: 1 };
  expect(app.im.gateway.tasks.execute(crossActor, 'list', {}).items.map((i: any) => i.title)).toContain('Cross-space deliverable');
  expect(app.im.gateway.tasks.execute(crossActor, 'focus', { scope: 'all' }).active.map((i: any) => i.title)).toContain('Cross-space deliverable');
  expect(app.im.gateway.tasks.executionScopes(crossActor).conversation_ids).toContain(pubGroup.id);

  // 2. Tighten alice-company-bot from team -> owner_only via PATCH config!
  sentFrames.length = 0;
  const tighten = await request(alice.access_token, 'PATCH', '/im/v1/agents/alice-company-bot/config', {
    profile_version: 1,
    display_name: 'Company Bot',
    work_mode: 'global',
    collaboration_scope: 'owner_only',
    skills: ['nano-ongoing-work'],
    tool_allowlist: taskTools,
    features: taskFeatures,
  });
  expect(tighten.statusCode, tighten.body).toBe(200);

  // Durable task_context_index revocations recorded AND delivered via relay.message for BOTH exited pubGroup AND frozen bobDm!
  const revokedConvs = db.prepare("SELECT conversation_id FROM task_context_index WHERE agent_id='alice-company-bot' AND projection_kind='revoked'")
    .all().map((r: any) => r.conversation_id);
  expect(revokedConvs).toEqual(expect.arrayContaining([pubGroup.id, bobDm.id]));
  expect(revokedConvs).not.toContain(ownerDm.id);
  const revokedRelays = sentFrames.filter(f => f.type === 'relay.message' && f.payload.agent_id === 'alice-company-bot' && f.payload.message?.system_notice?.change_kinds?.includes('access_revoked'));
  expect(revokedRelays.map(f => f.payload.conversation_id)).toEqual(expect.arrayContaining([pubGroup.id, bobDm.id]));

  // 3. owner_only alice-company-bot calling list, focus, and executionScopes does NOT crash on public groups or frozen bobDm, and returns only ownerDm!
  const privateActor = { kind: 'agent' as const, id: 'alice-company-bot', node_id: 'node-alice', lifecycle_revision: 1 };
  expect(app.im.gateway.tasks.execute(privateActor, 'list', {}).items.map((i: any) => i.graph_id)).toEqual([ownerDmGraph.graph_id]);
  expect(app.im.gateway.tasks.execute(privateActor, 'focus', { scope: 'all' }).active.map((i: any) => i.graph_id)).toEqual([ownerDmGraph.graph_id]);
  expect(app.im.gateway.tasks.executionScopes(privateActor).conversation_ids).toEqual([ownerDm.id]);

  // 4. Colleague Bob in frozen agent_private bobDm can still read existing task graph, but create/apply/delete are blocked with 403 agent_private!
  expect((await request(bob.access_token, 'GET', `/im/v1/task-graphs/${bobDmGraph.graph_id}`)).statusCode).toBe(200);
  for (const writeRes of [
    await request(bob.access_token, 'POST', '/im/v1/task-graphs', { request_key: 'bob-blocked-create', conversation_id: bobDm.id, title: 'Blocked' }),
    await request(bob.access_token, 'POST', `/im/v1/task-graphs/${bobDmGraph.graph_id}/apply`, { request_key: 'bob-blocked-apply', base_revision: bobDmGraph.revision, change_note: '', operations: [{ op: 'update_task', node_id: 'n1', patch: { title: 'Mutated' } }] }),
    await request(bob.access_token, 'DELETE', `/im/v1/task-graphs/${bobDmGraph.graph_id}`, { request_key: 'bob-blocked-del', base_revision: bobDmGraph.revision, node_id: 'n1' }),
  ]) {
    expect(writeRes.statusCode).toBe(403);
    expect(writeRes.json().detail).toMatchObject({ code: 'agent_private' });
  }
});
