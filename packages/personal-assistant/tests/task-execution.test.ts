import {expect,it} from 'vitest';
import type {AgentConfiguration,RelayInput,TaskResponsibility} from '@nano/product-contracts';
import {TaskExecution} from '../src/task-execution.js';
import {NodeStore} from '../src/store.js';

it('discovers UI-started doing_wake once, keeps unscheduled waiting quiet, and recovers an unconfirmed stop',async()=>{
  const store=new NodeStore(':memory:','owner');
  const agent:AgentConfiguration={agentId:'a',mode:'single_thread',workspace:'/tmp',revision:'1',provider:'p',model:'m',features:{task_graph:false,cron_scheduling:true}};
  let task:TaskResponsibility={
    graph_id:'g',node_id:'n1',title:'Wait for decision',status:'waiting',revision:2,
    conversation:{id:'chat'},relative_url:'/tasks/g',
    wait:{reason:'Confirm timeline?',asked_user_id:'owner'},
  };
  let online=true,paused=false,noticeOnline=false;const notices:Record<string,unknown>[]=[];const runtimeBlocks:boolean[]=[];
  const options={nodeId:'node',ownerId:'owner',store,agents:[agent],drain:async()=>{},context:async()=>({messages:[{inputId:'original-task-pause',conversationId:'chat',content:[{type:'text' as const,text:'Original Task update with application-attested human pause'}]}],revoked:[]}),runtime:{onNotification:()=>()=>{},request:async(method:string,value:unknown)=>{
    const args=value as Record<string,unknown>;
    if(method==='task.execution.block')runtimeBlocks.push(Boolean(args.blocked));
    if(method==='task.context.passive'){notices.push(args);if(!noticeOnline)throw new Error('notice unavailable');return {accepted:true,durable:true};}
    if(method==='session.cancel')return {wasRunning:true};
    return {};
  }},relay:{request:async(type:string)=>{
    if(type==='task.execution.scopes')return {type:'result',payload:{ok:true,result:{conversation_ids:['chat']}}};
    if(type==='task.execution.pause'){if(!online)throw new Error('offline');paused=true;return {type:'result',payload:{ok:true,result:{paused:1}}};}
    return {type:'result',payload:{ok:true,result:{items:paused?[]:[task]}}};
  }}};
  let service=new TaskExecution(options);
  try{
    await service.recover(['a']);
    expect(store.bindings()).toHaveLength(0);
    agent.features!.task_graph=true;
    await service.recover(['a']);
    const binding=store.bindingFor('a','chat')!;expect(binding).toBeTruthy();
    const identity={sessionId:binding.sessionId,agentId:'a',ownerId:'owner'};

    // Waiting without a schedule stays quiescent without a repair_task_ids loop.
    expect(await service.snapshot(identity)).toMatchObject({kind:'quiescent',tasks:[{status:'waiting',wait:{reason:'Confirm timeline?',asked_user_id:'owner'}}]});

    // External doing_wake triggers single-shot continue until durably acked; self-authored doing stays quiescent.
    task={
      graph_id:'g',node_id:'n1',title:'Execute approved plan',status:'doing',revision:3,
      updated_at:'2026-10-23T15:00:00Z',conversation:{id:'chat'},relative_url:'/tasks/g',
      doing_wake:{revision:3,at:'2026-10-23T15:00:00Z',actor:{type:'user',id:'owner'},assignee_id:'a'},
    };
    expect(await service.snapshot(identity)).toMatchObject({kind:'continue',tasks:[{status:'doing',unwoken_doing:true}]});
    service.ackDoing({...identity,items:[{graph_id:'g',node_id:'n1',revision:3}]});
    const ackedSnap=await service.snapshot(identity);
    expect(ackedSnap).toMatchObject({kind:'quiescent',tasks:[{status:'doing'}]});
    expect(ackedSnap.tasks[0]?.unwoken_doing).toBeUndefined();

    task={...task,revision:4,doing_wake:{revision:4,at:'2026-10-23T15:05:00Z',actor:{type:'agent',id:'a'},assignee_id:'a'}};
    const selfSnap=await service.snapshot(identity);
    expect(selfSnap).toMatchObject({kind:'quiescent',tasks:[{status:'doing'}]});
    expect(selfSnap.tasks[0]?.unwoken_doing).toBeUndefined();

    const input:RelayInput={agent_id:'a',conversation_id:'chat',relay_task_id:'stop',idempotency_key:'stop',metadata:{},message:{id:'stop',content:'/stop',sender_type:'user',sender_user_id:'owner',attachments:[]}};
    online=false;
    await expect(service.stop(binding,input)).rejects.toThrow('offline');
    expect(await service.snapshot(identity)).toMatchObject({kind:'unavailable',reason:'stop_pending'});
    expect(store.controls().find(i=>i.action==='task-stop')?.text).toBeUndefined();
    service=new TaskExecution(options);online=true;
    await expect(service.recoverStops()).rejects.toThrow('notice unavailable');
    expect(paused).toBe(true);expect(runtimeBlocks.at(-1)).toBe(true);
    expect(store.controls().find(i=>i.action==='task-stop')?.text).toBeUndefined();
    noticeOnline=true;await service.recoverStops();
    expect(notices).toHaveLength(2);expect(notices[0]).toEqual(notices[1]);
    expect(notices[0]).toMatchObject({messages:[{inputId:'original-task-pause',conversationId:'chat'}]});
    expect(JSON.stringify(notices[0])).not.toContain('task-stop-notice');
    expect(runtimeBlocks.at(-1)).toBe(false);expect(paused).toBe(true);
    expect(await service.snapshot(identity)).toMatchObject({kind:'quiescent',tasks:[]});
    expect(await service.stop(binding,input)).toMatchObject({paused:1});
  }finally{store.close();}
});

it('checks only the current Task session, including mirrored external conversations', async () => {
  const store = new NodeStore(':memory:', 'owner');
  const binding = {agentId:'a',sessionId:'old',ownerId:'owner',conversationId:'external:chat',cwd:'/tmp',revision:'1'};
  store.bind(binding); store.aliasConversation('a','shadow','external:chat');
  store.reset(binding,{...binding,sessionId:'current'},'reset');
  const calls: unknown[] = [];
  const service = new TaskExecution({nodeId:'node',ownerId:'owner',store,
    agents:[{agentId:'a',mode:'single_thread',workspace:'/tmp',revision:'1',provider:'p',model:'m'}],
    runtime:{onNotification:()=>()=>{},request:async (_method,args)=>{calls.push(args);return {valid:true};}},
    relay:{request:async()=>({type:'result',payload:{ok:true,result:{items:[]}}})},
    drain:async()=>{},context:async()=>({messages:[],revoked:[]}),
  });
  try {
    expect(await service.inspect({agent_id:'a',conversation_id:'shadow',schedule_id:'schedule'})).toMatchObject({valid:true});
    expect(calls).toEqual([expect.objectContaining({sessionId:'current',scheduleId:'schedule'})]);
    expect(await service.inspect({agent_id:'a',conversation_id:'external:chat',schedule_id:'schedule'})).toMatchObject({valid:false});
    expect(await service.snapshot({agentId:'a',ownerId:'owner',sessionId:'old'})).toMatchObject({reason:'session_superseded'});
    expect(calls).toHaveLength(1);
  } finally {store.close();}
});
