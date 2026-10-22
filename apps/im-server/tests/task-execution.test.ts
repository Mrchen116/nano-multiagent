import { describe, expect, it, vi } from 'vitest';
import { fixture } from './control-fixture.js';
import { TaskGraphService } from '../src/task-graphs.js';
import { Messaging } from '../src/messaging.js';

const actor = {kind:'agent' as const,id:'a',node_id:'n'};
const human = {kind:'user' as const,id:'u1'};
function setup() {
  const {db,ctx}=fixture(); ctx.gateway.broadcast=vi.fn(); ctx.messaging=new Messaging(ctx);
  const inspect=vi.fn(async()=>({valid:true,owner_agent_id:'a',session_id:'session-a',next_check_at:new Date(Date.now()+60000).toISOString(),checked_at:new Date().toISOString()}));
  const changed=vi.fn();
  const runtime=vi.fn(async()=>({state:'running' as const}));
  const tasks=new TaskGraphService(db,ctx.messaging,undefined,{inspect,changed,runtime});
  const graph=tasks.execute(human,'create',{title:'Release',mode:'dag',conversation_id:'chat',request_key:'create',assignee:{type:'agent',id:'a'},status:'doing'});
  const waiting={graph_id:graph.graph_id,base_revision:1,request_key:'wait',change_note:'Asked owner; delivery confirmed',operations:[{op:'update_task',node_id:'n1',patch:{status:'waiting',wait:{reason:'Await budget; resume on reply',schedule_id:'schedule-a'}}}]};
  return {db,tasks,inspect,changed,runtime,graph,waiting};
}

describe('durable Task execution responsibility',()=>{
  it('requires real schedule evidence, saves waiting atomically, and replays a confirmed write after schedule expiry',async()=>{
    const {tasks,inspect,waiting,graph}=setup();
    inspect.mockResolvedValueOnce({valid:false} as any);
    await expect(tasks.executeChecked(actor,'apply',waiting)).rejects.toThrow('schedule');
    expect(tasks.execute(actor,'get',{graph_id:graph.graph_id,view:'all'}).revision).toBe(1);
    const saved=await tasks.executeChecked(actor,'apply',waiting);
    const node=tasks.execute(actor,'get',{graph_id:graph.graph_id,view:'all'}).nodes[0];
    expect(node).toMatchObject({status:'waiting',wait:{schedule_id:'schedule-a',owner_agent_id:'a',session_id:'session-a'}});
    inspect.mockResolvedValue({valid:false} as any);
    expect(await tasks.executeChecked(actor,'apply',waiting)).toEqual(saved);
    tasks.execute(human,'apply',{...waiting,base_revision:2,request_key:'pause',operations:[{op:'update_task',node_id:'n1',patch:{status:'paused'}}]});
    expect(tasks.execute(actor,'get',{graph_id:graph.graph_id,view:'all'}).nodes[0].wait).toBeUndefined();
  });
  it('does not overwrite a revision changed while waiting for schedule validation',async()=>{
    const {tasks,inspect,waiting,graph}=setup();
    inspect.mockImplementationOnce(async()=>{
      tasks.execute(human,'apply',{...waiting,request_key:'rename',operations:[{op:'update_task',node_id:'n1',patch:{title:'Changed while checking'}}]});
      return {valid:true,owner_agent_id:'a',session_id:'session-a',next_check_at:new Date(Date.now()+60000).toISOString(),checked_at:new Date().toISOString()};
    });
    await expect(tasks.executeChecked(actor,'apply',waiting)).rejects.toThrow('current graph');
    expect(tasks.execute(actor,'get',{graph_id:graph.graph_id,view:'all'}).nodes[0]).toMatchObject({status:'doing',title:'Changed while checking'});
  });
  it('returns every owned depth beyond a page and atomically pauses the exact scope once',()=>{
    const {tasks,graph}=setup();
    tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:1,request_key:'children',change_note:'',operations:Array.from({length:55},(_,i)=>({op:'add_task',container_id:'n1',client_ref:'c'+i,title:'Child '+i,status:i===54?'todo':'doing',assignee:{type:'agent',id:'a'}}))});
    expect(tasks.executionSnapshot(actor,'chat').items).toHaveLength(55);
    const paused=tasks.pauseExecution(actor,'chat','stop-1');
    expect(paused.paused).toBe(55);
    tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:3,request_key:'resume',change_note:'Owner resumed',operations:[{op:'update_task',node_id:'n1',patch:{status:'doing'}}]});
    expect(tasks.pauseExecution(actor,'chat','stop-1')).toEqual(paused);
    expect(tasks.executionSnapshot(actor,'chat').items).toHaveLength(1);
    expect(tasks.execute(actor,'get',{graph_id:graph.graph_id,view:'all'}).nodes.at(-1).status).toBe('todo');
  });
});

it('pauses after a server write still awaiting native evidence, even when its client no longer awaits the result',async()=>{
  const {Gateway}=await import('../src/gateway.js');
  const {db,ctx}=fixture();ctx.messaging=new Messaging(ctx);
  const gateway=new Gateway(ctx);ctx.gateway=gateway;gateway.valid=()=>true;
  const connection={node_id:'n',owner_id:'o1',node_epoch:1,token:'token',lastSeen:0,socket:{readyState:0}} as any;
  gateway.nodes.set('n',connection);
  const graph=gateway.tasks.execute(human,'create',{title:'Pending write',mode:'dag',conversation_id:'chat',request_key:'create',status:'doing',assignee:{type:'agent',id:'a'}});
  let release!:(value:any)=>void,entered!:()=>void;const checking=new Promise<void>(resolve=>{entered=resolve;});
  gateway.request=async()=>{entered();return new Promise(resolve=>{release=resolve;});};
  const writing=gateway.handle(connection,'task_graph.command',{node_id:'n',agent_id:'a',request_id:'write',action:'apply',args:{graph_id:graph.graph_id,base_revision:1,request_key:'wait',change_note:'',operations:[{op:'update_task',node_id:'n1',patch:{status:'waiting',wait:{reason:'Await delivered request',schedule_id:'schedule'}}}]}});
  await checking;
  const stopping=gateway.handle(connection,'task.execution.pause',{node_id:'n',agent_id:'a',conversation_id:'chat',request_id:'stop',request_key:'stop'});
  expect(gateway.tasks.execute(human,'get',{graph_id:graph.graph_id,view:'all'}).nodes[0].status).toBe('doing');
  release({valid:true,owner_agent_id:'a',session_id:'s',next_check_at:new Date(Date.now()+60000).toISOString(),checked_at:new Date().toISOString()});
  expect((await writing).payload.ok).toBe(true);expect((await stopping).payload.result.paused).toBe(1);
  expect(gateway.tasks.execute(human,'get',{graph_id:graph.graph_id,view:'all'}).nodes[0]).toMatchObject({status:'paused'});
});

it('observes only the stored assignee after enforcing the graph read ACL',async()=>{
  const {tasks,runtime,graph}=setup();
  await expect(tasks.runtimeState({kind:'user',id:'u2'},{graph_id:graph.graph_id,node_id:'n1',agent_id:'someone-else'})).rejects.toThrow();
  expect(runtime).not.toHaveBeenCalled();
  await expect(tasks.runtimeState(human,{graph_id:graph.graph_id,node_id:'missing'})).rejects.toThrow();
  expect(runtime).not.toHaveBeenCalled();
  expect(await tasks.runtimeState(human,{graph_id:graph.graph_id,node_id:'n1',agent_id:'someone-else'})).toEqual({state:'running'});
  expect(runtime).toHaveBeenCalledExactlyOnceWith('a');
  runtime.mockRejectedValueOnce(new Error('Node unavailable'));
  expect(await tasks.runtimeState(human,{graph_id:graph.graph_id,node_id:'n1'})).toEqual({state:'unknown'});
});

it('attests only an authenticated human paused-to-doing transition and clears it on the next pause',()=>{
  const {tasks,graph}=setup();
  const apply=(who:typeof human|typeof actor,status:string,revision:number)=>tasks.execute(who,'apply',{graph_id:graph.graph_id,base_revision:revision,request_key:'status-'+revision,change_note:'',operations:[{op:'update_task',node_id:'n1',patch:{status}}]});
  apply(human,'paused',1);apply(actor,'doing',2);
  expect(tasks.executionSnapshot(actor,'chat').items[0].resume_request).toBeUndefined();
  apply(human,'paused',3);apply(human,'doing',4);
  expect(tasks.executionSnapshot(actor,'chat').items[0].resume_request).toMatchObject({actor_id:'u1',revision:5});
  expect(()=>tasks.execute(actor,'apply',{graph_id:graph.graph_id,base_revision:5,request_key:'forge',change_note:'',operations:[{op:'update_task',node_id:'n1',patch:{resume_request:{actor_id:'u1'}}}]})).toThrow('editable');
  tasks.pauseExecution(actor,'chat','stop-resume-proof');
  apply(actor,'doing',6);
  expect(tasks.executionSnapshot(actor,'chat').items[0].resume_request).toBeUndefined();
});
