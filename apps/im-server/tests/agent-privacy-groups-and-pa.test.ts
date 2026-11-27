import { EventEmitter } from 'node:events';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, expect, it, vi } from 'vitest';
import { createServer } from '../src/server.js';
import { TaskGraphService } from '../src/task-graphs.js';
import type { Connection } from '../src/gateway.js';

const cleanups: Array<() => unknown | Promise<unknown>> = [];
afterEach(async () => {
  for (const close of cleanups.splice(0).reverse()) await close();
});

async function createTestEnv() {
  const dir = mkdtempSync(join(tmpdir(), 'im-privacy-grp-'));
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

it('supports same-owner mixed-space internal groups and agent-agent 1:1, enforces group mutual exclusion, and handles team <-> owner_only transitions cleanly', async () => {
  const { app, db, alice, bob, request, attachOnlineNode } = await createTestEnv();
  db.prepare("UPDATE users SET personal_space_enabled=1 WHERE id=?").run(alice.user.id);
  const { connection: aliceNode, sentFrames } = attachOnlineNode('node-alice', alice.user.owner_id, 1);
  const now = new Date().toISOString();

  // Legacy company-space private Agent X + personal-space private Agent Y owned by Alice.
  db.prepare(
    `INSERT INTO agent_profiles(agent_id,owner_id,space_id,node_id,display_name,collaboration_scope,work_mode,tool_allowlist_json,features_json,is_stale,created_at,updated_at)
     VALUES('agent-x',?,'company:default','node-alice','Agent X','owner_only','global','["task_graph"]','{"intelligent_ui":false,"task_graph":false}',0,?,?)`,
  ).run(alice.user.owner_id, now, now);
  db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES('u-agent-x','agent:agent-x','Agent X',?,?)").run(alice.user.owner_id, now);

  db.prepare(
    `INSERT INTO agent_profiles(agent_id,owner_id,space_id,node_id,display_name,collaboration_scope,work_mode,tool_allowlist_json,features_json,is_stale,created_at,updated_at)
     VALUES('agent-y',?,?,'node-alice','Agent Y','team','global','["task_graph"]','{"intelligent_ui":false,"task_graph":false}',0,?,?)`,
  ).run(alice.user.owner_id, `personal:${alice.user.owner_id}`, now, now);
  db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES('u-agent-y','agent:agent-y','Agent Y',?,?)").run(alice.user.owner_id, now);

  // 1) Group mutual exclusion: cannot create a group mixing Alice's private agent-x and external colleague Bob, nor explicit public visibility.
  const mixedGroup = await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: 'Mixed Forbidden',
    type: 'group',
    participants: [{ type: 'agent', id: 'agent-x' }, { type: 'user', id: bob.user.id }],
  });
  expect(mixedGroup.statusCode).toBe(409);
  expect(mixedGroup.json()).toMatchObject({ detail: { code: 'private_agent_in_group' } });

  const explicitPubWithPriv = await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: 'Public Forbidden',
    type: 'group',
    visibility: 'public',
    participants: [{ type: 'agent', id: 'agent-x' }, { type: 'agent', id: 'agent-y' }],
  });
  expect(explicitPubWithPriv.statusCode).toBe(409);
  expect(explicitPubWithPriv.json()).toMatchObject({ detail: { code: 'private_agent_in_group' } });

  // 2) Same-owner mixed-space internal private group (Alice + company:default agent-x + personal:<alice> agent-y) succeeds and defaults to private!
  const internalGroupRes = await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: 'Alice War Room',
    type: 'group',
    participants: [{ type: 'agent', id: 'agent-x' }, { type: 'agent', id: 'agent-y' }],
  });
  expect(internalGroupRes.statusCode, internalGroupRes.body).toBe(201);
  const internalGroup = internalGroupRes.json();
  expect(internalGroup).toMatchObject({
    visibility: 'private',
    space_id: `personal:${alice.user.owner_id}`,
    can_change_visibility: false,
  });

  // Cannot switch internalGroup to public or add external Bob while agent-x is owner_only.
  expect((await request(alice.access_token, 'PATCH', `/im/v1/conversations/${internalGroup.id}`, { visibility: 'public' })).statusCode).toBe(409);
  const addBob = await request(alice.access_token, 'POST', `/im/v1/conversations/${internalGroup.id}/participants`, {
    participants: [{ type: 'user', id: bob.user.id }],
  });
  expect(addBob.statusCode).toBe(409);
  expect(addBob.json()).toMatchObject({ detail: { code: 'private_agent_in_group' } });

  // Mentioning agent-x in internalGroup creates relay with owner_internal=true, owner_direct=false, message_receipts & thread_follows!
  const mentionMsg = await request(alice.access_token, 'POST', `/im/v1/conversations/${internalGroup.id}/messages`, {
    sender_user_id: alice.user.id,
    content: '<mention type="user" target_id="u-agent-x"/> Coordinate with Y',
  });
  expect(mentionMsg.statusCode, mentionMsg.body).toBe(201);
  const relayRow = db.prepare("SELECT payload_json FROM relay_tasks WHERE message_id=?")
    .all(mentionMsg.json().id)
    .find((r: any) => JSON.parse(r.payload_json).agent_id === 'agent-x') as any;
  expect(relayRow).toBeTruthy();
  const relayPayload = JSON.parse(relayRow.payload_json);
  expect(relayPayload.metadata).toMatchObject({ owner_internal: true, owner_direct: false, addressed_to_agent: true });
  expect(db.prepare("SELECT 1 FROM message_receipts WHERE message_id=? AND recipient_id='u-agent-x'").get(mentionMsg.json().id)).toBeTruthy();

  // Same-owner mixed-space agent-agent 1:1 reuses the exact same direct conversation in both directions (X->Y and Y->X).
  const xyChat = app.im.messaging.resolveTarget('agent-x', 'agent:agent-y');
  const yxChat = app.im.messaging.resolveTarget('agent-y', 'agent:agent-x');
  expect(xyChat).toBe(yxChat);
  // Private agent-x cannot resolveTarget to external Bob or join a public company group!
  expect(() => app.im.messaging.resolveTarget('agent-x', `user:${bob.user.id}`)).toThrow();
  const pubGroup = (await request(bob.access_token, 'POST', '/im/v1/conversations', {
    title: 'Company Townhall',
    type: 'group',
    visibility: 'public',
    participants: [],
  })).json();
  expect(() => app.im.messaging.joinConversation('u-agent-x', pubGroup.id)).toThrow();
  expect((await request(bob.access_token, 'POST', `/im/v1/conversations/${pubGroup.id}/participants`, {
    participants: [{ type: 'agent', id: 'agent-x' }],
  })).statusCode).toBe(404);
  await request(alice.access_token, 'POST', `/im/v1/conversations/${pubGroup.id}/join`);
  const aliceAddPrivToPub = await request(alice.access_token, 'POST', `/im/v1/conversations/${pubGroup.id}/participants`, {
    participants: [{ type: 'agent', id: 'agent-x' }],
  });
  expect(aliceAddPrivToPub.statusCode).toBe(409);
  expect(aliceAddPrivToPub.json()).toMatchObject({ detail: { code: 'private_agent_group_external_members' } });

  // 3) Put team agent-y into an external group with Bob AND a 1:1 chat with Bob, with a task graph and provisional running bubble, then tighten agent-y -> owner_only!
  const extGroup = (await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: 'Project Sync',
    type: 'group',
    participants: [{ type: 'user', id: bob.user.id }, { type: 'agent', id: 'agent-y' }],
  })).json();
  const bobDm = (await request(bob.access_token, 'POST', '/im/v1/conversations', {
    title: 'Bob & Agent Y',
    type: 'direct',
    participants: [{ type: 'agent', id: 'agent-y' }],
  })).json();
  const preMsg = (await request(bob.access_token, 'POST', `/im/v1/conversations/${bobDm.id}/messages`, {
    sender_user_id: bob.user.id,
    content: 'Hi Agent Y!',
  })).json();
  const preRelay = db.prepare("SELECT relay_task_id, payload_json FROM relay_tasks WHERE message_id=?")
    .all(preMsg.id)
    .find((r: any) => JSON.parse(r.payload_json).agent_id === 'agent-y') as any;

  // Create a task graph assigned to agent-y in extGroup + an empty provisional running bubble in extGroup.
  const tasks = new TaskGraphService(db, app.im.messaging);
  tasks.execute({ kind: 'agent', id: 'agent-y', node_id: 'node-alice' }, 'create', {
    title: 'External Sprint Plan',
    mode: 'dag',
    request_key: 'plan-y',
    conversation_id: extGroup.id,
  });
  const runningBubble = app.im.messaging.insertMessage(extGroup.id, 'u-agent-y', 'agent', '', [], 'prov-1', 'running');

  vi.spyOn(app.im.gateway, 'request').mockImplementation(async (_node, _cmd, payload: any) => ({
    status: 'applied',
    operation_id: payload.operation_id,
    candidate_fingerprint: payload.candidate_fingerprint,
    agent: payload.agent,
  }));
  sentFrames.length = 0;
  const tightenY = await request(alice.access_token, 'PATCH', '/im/v1/agents/agent-y/config', {
    profile_version: 1,
    display_name: 'Agent Y',
    collaboration_scope: 'owner_only',
  });
  expect(tightenY.statusCode, tightenY.body).toBe(200);

  // agent-y exited extGroup, provisional empty bubble was discarded, internalGroup kept agent-y, and node received agent.scope.revoked!
  expect(db.prepare("SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id='u-agent-y'").get(extGroup.id)).toBeUndefined();
  expect(db.prepare("SELECT 1 FROM messages WHERE id=?").get(runningBubble.id)).toBeUndefined();
  expect(db.prepare("SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id='u-agent-y'").get(internalGroup.id)).toBeTruthy();
  const revokedFrame = sentFrames.find(f => f.type === 'agent.scope.revoked');
  expect(revokedFrame?.payload.conversation_ids).toEqual(expect.arrayContaining([extGroup.id, bobDm.id]));

  // Bob's 1:1 with agent-y is retained with history, can_write=false, write_blocked_reason='agent_private', blocks messages/forks (403 agent_private), yet allows pin/mute!
  const bobDmView = (await request(bob.access_token, 'GET', `/im/v1/conversations/${bobDm.id}`)).json();
  expect(bobDmView).toMatchObject({ can_write: false, write_blocked_reason: 'agent_private' });
  const bobSendBlocked = await request(bob.access_token, 'POST', `/im/v1/conversations/${bobDm.id}/messages`, {
    sender_user_id: bob.user.id,
    content: 'Still there?',
  });
  expect(bobSendBlocked.statusCode).toBe(403);
  expect(bobSendBlocked.json()).toMatchObject({ detail: { code: 'agent_private' } });
  const bobPinOk = await request(bob.access_token, 'PATCH', `/im/v1/conversations/${bobDm.id}`, { is_pinned: true, is_muted: true });
  expect(bobPinOk.statusCode, bobPinOk.body).toBe(200);
  expect(bobPinOk.json()).toMatchObject({ is_pinned: true, is_muted: true });

  // Late node.delivery_receipt and agent.message.status for pre-transition tasks settle cleanly without 404!
  await expect(app.im.gateway.handle(aliceNode, 'node.delivery_receipt', {
    node_id: 'node-alice',
    relay_task_id: preRelay.relay_task_id,
    delivery_status: 'skipped',
  })).resolves.toMatchObject({ type: 'ack' });
  await expect(app.im.gateway.handle(aliceNode, 'agent.message.status', {
    node_id: 'node-alice',
    agent_id: 'agent-y',
    operation_id: 'missing-op',
    request_id: 'req-status-1',
  })).resolves.toBeDefined();

  // Reopening agent-y -> 'team' requires explicit confirm_scope_widen, then automatically restores Bob's 1:1 write access!
  const unconfirmedReopenY = await request(alice.access_token, 'PATCH', '/im/v1/agents/agent-y/config', {
    profile_version: 2,
    display_name: 'Agent Y',
    collaboration_scope: 'team',
  });
  expect(unconfirmedReopenY.statusCode).toBe(409);
  expect(unconfirmedReopenY.json()).toMatchObject({ detail: { code: 'scope_widen_confirmation_required' } });

  const reopenY = await request(alice.access_token, 'PATCH', '/im/v1/agents/agent-y/config', {
    profile_version: 2,
    display_name: 'Agent Y',
    collaboration_scope: 'team',
    confirm_scope_widen: true,
  });
  expect(reopenY.statusCode).toBe(200);
  expect((await request(bob.access_token, 'GET', `/im/v1/conversations/${bobDm.id}`)).json()).toMatchObject({
    can_write: true,
  });
  expect((await request(bob.access_token, 'POST', `/im/v1/conversations/${bobDm.id}/messages`, {
    sender_user_id: bob.user.id,
    content: 'Welcome back!',
  })).statusCode).toBe(201);
});

it('keeps private PA silent observer events while blocking PA send_message and send_user_message to external chats with structured code', async () => {
  const { app, db, alice, bob, request, attachOnlineNode } = await createTestEnv();
  const { connection: aliceNode } = attachOnlineNode('node-alice', alice.user.owner_id, 1);

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

  const paRes = await request(alice.access_token, 'POST', '/im/v1/personal-agent', {
    request_key: 'pa-stealth',
    node_id: 'node-alice',
    display_name: 'Stealth PA',
    collaboration_scope: 'owner_only',
  });
  expect(paRes.statusCode).toBe(201);
  const binding = paRes.json().binding;

  // Alice and Bob talk in a human 1:1 chat; Alice's private PA silently observes it via personal_observation_event trigger!
  const humanChat = (await request(alice.access_token, 'POST', '/im/v1/conversations', {
    title: 'Alice & Bob',
    type: 'direct',
    participants: [{ type: 'user', id: bob.user.id }],
  })).json();
  const bobMsgRes = await request(bob.access_token, 'POST', `/im/v1/conversations/${humanChat.id}/messages`, {
    sender_user_id: bob.user.id,
    content: 'Can Alice review the Q4 contract tomorrow?',
  });
  expect(bobMsgRes.statusCode, bobMsgRes.body).toBe(201);
  const bobMsg = bobMsgRes.json();

  const principal = { node_id: 'node-alice', owner_id: alice.user.owner_id, node_epoch: 1 };
  const paArgs = { agent_id: binding.agent_id, binding_id: binding.binding_id, epoch: binding.node_epoch };
  const obs = app.im.personal.observations(principal, paArgs);
  expect(obs.items.some((item: any) => item.message_id === bobMsg.id && item.delivery === 'observer')).toBe(true);

  // Private PA attempting pa.action.prepare (self or owner representation) on external humanChat fails with 403 collaboration_scope_restricted,
  // and Gateway unwraps error.code cleanly as 'collaboration_scope_restricted'!
  for (const representation of ['self', 'owner'] as const) {
    const resp = await app.im.gateway.handle(aliceNode, 'pa.action.prepare', {
      node_id: 'node-alice',
      request_id: `req-${representation}`,
      ...paArgs,
      request_key: `op-${representation}`,
      representation,
      conversation_id: humanChat.id,
      content: 'External reply attempt',
    });
    expect(resp).toMatchObject({
      type: 'pa.action.prepare.result',
      payload: {
        ok: false,
        error: { code: 'collaboration_scope_restricted' },
      },
    });
  }

  // Meanwhile, PA can resolve_target to Alice's own Agent in company:default, and fails with collaboration_scope_restricted for Bob!
  const now = new Date().toISOString();
  db.prepare(
    `INSERT INTO agent_profiles(agent_id,owner_id,space_id,node_id,display_name,collaboration_scope,work_mode,is_stale,created_at,updated_at)
     VALUES('alice-helper',?,'company:default','node-alice','Helper','owner_only','single_thread',0,?,?)`,
  ).run(alice.user.owner_id, now, now);
  db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES('u-alice-helper','agent:alice-helper','Helper',?,?)").run(alice.user.owner_id, now);

  const okTarget = app.im.messaging.resolveTarget(binding.agent_id, 'agent:alice-helper');
  expect(okTarget).toBeTruthy();
  expect(() => app.im.messaging.resolveTarget(binding.agent_id, `user:${bob.user.id}`)).toThrow();
});
