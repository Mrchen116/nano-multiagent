import Fastify from 'fastify';
import { expect, it } from 'vitest';
import { fixture, connectFixtureGateway } from './control-fixture.js';
import { registerControlRoutes } from '../src/control-routes.js';
import { PersonalAgents, registerPersonalAgentRoutes } from '../src/personal-agent.js';
import { Messaging } from '../src/messaging.js';
import { contactDetail } from '../src/contacts.js';

function setup() {
  const {ctx,db} = fixture();
  connectFixtureGateway({ctx,db});
  ctx.messaging = new Messaging(ctx);
  ctx.personal = new PersonalAgents(ctx);
  const applied: Record<string, unknown>[] = [];
  ctx.gateway.request = async (_node, action, p) => {
    if (action === 'node.capabilities.resolve') return {capabilities:{tools:[],skills:[]}};
    applied.push(p.agent);
    return {status:'applied',operation_id:p.operation_id,candidate_fingerprint:p.candidate_fingerprint,
      agent:{...p.agent,workspace_root:`/agents/${p.agent.agent_id}`,workspace_is_default:true}};
  };
  const app=Fastify();
  app.setErrorHandler((error:any,_req,reply)=>reply.code(error.statusCode ?? 500).send({detail:error.detail ?? error.message}));
  registerControlRoutes(app,ctx); registerPersonalAgentRoutes(app,ctx);
  return {app,ctx,db,applied};
}

it.each([false,true])('persists the selected avatar and projects it to chat and contacts (personal=%s)',async personal=>{
  const {app,ctx,db,applied}=setup();
  try {
    const url=personal ? '/im/v1/personal-agent' : '/im/v1/nodes/n/agents';
    const payload=personal ? {node_id:'n',request_key:'appearance',display_name:'Same name',avatar_variant:17}
      : {agent_id:'new-agent',display_name:'Same name',avatar_variant:17,group_reply_policy:'manual',skills:[]};
    const response=await app.inject({method:'POST',url,payload});
    expect(response.statusCode,response.body).toBe(201);
    const result=personal ? response.json().binding : response.json();
    expect(result.avatar_variant).toBe(17);
    expect(db.prepare('SELECT avatar_variant FROM agent_profiles WHERE agent_id=?').get(result.agent_id)).toEqual({avatar_variant:17});
    const actor=ctx.messaging.actor(ctx.messaging.agentUser(result.agent_id));
    expect(actor).toMatchObject({id:result.agent_id,avatar_variant:17,...(personal ? {role:'personal'} : {})});
    expect(contactDetail(db,ctx.identity.user('u1')!,actor.user_id)).toMatchObject({avatar_variant:17});
    expect(applied).toHaveLength(1);
    expect(applied[0]).not.toHaveProperty('avatar_variant');
    if(personal) {
      expect((await app.inject({method:'GET',url})).json().binding.avatar_variant).toBe(17);
      expect((await app.inject({method:'POST',url,payload})).json().binding.avatar_variant).toBe(17);
      expect(applied).toHaveLength(1);
    }
  } finally {await app.close();}
});

it.each([-1,24,1.5,'7'])('rejects an invalid avatar before creating anything: %s',async avatar_variant=>{
  const {app,db,applied}=setup();
  try {
    for (const [url,payload] of [
      ['/im/v1/personal-agent',{node_id:'n',request_key:'invalid',display_name:'Name',avatar_variant}],
      ['/im/v1/nodes/n/agents',{agent_id:'invalid',display_name:'Name',group_reply_policy:'manual',avatar_variant}],
    ] as const) expect((await app.inject({method:'POST',url,payload})).statusCode).toBe(422);
    expect(applied).toHaveLength(0);
    expect(db.prepare('SELECT 1 FROM personal_agent_bindings').get()).toBeUndefined();
    expect(db.prepare("SELECT 1 FROM agent_profiles WHERE agent_id='invalid'").get()).toBeUndefined();
  } finally {await app.close();}
});
