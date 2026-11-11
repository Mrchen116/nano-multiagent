import Fastify from 'fastify';
import {expect, it} from 'vitest';
import {registerControlRoutes} from '../src/control-routes.js';
import {fixture, connectFixtureGateway} from './control-fixture.js';

it('preserves omitted and nullable configuration fields through the HTTP boundary', async () => {
  const f = fixture(); connectFixtureGateway(f);
  const app = Fastify();
  registerControlRoutes(app,f.ctx);
  f.db.prepare("UPDATE agent_profiles SET heartbeat_json=?,reasoning_effort='high',approval_mode='cc' WHERE agent_id='a'").run('{"every":"30m"}');
  f.ctx.gateway.request = async (_node, _command, payload) => ({status:'applied',operation_id:payload.operation_id,candidate_fingerprint:payload.candidate_fingerprint,agent:payload.agent});
  try {
    const response = await app.inject({method:'PATCH',url:'/im/v1/agents/a/config',payload:{profile_version:1,display_name:'  Name  ',group_reply_policy:'manual',work_mode:null,features:null,heartbeat_json:null,reasoning_effort:null,ignored_future_option:{anything:true}}});
    expect(response.statusCode,response.body).toBe(200);
    expect(response.json()).toMatchObject({display_name:'Name',heartbeat_json:'{"every":"30m"}',reasoning_effort:null,approval_mode:'cc',work_mode:'single_thread',features:{task_graph:true}});
    expect(response.json()).not.toHaveProperty('ignored_future_option');
    expect(response.json()).not.toHaveProperty('skills_json');
    const operation = f.db.prepare('SELECT candidate_json FROM agent_config_operations').get()!;
    expect(JSON.parse(String(operation.candidate_json))).toMatchObject({approval_mode:'cc'});
  } finally { await app.close(); }
});

it('rejects malformed known HTTP fields before any durable operation or node request', async () => {
  const f = fixture(); connectFixtureGateway(f);
  const app = Fastify();
  registerControlRoutes(app,f.ctx);
  let requested = false;
  f.ctx.gateway.request = async () => {requested=true; throw new Error('must not reach node');};
  try {
    for (const malformed of [{skills:42},{tool_allowlist:[false]},{profile_version:'1'},{initial_role:'creation-only'},{knowledge:{memoryMode:'legacy'}},{memoryMode:'legacy'},{legacyMemory:{enabled:true}},{dreaming:{intervalMs:1}}]) {
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


it('keeps an inferred explicit Skill selection after retiring its only fixed member', async () => {
  const f=fixture(),app=Fastify();
  f.db.prepare("UPDATE agent_profiles SET skills_json='[\"skill-creator\"]',skills_selection_mode=NULL WHERE agent_id='a'").run();
  registerControlRoutes(app,f.ctx);
  try {
    const response=await app.inject({url:'/im/v1/agents/a/config?source=mirror',headers:{authorization:'Bearer token'}});
    expect(response.statusCode,response.body).toBe(200);
    expect(response.json()).toMatchObject({skills:[],skills_selection_mode:'explicit_allowlist'});
  } finally {await app.close();}
});


it('validates initial ROLE at creation and keeps retired instructions out of public profiles', async () => {
  const f=fixture(); connectFixtureGateway(f);
  const app=Fastify(); registerControlRoutes(app,f.ctx);
  const requests:Record<string,any>[]=[];
  f.ctx.gateway.request=async (_node,command,payload) => {
    if (command === 'node.capabilities.resolve') return {skills:[]};
    requests.push(payload);
    return {status:'applied',operation_id:payload.operation_id,candidate_fingerprint:payload.candidate_fingerprint,agent:{...payload.agent,workspace_root:'/new'}};
  };
  const create=(fields:Record<string,unknown>) => app.inject({method:'POST',url:'/im/v1/nodes/n/agents',payload:{agent_id:'new',display_name:'New',group_reply_policy:'manual',...fields}});
  try {
    for (const initial_role of [null,42,'😀'.repeat(1001)]) expect((await create({initial_role})).statusCode).toBe(422);
    expect(requests).toHaveLength(0);
    const content='😀'.repeat(1000);
    const response=await create({initial_role:content,custom_prompt:'retired'});
    expect(response.statusCode,response.body).toBe(201);
    expect(requests[0].initial_role).toBe(content);
    for (const value of [response.json(),requests[0].agent]) {
      expect(value).not.toHaveProperty('custom_prompt');
      expect(value).not.toHaveProperty('initial_role');
    }
  } finally {await app.close();}
});
