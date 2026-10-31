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
  return {db,ctx,tasks,inspect,changed,runtime,graph,waiting};
}

describe('durable Task execution responsibility',()=>{
  it('versions only the edited responsibility when another node in the same graph changes',()=>{
    vi.useFakeTimers({toFake:['Date']});
    try {
      vi.setSystemTime(new Date('2026-10-23T15:00:00Z'));
      const {tasks,graph}=setup();
      const added=tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:1,request_key:'add',change_note:'Add independent work',operations:[{op:'add_task',container_id:'n1',client_ref:'other',title:'Other',status:'doing',assignee:{type:'agent',id:'a'}}]});
      const other=added.client_refs.other;
      const times=()=>Object.fromEntries(tasks.executionSnapshot(actor,'chat').items.map((n:any)=>[n.node_id,n.updated_at]));
      const initial=times();
      vi.setSystemTime(new Date('2026-10-23T15:01:00Z'));
      tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:2,request_key:'body',change_note:'New constraint',operations:[{op:'update_task',node_id:'n1',patch:{description:'A changed constraint without a title or status change'}}]});
      const revised=times();
      expect(revised.n1).not.toBe(initial.n1);expect(revised[other]).toBe(initial[other]);
      vi.setSystemTime(new Date('2026-10-23T15:02:00Z'));
      tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:3,request_key:'other-body',change_note:'Independent update',operations:[{op:'update_task',node_id:other,patch:{description:'Other changed'}}]});
      expect(times().n1).toBe(revised.n1);
    } finally {vi.useRealTimers();}
  });
  it('caps both new and renewed waits at one hour without changing the graph on rejection',async()=>{
    const {tasks,inspect,waiting,graph}=setup();
    const now=Date.now();
    const clock=vi.spyOn(Date,'now').mockReturnValue(now);
    const proof=(delay:number)=>({valid:true,owner_agent_id:'a',session_id:'session-a',next_check_at:new Date(now+delay).toISOString(),checked_at:new Date(now).toISOString()});
    try {
      inspect.mockResolvedValue(proof(3_600_001));
      await expect(tasks.executeChecked(actor,'apply',waiting)).rejects.toMatchObject({code:'task_wait_schedule_too_late'});
      expect(tasks.execute(actor,'get',{graph_id:graph.graph_id,view:'all'}).revision).toBe(1);
      inspect.mockResolvedValue(proof(3_600_000));
      await tasks.executeChecked(actor,'apply',waiting);
      const renewal={...waiting,base_revision:2,request_key:'renew',operations:[{op:'update_task',node_id:'n1',patch:{status:'waiting',wait:{reason:'Still waiting after checking alternatives',schedule_id:'schedule-b'}}}]};
      inspect.mockResolvedValue(proof(3_600_001));
      await expect(tasks.executeChecked(actor,'apply',renewal)).rejects.toMatchObject({code:'task_wait_schedule_too_late'});
      expect(tasks.execute(actor,'get',{graph_id:graph.graph_id,view:'all'}).nodes[0].wait.schedule_id).toBe('schedule-a');
      inspect.mockResolvedValue(proof(30_000));
      await tasks.executeChecked(actor,'apply',renewal);
      expect(tasks.execute(actor,'get',{graph_id:graph.graph_id,view:'all'}).nodes[0].wait.schedule_id).toBe('schedule-b');
    } finally {clock.mockRestore();}
  });
  it('returns committed child feedback with the fixed conversation and replays that receipt after later changes',async()=>{
    const {tasks,graph,waiting}=setup();
    const added=tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:1,request_key:'add',change_note:'Add child',operations:[{op:'add_task',container_id:'n1',client_ref:'child',title:'Child work',status:'doing',assignee:{type:'agent',id:'a'}}]});
    const child=added.client_refs.child;
    const args={...waiting,base_revision:2,operations:[{op:'update_task',node_id:child,patch:{status:'waiting',wait:{reason:'External artifact absent',schedule_id:'schedule-a'}}}]};
    const result=await tasks.executeChecked(actor,'apply',args);
    expect(result.feedback).toMatchObject({conversation_id:'chat',tasks:[{node_id:child,title:'Child work',status:'waiting',wait:{reason:'External artifact absent',schedule_id:'schedule-a',session_id:'session-a',owner_agent_id:'a'}}]});
    expect(result.feedback.tasks).toHaveLength(1);
    expect(result.feedback.tasks[0].wait.next_check_at).toBeTruthy();
    tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:3,request_key:'later',change_note:'Pause',operations:[{op:'update_task',node_id:child,patch:{status:'paused'}}]});
    expect(await tasks.executeChecked(actor,'apply',args)).toEqual(result);
    expect(tasks.execute(actor,'get',{graph_id:graph.graph_id,view:'all'}).nodes.find((n:any)=>n.id===child).status).toBe('paused');
  });
  it('allows the selected Task tool without the Feature, but keeps automatic execution gated', () => {
    const {db,tasks,graph}=setup();
    db.prepare("UPDATE agent_profiles SET features_json=?").run(JSON.stringify({task_graph:false}));
    expect(tasks.execute(actor,'get',{graph_id:graph.graph_id,view:'all'}).graph_id).toBe(graph.graph_id);
    expect(() => tasks.executionSnapshot(actor,'chat')).toThrow();
  });
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
  const stop=ctx.messaging.insertMessage('chat','u1','user','/stop');ctx.messaging.queueRepresentedRelays(stop,'no-agent');
  const stopping=gateway.handle(connection,'task.execution.pause',{node_id:'n',agent_id:'a',conversation_id:'chat',request_id:'stop',request_key:'stop',control_message_id:stop.id});
  expect(gateway.tasks.execute(human,'get',{graph_id:graph.graph_id,view:'all'}).nodes[0].status).toBe('doing');
  release({valid:true,owner_agent_id:'a',session_id:'s',next_check_at:new Date(Date.now()+60000).toISOString(),checked_at:new Date().toISOString()});
  expect((await writing).payload.ok).toBe(true);const stopped=await stopping;expect(stopped,JSON.stringify(stopped)).toMatchObject({payload:{ok:true,result:{paused:1}}});
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


it('closes waiting and resumed work with human audit before publishing dissolution',async()=>{
  const {db,ctx,tasks,changed,graph,waiting}=setup();
  ctx.gateway.tasks=tasks;
  db.prepare("UPDATE conversations SET type='group',creator_id='u1' WHERE id='chat'").run();
  tasks.pauseExecution(actor,'chat','stop');
  tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:2,request_key:'resume',change_note:'Resume',operations:[{op:'update_task',node_id:'n1',patch:{status:'doing'}}]});
  await tasks.executeChecked(actor,'apply',{...waiting,base_revision:3});
  const read=()=>tasks.execute(human,'get',{graph_id:graph.graph_id,view:'all'});
  expect(read().nodes[0]).toMatchObject({status:'waiting',resume_request:{actor_id:'u1'},updated_by:'Agent (a)'});
  // The domain action must handle a whole graph, beyond apply's 100-operation limit.
  const added=tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:4,request_key:'many',change_note:'Add work',operations:Array.from({length:100},(_,i)=>({op:'add_task',client_ref:'work-'+i,container_id:'n1',title:'Work '+i,status:i===0?'done':i===1?'closed':'todo'}))});
  tasks.execute(actor,'apply',{graph_id:graph.graph_id,base_revision:added.revision,request_key:'agent-update',change_note:'Agent reviewed progress',operations:[{op:'update_task',node_id:'n1',patch:{description:'Latest Agent update'}}]});
  const before=read();
  const storedBefore=JSON.parse(db.prepare('SELECT document_json FROM task_graphs WHERE graph_id=?').get(graph.graph_id)!.document_json as string);
  const complete=tasks.execute(actor,'create',{title:'Completed graph',mode:'dag',status:'done',result:'Keep result',conversation_id:'chat',request_key:'completed'});
  const completeBefore=tasks.execute(human,'get',{graph_id:complete.graph_id,view:'all'});
  const counts=()=>['messages','conversation_events','relay_tasks','task_graph_mutation_receipts','task_node_chat_activity'].map(table=>db.prepare(`SELECT count(*) AS n FROM ${table}`).get()!.n);
  const beforeCounts=counts();
  changed.mockClear(); ctx.gateway.broadcast.mockClear();
  const observed:any[]=[];
  changed.mockImplementation(hint=>{observed.push({hint,tasks:tasks.executionSnapshot(actor,'chat').items,transaction:db.isTransaction});});
  ctx.messaging.dissolveConversation('u1','chat');
  const after=read(),at=db.prepare("SELECT dissolved_at FROM conversations WHERE id='chat'").get()!.dissolved_at;
  expect(after).toMatchObject({revision:before.revision+1,updated_at:at,updated_by:'u1 (u1)',conversation:{can_write:false}});
  expect(after.nodes).toHaveLength(101);
  for(const node of after.nodes.filter((n:any)=>!['n2','n3'].includes(n.id))) {
    expect(node).toMatchObject({status:'closed',updated_at:at,updated_by:'u1 (u1)',updated_by_actor:{type:'user',id:'u1'},provenance:{agent_id:null,source_message_id:null}});
    expect(node.change_note).toBeTruthy();
    expect(node.wait).toBeUndefined();expect(node.resume_request).toBeUndefined();
  }
  // Read permissions change for every node, but finished records themselves do not.
  const stored=JSON.parse(db.prepare('SELECT document_json FROM task_graphs WHERE graph_id=?').get(graph.graph_id)!.document_json as string);
  for(const id of ['n2','n3']) {
    expect(stored.nodes.find((n:any)=>n.id===id)).toEqual(storedBefore.nodes.find((n:any)=>n.id===id));
  }
  expect(after.nodes[0].created_by).toEqual(before.nodes[0].created_by);
  expect(after.nodes[0].assignee).toEqual(before.nodes[0].assignee);
  const completed=tasks.execute(human,'get',{graph_id:complete.graph_id,view:'all'});
  expect(completed.nodes[0]).toMatchObject({status:'done',result:'Keep result',updated_by:completeBefore.nodes[0].updated_by,updated_at:completeBefore.nodes[0].updated_at});
  expect(completed).toMatchObject({revision:2,updated_by:'u1 (u1)'});
  for(const row of db.prepare('SELECT revision,updated_at,updated_by,document_json FROM task_graphs').all()) {
    expect(JSON.parse(row.document_json as string)).toMatchObject({revision:row.revision,updated_at:row.updated_at,updated_by:row.updated_by});
  }
  expect(observed).toHaveLength(2);
  expect(observed).toEqual(expect.arrayContaining([
    {hint:{agent_ids:['a'],conversation_ids:['chat']},tasks:[],transaction:false},
    {hint:{agent_ids:[],conversation_ids:['chat']},tasks:[],transaction:false},
  ]));
  expect(counts()).toEqual(beforeCounts.map((value,index)=>index<2?Number(value)+1:value));
  const withdrawal=JSON.parse(db.prepare("SELECT system_notice_json FROM messages WHERE system_notice_json LIKE '%access_revoked%' ORDER BY rowid DESC LIMIT 1").get()!.system_notice_json as string);
  expect(withdrawal).toMatchObject({kind:'task_graph',change_kinds:['access_revoked']});
  expect(JSON.stringify(withdrawal)).not.toContain('Completed graph');
  expect(db.prepare("SELECT count(*) AS n FROM relay_tasks WHERE status IN ('queued','sent','accepted')").get()!.n).toBe(0);
  expect(ctx.gateway.broadcast).toHaveBeenCalled();
});

it('rolls back all dissolution records and publishes nothing if a later graph cannot save',()=>{
  const {db,ctx,tasks,changed}=setup();ctx.gateway.tasks=tasks;
  db.prepare("UPDATE conversations SET type='group',creator_id='u1' WHERE id='chat'").run();
  tasks.execute(human,'create',{title:'Second',mode:'dag',conversation_id:'chat',request_key:'second',assignee:{type:'agent',id:'a'}});
  const snapshot=()=>['conversations','task_graphs','relay_tasks','messages','conversation_events'].map(table=>db.prepare(`SELECT * FROM ${table}`).all());
  const before=snapshot();changed.mockClear();ctx.gateway.broadcast.mockClear();
  // Fail on the second graph only, after the first graph and conversation were written.
  db.exec("CREATE TEMP TRIGGER fail_later_graph BEFORE UPDATE ON task_graphs WHEN (SELECT count(*) FROM task_graphs WHERE revision>1)=1 BEGIN SELECT RAISE(ABORT,'injected graph save failure'); END");
  expect(()=>ctx.messaging.dissolveConversation('u1','chat')).toThrow('injected graph save failure');
  expect(snapshot()).toEqual(before);
  expect(changed).not.toHaveBeenCalled();expect(ctx.gateway.broadcast).not.toHaveBeenCalled();
  expect(db.isTransaction).toBe(false);
});

it('dissolves a taskless group without task notices or execution invalidations',()=>{
  const {db,ctx}=fixture();ctx.gateway.broadcast=vi.fn();ctx.messaging=new Messaging(ctx);
  const changed=vi.fn();ctx.gateway.tasks=new TaskGraphService(db,ctx.messaging,undefined,{inspect:vi.fn(),changed});
  db.prepare("UPDATE conversations SET type='group',creator_id='u1' WHERE id='chat'").run();
  ctx.messaging.dissolveConversation('u1','chat');
  expect(db.prepare("SELECT dissolved_at FROM conversations WHERE id='chat'").get()!.dissolved_at).toBeTruthy();
  expect(db.prepare('SELECT count(*) AS n FROM messages').get()!.n).toBe(0);
  expect(changed).not.toHaveBeenCalled();expect(ctx.gateway.broadcast).toHaveBeenCalled();
});

it('keeps stop-generated collaboration notices passive for the stopped Agent',()=>{
  const {db,tasks,graph}=setup();
  tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:1,request_key:'children',change_note:'',operations:[{op:'add_task',container_id:'n1',client_ref:'child',title:'Same Agent child',status:'doing',assignee:{type:'agent',id:'a'}}]});
  const before=(db.prepare('SELECT message_id FROM relay_tasks').all() as any[]).map(row=>row.message_id);
  tasks.pauseExecution(actor,'chat','quiet-stop');
  const relays=(db.prepare('SELECT payload_json FROM relay_tasks').all() as any[]).map(row=>JSON.parse(row.payload_json)).filter(payload=>!before.includes(payload.message.id));
  expect(relays.length).toBeGreaterThan(0);
  expect(relays.every(payload=>payload.agent_id==='a'&&payload.metadata.context_only===true)).toBe(true);
});

it('notifies former and current assignees after human and Agent edits, reassignment and deletion commit',()=>{
  const {db,tasks,changed,graph}=setup();
  db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES('b1','agent:b','B','o1',?,'active')").run(new Date().toISOString());
  db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,tool_allowlist_json,workspace_root,created_at,updated_at) SELECT 'b',owner_id,node_id,'B',tool_allowlist_json,workspace_root,created_at,updated_at FROM agent_profiles WHERE agent_id='a'").run();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','b1')").run();
  const peer={kind:'agent' as const,id:'b',node_id:'n'};
  let revision=1;
  const apply=(who:typeof human|typeof actor,operations:unknown[])=>tasks.execute(who,'apply',{graph_id:graph.graph_id,base_revision:revision++,request_key:'edit-'+revision,change_note:'Current requirement',operations});
  const observations:any[]=[];
  changed.mockImplementation(hint=>observations.push({hint,a:tasks.executionSnapshot(actor,'chat').items,b:tasks.executionSnapshot(peer,'chat').items}));
  apply(peer,[{op:'update_task',node_id:'n1',patch:{description:'Updated by another Agent'}}]);
  expect(observations.at(-1)).toMatchObject({hint:{agent_ids:['a']},a:[{revision:2}],b:[]});
  apply(human,[{op:'set_assignee',node_id:'n1',assignee:{type:'agent',id:'b'}}]);
  expect(observations.at(-1)).toMatchObject({hint:{agent_ids:['a','b']},a:[],b:[{revision:3}]});
  apply(human,[{op:'update_task',node_id:'n1',patch:{status:'paused'}}]);
  expect(observations.at(-1)).toMatchObject({hint:{agent_ids:['b']},a:[],b:[]});
  apply(human,[{op:'update_task',node_id:'n1',patch:{status:'doing'}}]);
  expect(observations.at(-1).b[0].resume_request).toMatchObject({actor_id:'u1',revision:5});
  apply(peer,[{op:'set_assignee',node_id:'n1',assignee:null}]);
  expect(observations.at(-1)).toMatchObject({hint:{agent_ids:['b']},a:[],b:[]});
  apply(human,[{op:'set_assignee',node_id:'n1',assignee:{type:'agent',id:'a'}}]);
  const before=observations.length;
  expect(()=>tasks.execute(human,'apply',{graph_id:graph.graph_id,base_revision:1,request_key:'stale',change_note:'',operations:[{op:'update_task',node_id:'n1',patch:{title:'Stale'}}]})).toThrow();
  expect(observations).toHaveLength(before);
  tasks.execute(human,'delete',{graph_id:graph.graph_id,base_revision:revision,request_key:'delete'});
  expect(observations.at(-1)).toMatchObject({hint:{agent_ids:['a']},a:[],b:[]});
});
