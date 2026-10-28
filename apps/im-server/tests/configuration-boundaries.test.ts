import Fastify from 'fastify';
import {expect, it} from 'vitest';
import {registerControlRoutes} from '../src/control-routes.js';
import {fixture, connectFixtureGateway} from './control-fixture.js';

it('preserves omitted and nullable configuration fields through the HTTP boundary', async () => {
  const f = fixture(); connectFixtureGateway(f);
  const app = Fastify();
  registerControlRoutes(app,f.ctx);
  f.db.prepare("UPDATE agent_profiles SET custom_prompt='keep prompt',heartbeat_json=?,reasoning_effort='high',approval_mode='cc' WHERE agent_id='a'").run('{"every":"30m"}');
  f.ctx.gateway.request = async (_node, _command, payload) => ({status:'applied',operation_id:payload.operation_id,candidate_fingerprint:payload.candidate_fingerprint,agent:payload.agent});
  try {
    const response = await app.inject({method:'PATCH',url:'/im/v1/agents/a/config',payload:{profile_version:1,display_name:'  Name  ',group_reply_policy:'manual',work_mode:null,features:null,custom_prompt:null,heartbeat_json:null,reasoning_effort:null,ignored_future_option:{anything:true}}});
    expect(response.statusCode,response.body).toBe(200);
    expect(response.json()).toMatchObject({display_name:'Name',custom_prompt:'keep prompt',heartbeat_json:'{"every":"30m"}',reasoning_effort:null,approval_mode:'cc',work_mode:'single_thread',features:{task_graph:true}});
    expect(response.json()).not.toHaveProperty('ignored_future_option');
    expect(response.json()).not.toHaveProperty('skills_json');
    const operation = f.db.prepare('SELECT candidate_json FROM agent_config_operations').get()!;
    expect(JSON.parse(String(operation.candidate_json))).toMatchObject({custom_prompt:'keep prompt',approval_mode:'cc'});
  } finally { await app.close(); }
});

it('rejects malformed known HTTP fields before any durable operation or node request', async () => {
  const f = fixture(); connectFixtureGateway(f);
  const app = Fastify();
  registerControlRoutes(app,f.ctx);
  let requested = false;
  f.ctx.gateway.request = async () => {requested=true; throw new Error('must not reach node');};
  try {
    for (const malformed of [{skills:42},{tool_allowlist:[false]},{profile_version:'1'},{custom_prompt:{text:'bad'}}]) {
      const response = await app.inject({method:'PATCH',url:'/im/v1/agents/a/config',payload:{profile_version:1,display_name:'Name',group_reply_policy:'manual',...malformed}});
      expect(response.statusCode,response.body).toBe(422);
    }
    expect(requested).toBe(false);
    expect(f.db.prepare('SELECT count(*) n FROM agent_config_operations').get()?.n).toBe(0);
    expect(f.db.prepare("SELECT profile_version FROM agent_profiles WHERE agent_id='a'").get()?.profile_version).toBe(1);
  } finally { await app.close(); }
});


it('retains a legacy null skill selection in the stored mirror projection', async () => {
  const f = fixture(), app = Fastify();
  f.db.prepare("UPDATE agent_profiles SET skills_json='null',skills_selection_mode=NULL WHERE agent_id='a'").run();
  registerControlRoutes(app,f.ctx);
  try {
    const response = await app.inject({url:'/im/v1/agents/a/config?source=mirror',headers:{authorization:'Bearer token'}});
    expect(response.statusCode,response.body).toBe(200);
    expect(response.json()).toMatchObject({skills:null,skills_selection_mode:null});
  } finally { await app.close(); }
});
