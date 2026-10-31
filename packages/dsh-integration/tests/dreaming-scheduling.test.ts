import { afterEach, expect, it, vi } from 'vitest';
import { Dreaming } from '../src/knowledge/dreaming.js';
import type { AgentConfiguration } from '../src/index.js';

const disposals: Array<() => void> = [];
afterEach(() => { for (const dispose of disposals.splice(0)) dispose(); });
function scheduler() {
  const config: AgentConfiguration = { agentId: 'a', revision: '1', provider: 'fixture', model: 'test', features: { dreaming: true }, knowledge: { dreaming: { intervalMs: 100, quietMs: 10 } } };
  const owner = { protocol: 2, integrated: {}, activationAt: 1000, streams: {}, seen: [], rotation: 0, failures: 0 };
  const rows = new Map([[Buffer.from('a').toString('base64url'), owner]]);
  const parent = { id: 's', status: 'idle' };
  const hooks = new Map<string, (...args: any[]) => any>();
  let held = false;
  const ctx = { storageDomain: { open: async () => ({table: () => ({get: (id: string) => rows.get(id),put: async (id: string, value: any) => rows.set(id,value)}),close: async()=>{}}) },
    on: (name: string, callback: (...args: any[])=>any) => hooks.set(name,callback), effect: (factory:()=>()=>void) => disposals.push(factory()), agents: {get: () => parent} };
  const configs = new Map([['a',config]]);
  const instance = new Dreaming(ctx as never, {} as never, { configOf:()=>configs.get('a'), configs,
    bindings:new Map([['s',{sessionId:'s',agentId:'a',ownerId:'owner',cwd:'/owner',revision:'1'}]]), held:()=>held, notify:()=>{} });
  return { instance, config, configs, parent, owner, hooks, hold:(value:boolean)=>{held=value;} };
}
it('admits only due quiet or completed-step work and defers while foreground provider work is active', async () => {
  const f = scheduler(); const launch=vi.spyOn(f.instance,'start').mockResolvedValue({});
  await f.instance.tick('a',1099);expect(launch).not.toHaveBeenCalled();
  await f.instance.tick('a',1100);expect(launch).toHaveBeenCalledTimes(1);
  launch.mockClear();f.owner.lastSuccessAutomatic=1100;
  await f.instance.tick('a',1199);expect(launch).not.toHaveBeenCalled();
  f.owner.retryAt=1300;await f.instance.tick('a',1200);expect(launch).not.toHaveBeenCalled();
  delete f.owner.retryAt;
  f.hold(true);await f.instance.tick('a',1200);expect(launch).not.toHaveBeenCalled();f.hold(false);
  f.config.features!.dreaming=false;await f.instance.tick('a',1200);expect(launch).not.toHaveBeenCalled();f.config.features!.dreaming=true;
  const now=Date.now();f.hooks.get('session/event')!({id:'s'},{type:'user/message'});
  await f.instance.tick('a',now);expect(launch).not.toHaveBeenCalled();
  f.parent.status='running';await f.instance.tick('a',now);expect(launch).toHaveBeenCalledTimes(1);launch.mockClear();
  let release!:()=>void;const held = new Promise<void>(resolve=>{release=resolve;});
  const stream=f.hooks.get('llm/stream')!({sessionId:'s'},async function*(){await held;yield {};});
  const next=stream.next();await Promise.resolve();
  await f.instance.tick('a',now);expect(launch).not.toHaveBeenCalled();
  release();await next;await stream.return();
  await f.instance.tick('a',now);expect(launch).toHaveBeenCalledTimes(1);
});
it('cancels active automatic work when disabled but permits an explicit manual run to finish', async()=>{
  const f=scheduler();const automatic={automatic:true,controller:new AbortController(),promise:Promise.resolve()};
  (f.instance as any).active.set('a',automatic);
  await f.instance.configurationChanging({...f.config,features:{dreaming:false}});
  expect(automatic.controller.signal.aborted).toBe(true);
  const manual={...automatic,automatic:false,controller:new AbortController()};(f.instance as any).active.set('a',manual);
  await f.instance.configurationChanging({...f.config,features:{dreaming:false}});expect(manual.controller.signal.aborted).toBe(false);
  await f.instance.configurationChanging({...f.config,knowledge:{memoryMode:'legacy'}});expect(manual.controller.signal.aborted).toBe(true);
});
