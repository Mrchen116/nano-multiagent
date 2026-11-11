import Fastify from 'fastify';
import {expect, it} from 'vitest';
import type {ConfigurationResult} from '@nano/product-contracts';
import {registerControlRoutes} from '../src/control-routes.js';
import {registerPersonalAgentRoutes} from '../src/personal-agent.js';
import {connectFixtureGateway} from './control-fixture.js';
import {personalFixture} from './personal-fixture.js';

function settings() {
  const f = personalFixture();
  connectFixtureGateway(f);
  const app = Fastify();
  registerControlRoutes(app, f.ctx);
  registerPersonalAgentRoutes(app, f.ctx);
  const save = (name: string, version: number, description = '') => app.inject({
    method: 'PATCH', url: '/im/v1/agents/a/config',
    payload: {display_name: name, profile_version: version, group_reply_policy: 'manual', description},
  });
  const profile = () => f.db.prepare("SELECT display_name,description,profile_version FROM agent_profiles WHERE agent_id='a'").get();
  return {...f, app, save, profile};
}

it('returns the result of each settings edit when a PA rename ACK is delayed', async () => {
  const {app, ctx, save, profile} = settings();
  const applied = Promise.withResolvers<void>(), ack = Promise.withResolvers<void>();
  let receipt: ConfigurationResult;
  const commands: string[] = [];
  ctx.gateway.request = async (_node, command, payload) => {
    commands.push(command);
    if (command === 'agent.config.apply') {
      receipt = {status:'applied', operation_id:payload.operation_id, candidate_fingerprint:payload.candidate_fingerprint, agent:payload.agent};
      if (payload.agent.display_name === 'A') {
        applied.resolve();
        await ack.promise;
      }
    }
    return receipt;
  };
  // Release A only after B has entered Fastify and had a turn to run its handler.
  app.addHook('preHandler', async req => {
    if (req.url.endsWith('/config')) setImmediate(ack.resolve);
  });
  try {
    const rename = app.inject({method:'PATCH',url:'/im/v1/personal-agent',payload:{display_name:'A'}}).then(r => r);
    await applied.promise;
    const [a,b] = await Promise.all([rename, save('B', 1)]);
    expect({status:b.statusCode, name:b.json().display_name, stored:profile()?.display_name}).toEqual({status:409, name:undefined, stored:'A'});
    expect(a.statusCode, a.body).toBe(200);
    expect(a.json().binding.display_name).toBe('A');
    expect(profile()).toMatchObject({display_name:'A',profile_version:2});
    expect(b.body).toContain('profile_version conflict');
    expect(commands).toEqual(['agent.config.apply']);
    const fresh = await save('B', 2);
    expect(fresh.statusCode, fresh.body).toBe(200);
    expect(fresh.json()).toMatchObject({display_name:'B',profile_version:3});
    expect(profile()).toMatchObject({display_name:'B',profile_version:3});
  } finally { ack.resolve(); await app.close(); }
});

it.each(['same', 'different description', 'older version'])('checks retry identity after a lost ACK (%s)', async kind => {
  const {app, ctx, db, save, profile} = settings();
  db.prepare("UPDATE agent_profiles SET profile_version=2").run();
  let receipt: ConfigurationResult | undefined;
  let confirmed = false;
  const operationIds = new Set<string>();
  ctx.gateway.request = async (_node, command, payload) => {
    operationIds.add(payload.operation_id);
    if (command === 'agent.config.apply') {
      receipt = {status:'applied', operation_id:payload.operation_id, candidate_fingerprint:payload.candidate_fingerprint, agent:payload.agent};
    }
    return confirmed ? receipt! : {status:'pending'};
  };
  try {
    const pending = await save('A', 2, 'first');
    expect(pending.statusCode, pending.body).toBe(503);
    expect((await save('B', 2)).statusCode).toBe(503);
    expect(profile()).toMatchObject({display_name:'Agent',profile_version:2});
    confirmed = true;
    const retry = await save('A', kind === 'older version' ? 1 : 2, kind === 'different description' ? 'second' : 'first');
    expect(retry.statusCode,retry.body).toBe(kind === 'same' ? 200 : 409);
    if (kind === 'same') expect(retry.json()).toMatchObject({display_name:'A',description:'first',profile_version:3});
    expect(profile()).toEqual({display_name:'A',description:'first',profile_version:3});
    expect(operationIds.size).toBe(1);
  } finally { await app.close(); }
});

it('admits the PA rename after a different pending edit is definitively rejected', async () => {
  const {app, ctx, save, profile} = settings();
  let rejected: ConfigurationResult;
  let confirmed = false;
  ctx.gateway.request = async (_node, command, payload) => {
    if (command === 'agent.config.apply') {
      const identity = {operation_id:payload.operation_id, candidate_fingerprint:payload.candidate_fingerprint};
      if (payload.agent.display_name === 'PA') return {...identity, status:'applied', agent:payload.agent};
      rejected = {...identity, status:'rejected', error_code:'invalid_agent_config'};
    }
    return confirmed ? rejected : {status:'pending'};
  };
  try {
    expect((await save('generic', 1)).statusCode).toBe(503);
    confirmed = true;
    const rename = await app.inject({method:'PATCH',url:'/im/v1/personal-agent',payload:{display_name:'PA'}});
    expect(rename.statusCode,rename.body).toBe(200);
    expect(rename.json().binding.display_name).toBe('PA');
    expect(profile()).toMatchObject({display_name:'PA',profile_version:2});
  } finally { await app.close(); }
});

it.each(['current', 'legacy'])('only lets the original creation request claim its %s receipt', async format => {
  const {app, ctx, db} = settings();
  db.exec("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('other','o1','Other','online'),('bob','o2','Bob','online')");
  const original = {agent_id:'b',display_name:'Alpha',workspace_root:'/alpha',group_reply_policy:'manual',description:'original',initial_role:'Help with design.'};
  const create = (fields = {}, node = 'n', user = 'u1') => app.inject({
    method:'POST',url:`/im/v1/nodes/${node}/agents`,headers:{'x-user':user},payload:{...original,...fields},
  });
  let receipt: ConfigurationResult | undefined, confirmed = false;
  const operations = new Set<string>();
  ctx.gateway.request = async (_node, command, payload) => {
    if (command === 'node.capabilities.resolve') {
      return {skills:[{name: confirmed && format === 'current' ? 'new-default' : 'original-default',default_on:true}]};
    }
    operations.add(payload.operation_id);
    if (command === 'agent.create') {
      receipt = {status:'applied',operation_id:payload.operation_id,candidate_fingerprint:payload.candidate_fingerprint,agent:payload.agent};
    }
    return confirmed ? receipt! : {status:'pending'};
  };
  try {
    expect((await create()).statusCode).toBe(503);
    if (format === 'legacy') db.exec("UPDATE agent_config_operations SET candidate_json=json_remove(candidate_json,'$.create_default_skills')");
    expect((await create()).statusCode).toBe(503);
    confirmed = true;
    expect((await create({display_name:'Bravo',workspace_root:'/bravo'})).statusCode).toBe(409);
    expect((await create({description:'different'})).statusCode).toBe(409);
    expect((await create({initial_role:'Another role'})).statusCode).toBe(409);
    expect((await create({confirm_existing_workspace:true})).statusCode).toBe(409);
    expect((await create({}, 'other')).statusCode).toBe(409);
    expect((await create({}, 'n', 'u2')).statusCode).toBe(404);
    expect((await create({}, 'bob', 'u2')).statusCode).toBe(409);
    const retry = await create();
    expect(retry.statusCode,retry.body).toBe(201);
    expect(retry.json()).toMatchObject({display_name:'Alpha',workspace_root:'/alpha',description:'original',node_id:'n'});
    expect(retry.json().skills).toContain('original-default');
    expect((await create()).statusCode).toBe(409);
    expect(operations.size).toBe(1);
  } finally { await app.close(); }
});

it('defaults a created Agent to global mode and keeps an explicit single_thread request', async () => {
  const {app, ctx} = settings();
  const original = {display_name:'Charlie',workspace_root:'/charlie',group_reply_policy:'manual'};
  ctx.gateway.request = async (_node, command, payload) => {
    if (command === 'node.capabilities.resolve') return {skills:[]};
    if (command === 'agent.create') return {status:'applied',operation_id:payload.operation_id,candidate_fingerprint:payload.candidate_fingerprint,agent:payload.agent};
    return {status:'pending'};
  };
  const create = (fields: Record<string, unknown>) => app.inject({
    method:'POST',url:'/im/v1/nodes/n/agents',headers:{'x-user':'u1'},payload:{...original,...fields},
  });
  try {
    const omitted = await create({agent_id:'default-mode'});
    expect(omitted.statusCode,omitted.body).toBe(201);
    expect(omitted.json().work_mode).toBe('global');
    const explicit = await create({agent_id:'single-mode',work_mode:'single_thread'});
    expect(explicit.statusCode,explicit.body).toBe(201);
    expect(explicit.json().work_mode).toBe('single_thread');
  } finally { await app.close(); }
});
