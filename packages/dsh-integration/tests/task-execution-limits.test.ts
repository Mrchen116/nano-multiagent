import {registerNoopTaskContext} from './helpers/noop-task-context.js';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';

it('wakes once per external doing_wake revision without idle polling loops, and re-wakes only on a newer doing_wake or due Schedule',async()=>{
  const home=await mkdtemp(join(tmpdir(),'nano-task-limit-'));let client:RuntimeClient|undefined;
  try {
    await writeFile(join(home,'probe.mjs'),`
export const name='task-limit-probe';export const inject=['llm','agents','tools'];
export function apply(ctx){
 const runs=new Map();
 ctx.on('agent/pre-step',({agent,turn},next)=>{
  if(runs.get(agent.id)?.turn!==turn)runs.set(agent.id,{turn,steps:0});
  return next();
 });
 ctx.tools.register({name:'fixture_step',description:'One work step',parameters:{type:'object',properties:{}},output:{schema:{type:'string'},render:()=>[{type:'text',text:'ok'}]},execute:async()=>'ok'});
 ctx.on('tools/pre-execute',(exec,next)=>exec.name==='fixture_step'?{kind:'allow'}:next(),{prepend:true});
 ctx.on('llm/stream',async function*(){
  const agent=ctx.agents.currentInitiator(),run=runs.get(agent.id);const more=++run.steps<2;
  yield{type:'block-end',index:0,block:more?{type:'tool-call',id:'step-'+run.turn+'-'+run.steps,name:'fixture_step',arguments:'{}'}:{type:'text',text:'NO_REPLY'}};
  yield{type:'finish',reason:{kind:more?'tool-calls':'stop'}};
 });
}`);
    await prepareProfile(home,[{insert:[{id:'task-limit-probe',name:join(home,'probe.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home});registerNoopTaskContext(client);
    const acks:unknown[]=[];
    client.rpc.handle('product.task_execution.ack',value=>{acks.push(value);return null;});
    const totals=new Map<string,{automatic:number;schedule:number;turns:number;steps:number}>();
    const count=(id:string)=>{let value=totals.get(id);if(!value){value={automatic:0,schedule:0,turns:0,steps:0};totals.set(id,value);}return value;};
    client.rpc.onNotification((method,payload)=>{
      if(method!=='session.event')return;
      const {sessionId,event}=payload as {sessionId:string;event:{type:string;data:{source?:{kind?:string;channel?:string}}}};
      const value=count(sessionId);
      if(event.type==='user/message'&&event.data.source?.channel==='task-execution')value.automatic++;
      if(event.type==='user/message'&&event.data.source?.kind==='schedule')value.schedule++;
      if(event.type==='turn/end')value.turns++;
      if(event.type==='step/start')value.steps++;
    });
    const revisions=new Map<string,number>([['s',1],['same-agent',0],['other-agent',1]]);
    const ackedBySession=new Map<string,number>();
    client.rpc.handle('product.task_execution.ack',value=>{
      acks.push(value);
      const {sessionId,items}=value as {sessionId:string;items:{revision:number}[]};
      for(const item of items)ackedBySession.set(sessionId,Math.max(ackedBySession.get(sessionId)??0,item.revision));
      return null;
    });
    client.rpc.handle('product.task_execution.snapshot',identity=>{
      const {sessionId,agentId}=identity as {sessionId:string;agentId:string};
      const wakeRevision=revisions.get(sessionId)??0;
      const unwoken=wakeRevision>(ackedBySession.get(sessionId)??0);
      return {
        kind:unwoken?'continue':'quiescent',
        tasks:wakeRevision?[{
          graph_id:'g',node_id:'n',title:'Ongoing goal',status:'doing',revision:wakeRevision,
          updated_at:'2026-10-25T08:00:00Z',unwoken_doing:unwoken,
          doing_wake:{revision:wakeRevision,at:'2026-10-25T08:00:00Z',actor:{type:'user',id:'o'},assignee_id:agentId},
          conversation:{id:'c'},relative_url:'/tasks/g',
        }]:[],
      };
    });
    await client.rpc.request('initialize',{protocol:1,agents:['a','b'].map(agentId=>({agentId,knowledge:{memoryMode:'legacy'},revision:'1',provider:'deepseek-official',model:'deepseek-flash',features:{cron_scheduling:true}})),bindings:[]});
    const ensure=(sessionId:string,agentId:string)=>client!.rpc.request('session.ensure',{sessionId,agentId,ownerId:'o',revision:'1',cwd:home});
    const idle=async(sessionId:string)=>(await client!.rpc.request('session.observe',{sessionId}) as {status:string}).status==='idle';

    await ensure('s','a');
    await expect.poll(async()=>count('s').automatic===1&&await idle('s'),{timeout:10_000}).toBe(true);
    expect(count('s').automatic).toBe(1);
    expect(count('s').steps).toBe(2);
    expect(ackedBySession.get('s')).toBe(1);

    // Repeated change notifications and internal system channels at the same doing_wake revision never spin an idle loop.
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await new Promise(resolve=>setTimeout(resolve,120));
    expect(count('s').automatic).toBe(1);
    for(const channel of ['task-human-control','revalidation','personal-state']) {
      const before=count('s').turns;
      await client.rpc.request('session.submit',{sessionId:'s',inputId:channel,mode:'followup',content:[{type:'text',text:channel}],source:{kind:'system',actorId:'a',channel,messageId:channel}});
      await expect.poll(async()=>count('s').turns>before&&await idle('s')).toBe(true);
      expect(count('s').automatic).toBe(1);
    }

    await ensure('same-agent','a');
    await ensure('other-agent','b');
    await expect.poll(async()=>count('other-agent').automatic===1&&await idle('other-agent')).toBe(true);
    expect(count('same-agent').automatic).toBe(0);

    // An external doing_wake revision advance wakes the Agent once more and settles back to idle.
    revisions.set('s',2);
    await client.rpc.request('task.execution.changed',{agentId:'a'});
    await expect.poll(async()=>count('s').automatic===2&&await idle('s')).toBe(true);
    expect(ackedBySession.get('s')).toBe(2);

    // A due native Schedule wakes the Agent independently without fabricating extra automatic turns.
    await client.rpc.request('schedule.command',{agentId:'a',sessionId:'s',action:'create',args:{title:'Independent check',prompt:'Read the current Task.',after_seconds:1}});
    await expect.poll(async()=>count('s').schedule===1&&await idle('s'),{timeout:5000}).toBe(true);
    expect(count('s').automatic).toBe(2);
  } finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},30_000);
