import Fastify from 'fastify';
import { afterEach, expect, it, vi } from 'vitest';
import { registerIntelligentUIResources } from '../src/intelligent-ui-resources.js';
import { fixture } from './control-fixture.js';
import { Messaging } from '../src/messaging.js';

afterEach(()=>vi.unstubAllGlobals());
it('authenticates resource lookups before contacting upstream', async()=>{
  const {ctx}=fixture(); ctx.messaging=new Messaging(ctx);
  ctx.identity.authenticateRequest=()=>{throw Object.assign(new Error('unauthorized'),{statusCode:401})};
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
  const app=Fastify();registerIntelligentUIResources(app,ctx);
  const response=await app.inject('/im/v1/intelligent-ui/api/wiki?title=Paris');
  expect(response.statusCode).toBe(401);expect(fetch).not.toHaveBeenCalled();await app.close();
});
it('retains upstream input errors and proxies only the fixed public service',async()=>{
  const {ctx}=fixture();ctx.messaging=new Messaging(ctx);
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({code:'Ok',routes:[{geometry:{coordinates:[[2,48],[3,49]]}}]})});
  vi.stubGlobal('fetch',fetch);
  const app=Fastify();registerIntelligentUIResources(app,ctx);
  expect((await app.inject('/im/v1/intelligent-ui/api/street-route?coords=bad')).statusCode).toBe(400);
  expect(fetch).not.toHaveBeenCalled();
  const response=await app.inject('/im/v1/intelligent-ui/api/street-route?coords=2,48;3,49');
  expect(response.json()).toEqual({points:[[48,2],[49,3]]});
  expect(fetch.mock.calls[0][0]).toBe('https://router.project-osrm.org/route/v1/driving/2,48;3,49?overview=full&geometries=geojson&steps=false');
  await app.close();
});
