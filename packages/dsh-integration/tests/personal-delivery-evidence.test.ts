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
