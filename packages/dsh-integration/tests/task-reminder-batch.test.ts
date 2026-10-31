import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';
import {registerNoopTaskContext} from './helpers/noop-task-context.js';

it('coalesces two durable repair candidates into one current Task package per native step',async()=>{
 const home=await mkdtemp(join(tmpdir(),'nano-task-reminder-batch-'));let client:RuntimeClient|undefined;
 try {
  await writeFile(join(home,'probe.mjs'),`import {writeFile} from 'node:fs/promises';
export const name='task-batch-probe';export const inject=['llm'];
export function apply(ctx){ctx.on('llm/stream',async function*(o){await writeFile(process.env.DSH_HOME+'/call',JSON.stringify(o.messages));yield{type:'block-end',index:0,block:{type:'text',text:'NO_REPLY'}};yield{type:'finish',reason:{kind:'stop'}};});}`);
  await prepareProfile(home,[{insert:[{id:'task-batch-probe',name:join(home,'probe.mjs')}]}]);
  client=new RuntimeClient({home,cwd:home});registerNoopTaskContext(client);let active=false;
  const ids=['task-wait-repair:deletion-one','task-wait-repair:deletion-two'];
  client.rpc.handle('product.task_execution.snapshot',async()=>!active||await readFile(join(home,'call'),'utf8').catch(()=>'')?{kind:'quiescent',tasks:[],repair_task_ids:[]}:{kind:'continue',tasks:['one','two'].map(node_id=>({graph_id:'g',node_id,title:node_id,status:'waiting',revision:2,conversation:{id:'c'},relative_url:'/tasks/g'})),repair_task_ids:['g/one','g/two'],repairs:['one','two'].map(node_id=>({graph_id:'g',node_id,reason_code:'schedule_deleted',schedule_id:'deleted-'+node_id,checked_at:'2026-10-30T01:00:00Z'}))});
  await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',features:{task_graph:true}}],bindings:[]});
  await client.rpc.request('session.ensure',{sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home});
  await client.rpc.request('task.execution.block',{sessionId:'s',blocked:true});active=true;
  for(const inputId of ids)expect(await client.rpc.request('task.wait.repair',{agentId:'a',sessionId:'s',inputId})).toMatchObject({durable:true});
  expect(await readFile(join(home,'call'),'utf8').catch(()=>null)).toBeNull();
  await client.rpc.request('task.execution.block',{sessionId:'s',blocked:false});
  await client.rpc.request('session.submit',{sessionId:'s',inputId:'independent',mode:'followup',content:[{type:'text',text:'Check my current work.'}],source:{kind:'human',actorId:'o',channel:'test',messageId:'independent'}});
  await expect.poll(()=>readFile(join(home,'call'),'utf8').catch(()=>null)).not.toBeNull();
  await expect.poll(async()=>(await client!.rpc.request('session.observe',{sessionId:'s'}) as {status:string}).status).toBe('idle');
  const messages=JSON.parse(await readFile(join(home,'call'),'utf8')) as {id:string;content:{type:string;text?:string}[];source?:{channel?:string}}[];
  const text=messages.flatMap(message=>message.content).filter(part=>part.type==='text').map(part=>part.text??'').join('\n');
  expect(text.match(/Current Task context:/g)).toHaveLength(1);
  expect(text.match(/Deliver meaningful results or a new blocker to the Task's fixed conversation[.]/g)).toHaveLength(1);
  const pack=messages.find(message=>message.content.some(part=>part.text?.includes('Current Task context:')))!;
  const lines=pack.content.find(part=>part.text?.includes('Current Task context:'))!.text!.split('\n');
  const context=JSON.parse(lines.find(line=>line.startsWith('{'))!);
  expect(context.tasks.map((task:{node_id:string})=>task.node_id)).toEqual(['one','two']);
  expect(context.repairs.map((repair:{node_id:string})=>repair.node_id)).toEqual(['one','two']);
  const observed=await client.rpc.request('session.observe',{sessionId:'s'}) as {events:{type:string;data:{id?:string}}[]};
  for(const id of ids)expect(observed.events.filter(event=>event.type==='user/message'&&event.data.id===id)).toHaveLength(1);
 } finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},20_000);
