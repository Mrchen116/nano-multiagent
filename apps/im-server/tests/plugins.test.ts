import Fastify from 'fastify';
import { expect, it, vi } from 'vitest';
import { registerControlRoutes } from '../src/control.js';
import { fixture } from './control-fixture.js';

it('routes plugin management only for the owner and rejects client supplied scope', async () => {
  const {ctx}=fixture();
  const view={workspace:'/agent',entries:[{name:'report-style',enabled:true,rows:[]}]};
  const request=vi.fn(async()=>({plugins:view})); ctx.gateway.request=request;
  const app=Fastify(); registerControlRoutes(app,ctx);
  try {
    expect((await app.inject({method:'GET',url:'/im/v1/agents/a/plugins',headers:{'x-user':'u2'}})).statusCode).toBe(404);
    expect(request).not.toHaveBeenCalled();
    expect((await app.inject({method:'GET',url:'/im/v1/agents/a/plugins'})).json()).toEqual(view);
    expect(request).toHaveBeenLastCalledWith('n','node.plugins.request',{agent_id:'a',action:'list_bundles'});
    for(const payload of [
      {action:'install_bundle',target:'/tmp/package'},
      {action:'set_bundle',target:'report-style',enabled:'false'},
      {action:'set_bundle',target:'report-style',enabled:false,workspace:'/other'},
      {action:'remove_bundle'},
    ]) expect((await app.inject({method:'POST',url:'/im/v1/agents/a/plugins',payload})).statusCode).toBe(422);
    const payload={action:'set_bundle',target:'report-style',enabled:false};
    expect((await app.inject({method:'POST',url:'/im/v1/agents/a/plugins',payload})).json()).toEqual(view);
    expect(request).toHaveBeenLastCalledWith('n','node.plugins.request',{agent_id:'a',...payload});
    request.mockResolvedValueOnce(null as never);
    expect((await app.inject({method:'GET',url:'/im/v1/agents/a/plugins'})).statusCode).toBe(503);
  } finally {await app.close();}
});
