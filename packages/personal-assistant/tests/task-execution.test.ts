import {expect,it} from 'vitest';
import type {AgentConfiguration,RelayInput,TaskResponsibility} from '@nano/product-contracts';
import {TaskExecution} from '../src/task-execution.js';
import {NodeStore} from '../src/store.js';

it('discovers UI-started responsibility, validates the current session, and recovers an unconfirmed stop',async()=>{
  const store=new NodeStore(':memory:','owner');
  const agent:AgentConfiguration={agentId:'a',mode:'single_thread',workspace:'/tmp',revision:'1',provider:'p',model:'m',features:{task_graph:false,cron_scheduling:true}};
  let task:TaskResponsibility={graph_id:'g',node_id:'n1',title:'Wait for decision',status:'waiting',revision:2,conversation:{id:'chat'},relative_url:'/tasks/g',wait:{reason:'Await reply',schedule_id:'schedule',owner_agent_id:'a',session_id:'previous',next_check_at:new Date(Date.now()+60_000).toISOString()}};
  let online=true,paused=false,valid=true,noticeOnline=false;const notices:Record<string,unknown>[]=[];const runtimeBlocks:boolean[]=[];
  const options={nodeId:'node',ownerId:'owner',store,agents:[agent],drain:async()=>{},context:async()=>({messages:[{inputId:'original-task-pause',conversationId:'chat',content:[{type:'text' as const,text:'Original Task update with application-attested human pause'}]}],revoked:[]}),runtime:{onNotification:()=>()=>{},request:async(method:string,value:unknown)=>{
    const args=value as Record<string,unknown>;
    if(method==='task.execution.block')runtimeBlocks.push(Boolean(args.blocked));
    if(method==='task.context.passive'){notices.push(args);if(!noticeOnline)throw new Error('notice unavailable');return {accepted:true,durable:true};}
    if(method==='session.cancel')return {wasRunning:true};
    if(method==='schedule.wait.inspect')return {valid,owner_agent_id:'a',session_id:args.sessionId,next_check_at:task.wait?.next_check_at,checked_at:new Date().toISOString()};
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
    expect(await service.snapshot(identity)).toMatchObject({kind:'continue',repair_task_ids:['g/n1']});
    task={...task,wait:{...task.wait!,session_id:binding.sessionId}};
    const updated='2026-10-23T15:00:00Z';
    Object.assign(task,{updated_at:updated});
    expect(await service.snapshot(identity)).toMatchObject({kind:'quiescent',tasks:[{status:'waiting',updated_at:updated}]});
    valid=false;expect(await service.snapshot(identity)).toMatchObject({kind:'continue',repair_task_ids:['g/n1']});
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
