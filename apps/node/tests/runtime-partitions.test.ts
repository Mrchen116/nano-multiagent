import { expect, it } from 'vitest';
import type { AgentConfiguration, SessionBinding } from '@nano/product-contracts';
import { InboxStore, KnowledgeUpdates, NodeStore } from '@nano/personal-assistant';
import { RuntimePartitions, type PartitionRuntime, type RuntimePartition } from '../src/runtime-partitions.js';
class Host implements PartitionRuntime {
  available = true;
  calls: {method:string;params:unknown}[] = [];
  listeners = new Set<(method:string,value:unknown)=>void>();
  handlers = new Map<string,(params:unknown)=>unknown>();
  result: Record<string, unknown> = {'configuration.apply': {effective:true}};
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

it('keeps only applied configurations in the restart snapshot',async()=>{
  const {runtime,ordinary,hosts}=fixture();
  const partition=runtime.forAgent('ordinary'),previous=partition.agents[0];
  const candidate={...config('ordinary'),revision:'rejected',features:{cron_scheduling:false}};
  ordinary.result['configuration.prepare']={ready:false,error_code:'capability_in_use'};
  expect(await runtime.request('configuration.prepare',{operationId:'close',fingerprint:'next',config:candidate})).toMatchObject({ready:false});
  expect(partition.agents[0]).toBe(previous);
  ordinary.result['configuration.prepare']={ready:true};
  await runtime.request('configuration.prepare',{operationId:'close',fingerprint:'next',config:candidate});
  expect(partition.agents[0]).toBe(previous);
  ordinary.result['configuration.apply']={effective:false};
  await runtime.request('configuration.apply',candidate);
  expect(partition.agents[0]).toBe(previous);
  ordinary.result['configuration.apply']={effective:true};
  await runtime.request('configuration.apply',candidate);
  expect(partition.agents[0]).toEqual(candidate);
  const fresh=config('new-pa',true);
  await runtime.request('configuration.prepare',{operationId:'new',fingerprint:'new',config:fresh});
  expect(runtime.forAgent('new-pa').agents).toEqual([]);
  await runtime.request('configuration.release',{agentId:'new-pa',operationId:'new'});
  expect(hosts.get('personal:new-pa:1')?.calls.at(-1)?.method).toBe('configuration.release');
});

it('drops unbound preview status without weakening trusted product calls',async()=>{
  const {runtime,pa,errors}=fixture();const received:unknown[]=[];
  runtime.onNotification((_method,value)=>received.push(value));
  pa.emit('session.status',{sessionId:'preview',status:'idle'});
  expect(received).toEqual([]);expect(errors).toEqual([]);
  runtime.handle('product.call',value=>value);
  await expect(Promise.resolve().then(()=>pa.handlers.get('product.call')!({sessionId:'preview'}))).rejects.toThrow('trusted Session lineage');
});

it('does not acknowledge a new host fact when an old generation delivery completes late',async()=>{
  const {runtime,pa,errors}=fixture(),partition=runtime.forAgent('pa');
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  store.bind({agentId:'pa',sessionId:'root-pa',ownerId:'owner',cwd:'/private/work',revision:'1',conversationId:'dm'});
  const fact={id:'same-fact',reviewId:'same-review',agentId:'pa',rootSessionId:'root-pa',sessionId:'root-pa',kind:'memory',action:'add',turn:1};
  pa.result['knowledge.facts']={facts:[fact],reviews:[{id:'same-review',status:'completed'}]};
  let release!:()=>void,delivering!:()=>void;
  const started=new Promise<void>(resolve=>{delivering=resolve;}),receipt=new Promise<void>(resolve=>{release=resolve;});
  const updates=new KnowledgeUpdates({nodeId:'node',agents:[config('pa',true)],runtime:runtime.scoped(partition),store,inbox,partitionKey:partition.key,
    im:async()=>({}),onError:error=>errors.push(error),relay:{request:async()=>{delivering();await receipt;return{type:'ack',payload:{message_id:'old-receipt'}};}}});
  try {
    const pending=updates.recover();await started;
    runtime.unavailable(partition);
    pa.result['knowledge.facts']={facts:[{...fact,turn:2}],reviews:[{id:'same-review',status:'completed'}]};
    release();await pending;
    expect(pa.calls.filter(call=>call.method==='knowledge.acknowledge')).toEqual([]);
    expect(String(errors.at(-1))).toContain('generation_changed');
    await updates.recover();
    expect(pa.calls.filter(call=>call.method==='knowledge.acknowledge')).toEqual([{method:'knowledge.acknowledge',params:{id:'same-fact'}}]);
  } finally {release();await updates.stop();inbox.close();store.close();}
});
