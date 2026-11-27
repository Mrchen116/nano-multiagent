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

async function createThreeUserEnv() {
  const dir = mkdtempSync(join(tmpdir(), 'im-proj-scope-'));
  cleanups.push(() => rmSync(dir, { recursive: true, force: true }));
  const app = await createServer({ dbPath: join(dir, 'im.db'), publicUrl: 'http://localhost', jwtSecret: 'proj-scope-secret' });
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

it('enforces 3-tier ordinary/global scope vs 2-tier PA scope, group governance, cross-group confirmation, Work transparency, and 1:1 DM access', async () => {
  const { app, db, alice, bob, charlie, request, attachOnlineNode } = await createThreeUserEnv();
  db.prepare("UPDATE users SET personal_space_enabled=1 WHERE id=?").run(alice.user.id);
  attachOnlineNode('node-alice', alice.user.owner_id, 1);

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

  // 1. PA rejects 'project' at creation AND at PATCH /im/v1/agents/:id/config (422 invalid_collaboration_scope).
  const badPa = await request(alice.access_token, 'POST', '/im/v1/personal-agent', {
    request_key: 'pa-proj-bad',
    node_id: 'node-alice',
    display_name: 'Alice PA',
    collaboration_scope: 'project',
  });
  expect(badPa.statusCode).toBe(422);

  const paRes = await request(alice.access_token, 'POST', '/im/v1/personal-agent', {
    request_key: 'pa-alice',
    node_id: 'node-alice',
    display_name: 'Alice PA',
    collaboration_scope: 'owner_only',
  });
  expect(paRes.statusCode, paRes.body).toBe(201);
  const paBinding = paRes.json().binding;

  const patchPaProject = await request(alice.access_token, 'PATCH', `/im/v1/agents/${paBinding.agent_id}/config`, {
    profile_version: 1,
    display_name: 'Alice PA',
    collaboration_scope: 'project',
    confirm_scope_widen: true,
  });
  expect(patchPaProject.statusCode).toBe(422);

  // PA agent_creation(options) advertises team / project / owner_only for newly created ordinary/global Agents!
  const optionsRes = await app.im.personal.handle(
    { node_id: 'node-alice', owner_id: alice.user.owner_id, node_epoch: 1 },
    'pa.agent.creation',
    { agent_id: paBinding.agent_id, binding_id: paBinding.binding_id, epoch: 1, action: 'options' },
  );
  expect(String(optionsRes.configuration_fields.collaboration_scope)).toContain('project');

  // 2. Create a personal-space Global Agent with collaboration_scope='project'.
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
  expect(createProj.json()).toMatchObject({
    collaboration_scope: 'project',
    space_id: `personal:${alice.user.owner_id}`,
  });
  const now = new Date().toISOString();
  db.prepare(
    `INSERT INTO agent_work_sessions(session_id,root_agent_id,node_id,scope,parent_session_id,payload)
     VALUES('root-family-health','family-health','node-alice','global_main',NULL,?)`,
  ).run(JSON.stringify({ runtime: 'dsh', status: 'idle', title: 'Main', updated_at: now }));

  // Before joining any private group: hidden from Bob & Charlie in contacts, 1:1 DM, lifecycle, Work, and Agent resolveTarget!
  const familyUserId = app.im.messaging.agentUser('family-health').id;
  for (const outsider of [bob, charlie]) {
    expect((await request(outsider.access_token, 'GET', '/im/v1/contacts')).json().items.map((c: any) => c.agent_id)).not.toContain('family-health');
    expect((await request(outsider.access_token, 'GET', `/im/v1/contacts/${familyUserId}`)).statusCode).toBe(404);
    expect((await request(outsider.access_token, 'GET', '/im/v1/agents/family-health/lifecycle')).statusCode).toBe(404);
    expect((await request(outsider.access_token, 'GET', '/im/v1/agents/family-health/work')).statusCode).toBe(404);
    expect((await request(outsider.access_token, 'POST', '/im/v1/conversations', {
      title: 'DM Attempt',
      type: 'direct',
      participants: [{ type: 'agent', id: 'family-health' }],
    })).statusCode).toBe(404);
  }
  expect(() => app.im.messaging.resolveTarget('family-health', `user:${bob.user.id}`)).toThrow();

  // 3. Group governance: cannot put project Agent in public group (409 project_agent_requires_private_group).
  const pubAttempt = await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: 'Public Family',
    type: 'group',
    visibility: 'public',
    participants: [{ type: 'user', id: bob.user.id }, { type: 'agent', id: 'family-health' }],
  });
  expect(pubAttempt.statusCode).toBe(409);
  expect(pubAttempt.json()).toMatchObject({ detail: { code: 'project_agent_requires_private_group' } });

  // Alice creates private group "相亲相爱一家人" with Bob and family-health -> succeeds as private company:default group!
  const famGroupRes = await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: '相亲相爱一家人',
    type: 'group',
    participants: [{ type: 'user', id: bob.user.id }, { type: 'agent', id: 'family-health' }],
  });
  expect(famGroupRes.statusCode, famGroupRes.body).toBe(201);
  const famGroup = famGroupRes.json();
  expect(famGroup).toMatchObject({
    visibility: 'private',
    space_id: 'company:default',
    can_change_visibility: false,
  });

  // Cannot switch famGroup to public (409 project_agent_requires_private_group).
  const makePub = await request(alice.access_token, 'PATCH', `/im/v1/conversations/${famGroup.id}`, { visibility: 'public' });
  expect(makePub.statusCode).toBe(409);
  expect(makePub.json()).toMatchObject({ detail: { code: 'project_agent_requires_private_group' } });

  // 4. Now Bob is a same-project member, while Charlie remains an outsider!
  expect((await request(bob.access_token, 'GET', '/im/v1/contacts')).json().items.map((c: any) => c.agent_id)).toContain('family-health');
  expect((await request(bob.access_token, 'GET', `/im/v1/contacts/${familyUserId}`)).statusCode).toBe(200);
  expect((await request(bob.access_token, 'GET', '/im/v1/agents/family-health/lifecycle')).statusCode).toBe(200);
  expect((await request(bob.access_token, 'GET', '/im/v1/agents/family-health/work')).statusCode).toBe(200);
  // PA Work remains strictly owner-only even if PA were widened!
  expect((await request(bob.access_token, 'GET', `/im/v1/agents/${paBinding.agent_id}/work`)).statusCode).toBe(404);
  // Charlie still gets 404 everywhere.
  expect((await request(charlie.access_token, 'GET', `/im/v1/contacts/${familyUserId}`)).statusCode).toBe(404);
  expect((await request(charlie.access_token, 'GET', '/im/v1/agents/family-health/work')).statusCode).toBe(404);

  // Realtime agent.work.updated broadcasts to Alice AND Bob (even though family-health is in personal:<alice>), NOT Charlie!
  const broadcastTargets: string[][] = [];
  const origBroadcast = app.im.gateway.broadcast.bind(app.im.gateway);
  const broadcastSpy = vi.spyOn(app.im.gateway, 'broadcast').mockImplementation((targets: any, frame: any) => {
    if (frame?.event_type === 'agent.work.updated') broadcastTargets.push(Array.isArray(targets) ? targets : []);
    return origBroadcast(targets, frame);
  });
  (app.im.gateway.browsers as Set<any>).add({ userId: alice.user.id, user_id: alice.user.id, session_id: 's-alice', socket: { readyState: 1, send: vi.fn(), close: vi.fn() } });
  (app.im.gateway.browsers as Set<any>).add({ userId: bob.user.id, user_id: bob.user.id, session_id: 's-bob', socket: { readyState: 1, send: vi.fn(), close: vi.fn() } });
  (app.im.gateway.browsers as Set<any>).add({ userId: charlie.user.id, user_id: charlie.user.id, session_id: 's-charlie', socket: { readyState: 1, send: vi.fn(), close: vi.fn() } });
  app.im.gateway.work.append('node-alice', {
    journal_id: 'j-1',
    from_seq: 1,
    events: [{
      seq: 1,
      event_id: 'ev-1',
      root_agent_id: 'family-health',
      session_id: 'root-family-health',
      turn_id: 't-1',
      type: 'turn_started',
      observed_at: now,
      payload: { started_at: now },
    }],
  });
  expect(broadcastTargets.at(-1)).toEqual(expect.arrayContaining([alice.user.id, bob.user.id]));
  expect(broadcastTargets.at(-1)).not.toContain(charlie.user.id);
  broadcastSpy.mockRestore();

  // Bob CANNOT invite Alice's project Agent into another group (403 agent_owner_required),
  // AND Bob CANNOT add external Charlie into famGroup containing Alice's project Agent (403 project_agent_owner_required)!
  const bobOtherGroup = await request(bob.access_token, 'POST', '/im/v1/conversations', {
    title: 'Bob Side Group',
    type: 'group',
    visibility: 'private',
    participants: [{ type: 'agent', id: 'family-health' }],
  });
  expect(bobOtherGroup.statusCode).toBe(403);
  expect(bobOtherGroup.json()).toMatchObject({ detail: { code: 'agent_owner_required' } });

  const bobExpandGroup = await request(bob.access_token, 'POST', `/im/v1/conversations/${famGroup.id}/participants`, {
    participants: [{ type: 'user', id: charlie.user.id }],
  });
  expect(bobExpandGroup.statusCode).toBe(403);
  expect(bobExpandGroup.json()).toMatchObject({ detail: { code: 'project_agent_owner_required' } });

  // 5. Cross-group context share confirmation for Global project Agent:
  // Creating a 2nd private group with identical external human set ([Bob]) succeeds WITHOUT confirmation,
  // whereas creating one with different external human set ([Charlie]) returns 409 until confirm_project_context_share: true!
  const sameMembersGroup = await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: 'Family Diet Subtopic',
    type: 'group',
    visibility: 'private',
    participants: [{ type: 'user', id: bob.user.id }, { type: 'agent', id: 'family-health' }],
  });
  expect(sameMembersGroup.statusCode, sameMembersGroup.body).toBe(201);
  expect((await request(alice.access_token, 'DELETE', `/im/v1/conversations/${sameMembersGroup.json().id}`)).statusCode).toBe(204);

  const crossGroupUnconfirmed = await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: 'Charlie Project',
    type: 'group',
    visibility: 'private',
    participants: [{ type: 'user', id: charlie.user.id }, { type: 'agent', id: 'family-health' }],
  });
  expect(crossGroupUnconfirmed.statusCode).toBe(409);
  expect(crossGroupUnconfirmed.json()).toMatchObject({
    detail: { code: 'project_agent_cross_group_confirmation_required', agent_ids: ['family-health'] },
  });

  const crossGroupConfirmed = await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: 'Charlie Project',
    type: 'group',
    visibility: 'private',
    confirm_project_context_share: true,
    participants: [{ type: 'user', id: charlie.user.id }, { type: 'agent', id: 'family-health' }],
  });
  expect(crossGroupConfirmed.statusCode, crossGroupConfirmed.body).toBe(201);
  expect((await request(alice.access_token, 'DELETE', `/im/v1/conversations/${crossGroupConfirmed.json().id}`)).statusCode).toBe(204);

  // 6. Bob 1:1 DMs family-health -> bidirectional messaging & task graph work, relay carries project_allowed=true!
  const bobDmRes = await request(bob.access_token, 'POST', '/im/v1/conversations', {
    title: 'Bob <-> 家庭健康助手',
    type: 'direct',
    participants: [{ type: 'agent', id: 'family-health' }],
  });
  expect(bobDmRes.statusCode, bobDmRes.body).toBe(201);
  const bobDm = bobDmRes.json();
  expect(bobDm).toMatchObject({ can_write: true, write_blocked_reason: null });

  const bobMsgRes = await request(bob.access_token, 'POST', `/im/v1/conversations/${bobDm.id}/messages`, {
    sender_user_id: bob.user.id,
    content: 'Here is the blood pressure log',
  });
  expect(bobMsgRes.statusCode, bobMsgRes.body).toBe(201);
  const dmRelay = db.prepare('SELECT payload_json FROM relay_tasks WHERE message_id=?').get(bobMsgRes.json().id) as any;
  expect(JSON.parse(dmRelay.payload_json).metadata).toMatchObject({ project_allowed: true, addressed_to_agent: true });

  const agentReply = app.im.messaging.publishAgent({ kind: 'gateway', node_id: 'node-alice', owner_id: alice.user.owner_id }, 'family-health', 'op-proj-1', {
    to: `conversation:${bobDm.id}`,
    text: 'Logged!',
    from_session_id: 'root-family-health',
  } as any);
  expect(agentReply.message_id).toBeTruthy();
});
