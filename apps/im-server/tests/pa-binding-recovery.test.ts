import Fastify from 'fastify';
import { expect, it, vi } from 'vitest';
import { configurationOperations } from '../src/configuration-assembly.js';
import { Messaging } from '../src/messaging.js';
import { PersonalAgents, registerPersonalAgentRoutes } from '../src/personal-agent.js';
import { connectFixtureGateway, fixture } from './control-fixture.js';

function createPaHarness() {
  const f = fixture();
  f.ctx.gateway.broadcast = vi.fn();
  f.ctx.messaging = new Messaging(f.ctx);
  f.ctx.personal = new PersonalAgents(f.ctx);
  f.db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch) VALUES('n','o1',1)").run();
  connectFixtureGateway(f);
  const app = Fastify();
  app.setErrorHandler((error: any, _req, reply) => {
    reply.code(error.statusCode ?? 500).send({ detail: error.detail ?? error.message });
  });
  registerPersonalAgentRoutes(app, f.ctx);
  return { ...f, app };
}

it('rolls back pending PA binding and node residency on deterministic agent.create rejection, allowing clean retry', async () => {
  const { app, ctx, db } = createPaHarness();
  await app.ready();
  try {
    let rejectCreate = true;
    ctx.gateway.request = async (_node, method, payload: any) => {
      if (method === 'node.capabilities.resolve') {
        return { capabilities: { tools: [{ name: 'read', default_on: true }] } };
      }
      if (method === 'agent.create') {
        if (rejectCreate) {
          return {
            status: 'rejected',
            operation_id: payload.operation_id,
            candidate_fingerprint: payload.candidate_fingerprint,
            error_code: 'workspace_initialization_failed',
            message: 'Disk full while initializing workspace',
          };
        }
        return {
          status: 'applied',
          operation_id: payload.operation_id,
          candidate_fingerprint: payload.candidate_fingerprint,
          agent: { ...payload.agent, workspace_root: '/private/pa', workspace_is_default: true },
        };
      }
      return { status: 'pending' };
    };

    const failed = await app.inject({
      method: 'POST',
      url: '/im/v1/personal-agent',
      payload: { request_key: 'rk-rejected', node_id: 'n', display_name: '酷狗' },
    });
    expect(failed.statusCode).toBe(422);
    expect(failed.json().detail).toMatchObject({ code: 'workspace_initialization_failed' });

    const stateAfterReject = (await app.inject({ method: 'GET', url: '/im/v1/personal-agent' })).json();
    expect(stateAfterReject).toEqual({ binding: null, policy: null, creation: null });
    expect(db.prepare('SELECT COUNT(*) AS n FROM personal_agent_bindings').get()).toEqual({ n: 0 });
    expect(db.prepare('SELECT COUNT(*) AS n FROM pa_policies').get()).toEqual({ n: 0 });
    expect(db.prepare('SELECT COUNT(*) AS n FROM pa_binding_scopes').get()).toEqual({ n: 0 });
    expect(db.prepare('SELECT COUNT(*) AS n FROM pa_node_residencies').get()).toEqual({ n: 0 });

    rejectCreate = false;
    const retried = await app.inject({
      method: 'POST',
      url: '/im/v1/personal-agent',
      payload: { request_key: 'rk-fresh-after-fix', node_id: 'n', display_name: '新助手', collaboration_scope: 'owner_only' },
    });
    expect(retried.statusCode, retried.body).toBe(201);
    expect(retried.json()).toMatchObject({
      binding: { display_name: '新助手', status: 'active', collaboration_scope: 'owner_only' },
      creation: null,
    });
  } finally {
    await app.close();
  }
});

it('retains pending PA binding on unconfirmed in-flight create, blocks false-200 on a new request_key, and recovers cleanly', async () => {
  const { app, ctx, db } = createPaHarness();
  await app.ready();
  try {
    let appliedReceipt: any = null;
    let ackLost = true;
    ctx.gateway.request = async (_node, method, payload: any) => {
      if (method === 'node.capabilities.resolve') {
        return { capabilities: { tools: [{ name: 'read', default_on: true }] } };
      }
      if (method === 'agent.create') {
        appliedReceipt = {
          status: 'applied',
          operation_id: payload.operation_id,
          candidate_fingerprint: payload.candidate_fingerprint,
          agent: { ...payload.agent, workspace_root: '/private/pa', workspace_is_default: true },
        };
        if (ackLost) throw Object.assign(new Error('Gateway ACK timeout'), { statusCode: 504 });
        return appliedReceipt;
      }
      if (method === 'agent.config.operation.status') {
        if (ackLost) throw Object.assign(new Error('Gateway offline'), { statusCode: 503 });
        return appliedReceipt;
      }
      return null;
    };

    const unconfirmed = await app.inject({
      method: 'POST',
      url: '/im/v1/personal-agent',
      payload: { request_key: 'rk-inflight', node_id: 'n', display_name: '酷狗' },
    });
    expect(unconfirmed.statusCode).toBe(503);
    expect(unconfirmed.json().detail).toMatchObject({ code: 'config_apply_pending' });

    const pendingState = (await app.inject({ method: 'GET', url: '/im/v1/personal-agent' })).json();
    expect(pendingState).toMatchObject({
      binding: { display_name: '酷狗', status: 'pending' },
      creation: { request_key: 'rk-inflight' },
    });
    const originalBindingId = pendingState.binding.binding_id;
    const originalConversationId = pendingState.binding.conversation_id;

    // A second browser/dialog submitting a different request_key while still unconfirmed must NOT get a fake 200 OK.
    const competingWhilePending = await app.inject({
      method: 'POST',
      url: '/im/v1/personal-agent',
      payload: { request_key: 'rk-second-tab', node_id: 'n', display_name: '另一个名字' },
    });
    expect(competingWhilePending.statusCode).toBe(503);

    // Once the node responds with the applied receipt, even a competing or original retry reconciles the original PA identity.
    ackLost = false;
    const recovered = await app.inject({
      method: 'POST',
      url: '/im/v1/personal-agent',
      payload: { request_key: 'rk-second-tab', node_id: 'n', display_name: '另一个名字' },
    });
    expect(recovered.statusCode, recovered.body).toBe(201);
    expect(recovered.json()).toMatchObject({
      binding: {
        binding_id: originalBindingId,
        conversation_id: originalConversationId,
        display_name: '酷狗',
        status: 'active',
      },
      creation: null,
    });
    expect(db.prepare('SELECT id FROM conversations WHERE id=?').get(originalConversationId)).toEqual({ id: originalConversationId });
  } finally {
    await app.close();
  }
});

it('self-heals legacy orphan pending bindings across node epoch bumps and new request keys', async () => {
  const { app, ctx, db } = createPaHarness();
  await app.ready();
  try {
    // Simulate a legacy database with a stranded pending binding and a re-bound node epoch (1 -> 2), with no active config op.
    db.prepare("UPDATE node_binding_state SET node_epoch=2 WHERE node_id='n'").run();
    db.prepare(
      "INSERT INTO personal_agent_bindings VALUES('legacy-b','o1','u1','pa_legacy000001','n',1,'c_legacy','酷狗','legacy-rk','pending',NULL,?)",
    ).run(new Date().toISOString());
    db.prepare("INSERT INTO pa_policies(binding_id) VALUES('legacy-b')").run();
    db.prepare("INSERT INTO pa_binding_scopes(binding_id,collaboration_scope) VALUES('legacy-b','team')").run();

    ctx.gateway.request = async (_node, method, payload: any) => {
      if (method === 'node.capabilities.resolve') {
        return { capabilities: { tools: [{ name: 'read', default_on: true }] } };
      }
      if (method === 'agent.create') {
        return {
          status: 'applied',
          operation_id: payload.operation_id,
          candidate_fingerprint: payload.candidate_fingerprint,
          agent: { ...payload.agent, workspace_root: '/private/pa', workspace_is_default: true },
        };
      }
      return null;
    };

    // Pending auxiliary reads/mutations must not crash or materialize ghost agent users before activation.
    expect((await app.inject({ method: 'GET', url: '/im/v1/personal-agent/sources' })).json()).toMatchObject({ items: [] });
    expect((await app.inject({ method: 'PATCH', url: '/im/v1/personal-agent', payload: { display_name: '改名' } })).statusCode).toBe(404);

    // Retrying with the saved request_key refreshes node_epoch to 2 and completes creation cleanly.
    const sameKeyRecovered = await app.inject({
      method: 'POST',
      url: '/im/v1/personal-agent',
      payload: { request_key: 'legacy-rk', node_id: 'n', display_name: '酷狗' },
    });
    expect(sameKeyRecovered.statusCode, sameKeyRecovered.body).toBe(201);
    const activeBinding = sameKeyRecovered.json().binding;
    expect(activeBinding).toMatchObject({ binding_id: 'legacy-b', node_epoch: 2, status: 'active' });
    expect(ctx.personal!.authority({ node_id: 'n', owner_id: 'o1', node_epoch: 2 }, { agent_id: 'pa_legacy000001' }).binding_id).toBe('legacy-b');

    // Also verify a fresh request_key replaces an unbacked orphan pending binding when the user restarts setup.
    db.prepare('DELETE FROM conversation_participants WHERE conversation_id=?').run('c_legacy');
    db.prepare('DELETE FROM conversations WHERE id=?').run('c_legacy');
    db.prepare('DELETE FROM agent_profiles WHERE agent_id=?').run('pa_legacy000001');
    db.prepare('DELETE FROM agent_config_operations WHERE agent_id=?').run('pa_legacy000001');
    db.prepare("UPDATE personal_agent_bindings SET status='pending' WHERE binding_id='legacy-b'").run();

    const freshKeyCreated = await app.inject({
      method: 'POST',
      url: '/im/v1/personal-agent',
      payload: { request_key: 'brand-new-rk', node_id: 'n', display_name: '全新助手' },
    });
    expect(freshKeyCreated.statusCode, freshKeyCreated.body).toBe(201);
    expect(freshKeyCreated.json()).toMatchObject({
      binding: { display_name: '全新助手', status: 'active', node_epoch: 2 },
      creation: null,
    });
    expect(freshKeyCreated.json().binding.binding_id).not.toBe('legacy-b');
  } finally {
    await app.close();
  }
});

it.each([true, false])('keeps only a registered identity on failed legacy recovery (stale profile: %s)', async stale => {
  const { app, db, ctx } = createPaHarness();
  try {
    db.prepare("INSERT INTO personal_agent_bindings VALUES('b','o1','u1','pa_legacy','n',1,'c_pa','Assistant','old','pending',NULL,datetime('now'))").run();
    db.prepare("INSERT INTO pa_policies(binding_id) VALUES('b')").run();
    db.prepare("INSERT INTO pa_node_residencies VALUES('n','o1')").run();
    if (stale) db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,is_stale,created_at,updated_at) VALUES('pa_legacy','o1','n','Assistant',1,datetime('now'),datetime('now'))").run();
    ctx.gateway.request = async () => { throw Object.assign(new Error('Computer offline'), {statusCode:503}); };
    const result = await app.inject({method:'POST',url:'/im/v1/personal-agent',payload:{request_key:'old',node_id:'n',display_name:'Assistant'}});
    expect(result.statusCode).toBe(stale ? 409 : 503);
    const state = (await app.inject({method:'GET',url:'/im/v1/personal-agent'})).json();
    if (stale) expect(state.binding).toMatchObject({binding_id:'b',conversation_id:'c_pa',status:'pending'});
    else expect(state.binding).toBeNull();
    expect(db.prepare('SELECT count(*) n FROM pa_node_residencies').get()).toEqual({n: Number(stale)});
  } finally {
    await app.close();
  }
});

it('creates a queued PA using the current node epoch after rebind', async () => {
  const {app, ctx, db} = createPaHarness();
  await app.ready();
  const ops = configurationOperations(ctx);
  const lock = Promise.withResolvers<void>();
  const holder = ops.serialized('personal:o1', () => lock.promise);
  const queue = vi.spyOn(ops, 'serialized');
  try {
    ctx.gateway.request = async (_node, method, payload: any) => {
      if (method === 'node.capabilities.resolve') return {capabilities:{tools:[]}};
      return {status:'applied',operation_id:payload.operation_id,candidate_fingerprint:payload.candidate_fingerprint,
        agent:{...payload.agent,workspace_root:'/private/pa',workspace_is_default:true}};
    };
    const response = app.inject({method:'POST',url:'/im/v1/personal-agent',payload:{request_key:'queued',node_id:'n',display_name:'Assistant'}}).then(r=>r);
    await vi.waitFor(()=>expect(queue).toHaveBeenCalled());
    db.prepare("UPDATE node_binding_state SET node_epoch=2 WHERE node_id='n'").run();
    ctx.gateway.nodes.get('n')!.node_epoch=2;
    lock.resolve();
    const created = await response;
    expect(created.statusCode,created.body).toBe(201);
    const {binding} = created.json();
    expect(binding.node_epoch).toBe(2);
    expect(ctx.personal!.authority({node_id:'n',owner_id:'o1',node_epoch:2},{agent_id:binding.agent_id}).binding_id).toBe(binding.binding_id);
  } finally {
    lock.resolve();
    await holder;
    await app.close();
  }
});
