import { mkdtemp,writeFile,rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect,it } from 'vitest';
import { RuntimeClient,prepareProfile } from '../lib/client.js';

it('recovers schedule creation provenance after restart and grants it only to the actual wake',async()=>{
 const home=await mkdtemp(join(tmpdir(),'pa-schedule-evidence-'));let client:RuntimeClient|undefined,logs='';const sends:any[]=[];
 const config={agentId:'pa',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',personal:{bindingId:'b',ownerId:'owner',conversationId:'dm',epoch:1},features:{intelligent_ui:false,memory_curation:false,skill_creation:false,task_graph:false,cron_scheduling:false,personal_proactivity:false},toolAllowlist:['schedule_create'],approval:{dangerouslySkipPermissions:true}};
 const binding={agentId:'pa',sessionId:'root',ownerId:'owner',revision:'1',cwd:home};
 const start=async()=>{client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});client.rpc.handle('product.call',value=>{const call=value as any;if(call.method==='send_message'){sends.push(call);return {status:'sent',message_id:'sent'};}throw new Error(call.method);});await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});await client.rpc.request('session.ensure',binding);};
 try{
  await writeFile(join(home,'fixture.mjs'),`export const name='schedule-evidence-fixture';export const inject=['llm'];
export function apply(ctx){const seen=new Set();ctx.on('llm/stream',async function*(o){
 const last=o.messages.findLast(m=>m.role==='user'&&['user','schedule'].includes(m.source?.kind));let block;
 if(!seen.has(last.id)){seen.add(last.id);block=last.source.kind==='schedule'?{type:'tool-call',id:'notify',name:'send_message',arguments:JSON.stringify({target:'dm',text:'Due reminder'})}:last.id==='seed'?{type:'tool-call',id:'create',name:'schedule_create',arguments:JSON.stringify({title:'Owner reminder',prompt:'Remind the owner',after_seconds:5})}:{type:'tool-call',id:'later',name:'send_message',arguments:JSON.stringify({target:'dm',text:'Later direct reply'})};}
 else block={type:'text',text:'done'};
 yield{type:'block-end',index:0,block};yield{type:'finish',reason:{kind:block.type==='tool-call'?'tool-calls':'stop'}};
});}`);
  await prepareProfile(home,[{insert:[{id:'schedule-evidence-fixture',name:join(home,'fixture.mjs')}]}]);await start();
  await client!.rpc.request('session.submit',{sessionId:'root',inputId:'seed',mode:'followup',content:[{type:'text',text:'Remind me in five seconds'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'seed'}});
  await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:'seed'}) as any).terminal).toMatchObject({kind:'completed'});
  const [schedule]=await client!.rpc.request('schedule.command',{agentId:'pa',action:'catalog'}) as any[];expect(schedule).toBeDefined();
  await client!.shutdown();client=undefined;await start();
  await expect.poll(()=>sends.length,{timeout:10000}).toBe(1);
  expect(sends[0].liveInputIds).toEqual([]);
  expect(sends[0].scheduleTriggers).toEqual([{scheduleId:schedule.id,sourceMessageIds:['seed']}]);
  await expect.poll(async()=>(await client!.rpc.request('session.observe',{sessionId:'root'}) as any).status).toBe('idle');
  await client!.rpc.request('session.submit',{sessionId:'root',inputId:'later',mode:'followup',content:[{type:'text',text:'Hello'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'later'}});
  await expect.poll(()=>sends.length).toBe(2);expect(sends[1].scheduleTriggers).toEqual([]);expect(sends[1].liveInputIds).toEqual(['later']);
 }catch(error){throw new Error(`${error}\n${logs}`,{cause:error});}
 finally{await client?.shutdown().catch(()=>{});await rm(home,{recursive:true,force:true});}
},25000);

it.each(['return','cancel','restart'])('carries owner provenance only for a live native child %s',async outcome=>{
 const home=await mkdtemp(join(tmpdir(),'pa-child-evidence-'));let client:RuntimeClient|undefined,logs='';const sends:any[]=[];
 const config={agentId:'pa',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',personal:{bindingId:'b',ownerId:'owner',conversationId:'dm',epoch:1},features:{intelligent_ui:false,memory_curation:false,skill_creation:false,task_graph:false,cron_scheduling:false,personal_proactivity:false},toolAllowlist:['subagent','send_message','interrupt_agent'],approval:{dangerouslySkipPermissions:true}};
 const binding={agentId:'pa',sessionId:'root',ownerId:'owner',revision:'1',cwd:home};
 try{
  await writeFile(join(home,'fixture.mjs'),`import {readFile} from 'node:fs/promises';
export const name='child-evidence-fixture';export const inject=['llm','agents','subagents'];
export function apply(ctx){const steps=new Map();ctx.on('llm/stream',async function*(o){
 const agent=ctx.agents.get(o.sessionId),turn=agent.session.snapshotEvents().findLast(e=>e.type==='turn/start').data.turn,key=agent.id+':'+turn,n=steps.get(key)||0;steps.set(key,n+1);let block;
 if(agent.session.header.origin==='subagent'){
  while(!o.signal.aborted&&!await readFile(process.env.DSH_HOME+'/release','utf8').catch(()=>''))await new Promise(r=>setTimeout(r,20));
  if(o.signal.aborted)return;
  block=n===0?{type:'tool-call',id:'child-report',name:'send_message',arguments:JSON.stringify({agent_id:'root',message:'Actual completed child result'})}:{type:'text',text:'Child finished'};
 }else{
  const latest=o.messages.findLast(m=>m.role==='user'&&m.source?.kind!=='runtime-context');
  if(n===0&&latest.id==='seed')block={type:'tool-call',id:'spawn',name:'subagent',arguments:JSON.stringify({description:'Delegated work',prompt:'Prepare requested result and report',run_in_background:true})};
  else if(n===0&&latest.id==='resume'){const child=(await ctx.subagents.listChildren(agent.id))[0];block={type:'tool-call',id:'resume-child',name:'send_message',arguments:JSON.stringify({agent_id:child.id,message:'Continue the original delegated work'})};}
  else if(n===0&&latest.id==='cancel'){const child=(await ctx.subagents.listChildren(agent.id))[0];block={type:'tool-call',id:'cancel-child',name:'interrupt_agent',arguments:JSON.stringify({agent_id:child.id})};}
  else if(n===0)block={type:'tool-call',id:'deliver-'+turn,name:'send_message',arguments:JSON.stringify({target:'dm',text:latest.id==='later'?'Later direct reply':'Child result'})};
  else block={type:'text',text:'done'};
 }
 yield{type:'block-end',index:0,block};yield{type:'finish',reason:{kind:block.type==='tool-call'?'tool-calls':'stop'}};
});}`);
  await prepareProfile(home,[{insert:[{id:'child-evidence-fixture',name:join(home,'fixture.mjs')}]}]);
  const start=async()=>{client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
  client.rpc.handle('product.call',value=>{const call=value as any;if(call.method==='send_message'){sends.push(call);return {status:'sent',message_id:'sent'};}throw new Error(call.method);});
  await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});await client.rpc.request('session.ensure',binding);};await start();
  const submit=(id:string)=>client!.rpc.request('session.submit',{sessionId:'root',inputId:id,mode:'followup',content:[{type:'text',text:id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});
  await submit('seed');
  await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:'seed'}) as any).terminal).toMatchObject({kind:'completed'});
  const [child]=await client!.rpc.request('session.descendants',{sessionId:'root'}) as any[];expect(child.activity).toBe('running');
  if(outcome==='restart'){
   await client!.shutdown();client=undefined;await start();await submit('resume');
   await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:'resume'}) as any).terminal).toMatchObject({kind:'completed'});
  }
  if(outcome==='cancel')await submit('cancel');else await writeFile(join(home,'release'),'ready');
  await expect.poll(async()=>(await client!.rpc.request('session.descendants',{sessionId:'root'}) as any[]).find(row=>row.id===child.id)?.activity,{timeout:10000}).not.toBe('running');
  if(outcome!=='cancel'){
   await expect.poll(()=>sends.filter(call=>call.args.text==='Child result').length).toBeGreaterThan(0);
   const returned=sends.find(call=>call.args.text==='Child result');expect(returned.liveInputIds).toEqual([]);
   expect(returned.childReturns).toEqual([{childId:child.id,sourceMessageIds:['seed']}]);
  }else expect(sends.every(call=>call.childReturns.length===0)).toBe(true);
  await expect.poll(async()=>(await client!.rpc.request('session.observe',{sessionId:'root'}) as any).status).toBe('idle');
  await submit('later');await expect.poll(()=>sends.some(call=>call.args.text==='Later direct reply')).toBe(true);
  expect(sends.find(call=>call.args.text==='Later direct reply').childReturns).toEqual([]);
 }catch(error){throw new Error(`${error}\n${logs}`,{cause:error});}
 finally{await client?.shutdown().catch(()=>{});await rm(home,{recursive:true,force:true});}
},25000);
