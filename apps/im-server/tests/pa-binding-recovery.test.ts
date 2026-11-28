import Fastify from 'fastify';
import { expect, it, vi } from 'vitest';
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
