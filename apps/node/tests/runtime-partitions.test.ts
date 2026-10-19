import { expect, it } from 'vitest';
import type { AgentConfiguration, SessionBinding } from '@nano/product-contracts';
import { RuntimePartitions, type PartitionRuntime, type RuntimePartition } from '../src/runtime-partitions.js';
class Host implements PartitionRuntime {
  available = true;
  calls: {method:string;params:unknown}[] = [];
  listeners = new Set<(method:string,value:unknown)=>void>();
  handlers = new Map<string,(params:unknown)=>unknown>();
  result: Record<string, unknown> = {};
  async start() {this.available=true;}
  async shutdown(){this.available=false;}
  async request(method:string,params:unknown){if(!this.available)throw new Error('offline');this.calls.push({method,params});return this.result[method] ?? {};}
  onNotification(listener:(method:string,value:unknown)=>void){this.listeners.add(listener);return()=>{this.listeners.delete(listener);};}
  handle(method:string,handler:(params:unknown)=>unknown){this.handlers.set(method,handler);}
  emit(method:string,value:unknown){for(const listener of this.listeners)listener(method,value);}
}
const config=(agentId:string,personal=false)=>({agentId,revision:'1',workspace:'/private/work',mode:'global',provider:'p',model:'m',...(personal?{personal:{bindingId:agentId,ownerId:'owner',conversationId:'dm',epoch:1}}:{})}) as AgentConfiguration;
function fixture(){
  const agents=[config('ordinary'),config('pa',true)];
  const bindings=agents.map(agent=>({agentId:agent.agentId,sessionId:`root-${agent.agentId}`,ownerId:'owner',cwd:agent.workspace,revision:'1',conversationId:'dm'})) as SessionBinding[];
  const errors:unknown[]=[];const hosts=new Map<string,Host>();
  const runtime=new RuntimePartitions({agents,bindings:()=>bindings,create:partition=>{const host=new Host();hosts.set(partition.key,host);return host;},onError:error=>errors.push(error)});
  return {runtime,hosts,errors,ordinary:hosts.get('ordinary')!,pa:hosts.get('personal:pa:1')!};
}
it('keeps sessions, child callbacks and configuration in their trusted host',async()=>{
  const {runtime,ordinary,pa,errors}=fixture();const received:unknown[]=[];
  runtime.onNotification((_method,value)=>received.push(value));
  await runtime.request('session.observe',{sessionId:'root-pa'});
  expect(pa.calls.at(-1)?.method).toBe('session.observe');expect(ordinary.calls).toEqual([]);
  await expect(runtime.request('session.observe',{sessionId:'root-pa',agentId:'ordinary'})).rejects.toThrow('conflicting');
  pa.emit('session.event',{sessionId:'child',rootSessionId:'root-pa',event:{type:'step/start'}});
  await runtime.request('session.observe',{sessionId:'child'});expect(pa.calls.at(-1)?.params).toEqual({sessionId:'child'});
  ordinary.emit('session.event',{sessionId:'root-pa',rootSessionId:'root-ordinary'});
  expect(received).toHaveLength(1);expect(errors).toHaveLength(1);
  runtime.handle('product.call',value=>value);
  await expect(Promise.resolve().then(()=>ordinary.handlers.get('product.call')!({agentId:'pa',sessionId:'root-pa'}))).rejects.toThrow('forged');
  await expect(runtime.request('configuration.apply',{...config('pa',true),personal:undefined})).rejects.toThrow('immutable');
});
it('keeps native collection ACKs scoped even when identifiers collide and another host is offline',async()=>{
  const {runtime,ordinary,pa}=fixture();const partition=runtime.forAgent('pa');
  const port=runtime.scoped(partition);
  ordinary.result['workflow.pending']=[{id:'same',parentSessionId:'root-ordinary'}];
  pa.result['workflow.pending']=[{id:'same',parentSessionId:'root-pa'}];
  ordinary.available=false;
  expect(await port.request('workflow.pending',{})).toEqual([{id:'same',parentSessionId:'root-pa'}]);
  await port.request('workflow.acknowledge',{runId:'same'});
  expect(pa.calls.at(-1)).toEqual({method:'workflow.acknowledge',params:{runId:'same'}});
  expect(ordinary.calls).toEqual([]);
  await expect(runtime.request('workflow.pending',{})).rejects.toThrow('scoped');
  pa.result['knowledge.facts']={facts:[{id:'forged',agentId:'ordinary',rootSessionId:'root-ordinary'}]};
  await expect(port.request('knowledge.facts',{})).rejects.toThrow('forged');
});
it('routes opaque observer handles only to the prepared generation and releases every prepared update host',async()=>{
  const {runtime,ordinary,pa}=fixture();
  await runtime.request('trajectory.prepare',{observerId:'observer',rootAgentId:'pa',rootSessionId:'root-pa'});
  await runtime.request('trajectory.call',{observerId:'observer',method:'session/read'});
  expect(pa.calls.at(-1)?.method).toBe('trajectory.call');expect(ordinary.calls).toEqual([]);
  expect(runtime.unavailable(runtime.forAgent('pa'))).toEqual(['observer']);
  await expect(runtime.request('trajectory.next',{observerId:'observer'})).rejects.toThrow('generation_changed');
  ordinary.result['update.prepare']={ready:true};pa.result['update.prepare']={ready:false};
  expect(await runtime.request('update.prepare',{operationId:'update'})).toEqual({ready:false});
  expect(ordinary.calls.at(-1)?.method).toBe('update.release');expect(pa.calls.at(-1)?.method).toBe('update.release');
});
it('creates a new personal host before applying its configuration without exposing it to ordinary initialization',async()=>{
  const {runtime,ordinary,hosts}=fixture();await runtime.start();
  await runtime.request('configuration.apply',config('second',true));
  expect(hosts.get('personal:second:1')?.calls.at(-1)?.method).toBe('configuration.apply');
  expect(runtime.forAgent('second').agents.map(agent=>agent.agentId)).toEqual(['second']);
  expect(ordinary.calls).toEqual([]);
});

it('drops unbound preview status without weakening trusted product calls',async()=>{
  const {runtime,pa,errors}=fixture();const received:unknown[]=[];
  runtime.onNotification((_method,value)=>received.push(value));
  pa.emit('session.status',{sessionId:'preview',status:'idle'});
  expect(received).toEqual([]);expect(errors).toEqual([]);
  runtime.handle('product.call',value=>value);
  await expect(Promise.resolve().then(()=>pa.handlers.get('product.call')!({sessionId:'preview'}))).rejects.toThrow('trusted Session lineage');
});
