import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';
import {registerNoopTaskContext} from './helpers/noop-task-context.js';

it('delivers a newly transitioned doing_wake in the next running step before further tool work',async()=>{
 const home=await mkdtemp(join(tmpdir(),'nano-task-wake-running-'));let client:RuntimeClient|undefined;
 try {
  await writeFile(join(home,'probe.mjs'),`import {appendFile,writeFile,readFile} from 'node:fs/promises';
export const name='running-wake-probe';export const inject=['llm','tools'];
export function apply(ctx){let call=0;
 ctx.tools.register({name:'hold_step',description:'Hold one step',parameters:{type:'object',properties:{}},output:{schema:{type:'string'},render:()=>[{type:'text',text:'done'}]},execute:async()=>{
  await writeFile(process.env.DSH_HOME+'/held','ready');
  while(!await readFile(process.env.DSH_HOME+'/release','utf8').catch(()=>''))await new Promise(resolve=>setTimeout(resolve,10));
  return 'done';
 }});
 ctx.on('tools/pre-execute',(exec,next)=>exec.name==='hold_step'?{kind:'allow'}:next(),{prepend:true});
 ctx.on('llm/stream',async function*(o){
  await appendFile(process.env.DSH_HOME+'/calls',JSON.stringify(o.messages)+'\\n');
  if(++call===1){yield{type:'block-end',index:0,block:{type:'tool-call',id:'hold-call',name:'hold_step',arguments:{}}};yield{type:'finish',reason:{kind:'tool-use'}};}
  else{yield{type:'block-end',index:0,block:{type:'text',text:'Observed doing wake'}};yield{type:'finish',reason:{kind:'stop'}};}
 });
}`);
  await prepareProfile(home,[{insert:[{id:'running-wake-probe',name:join(home,'probe.mjs')}]}]);
  client=new RuntimeClient({home,cwd:home});registerNoopTaskContext(client);let armed=false;
  client.rpc.handle('product.task_execution.ack',()=>null);
  client.rpc.handle('product.task_execution.snapshot',()=>armed?{kind:'continue',tasks:[{graph_id:'g',node_id:'n1',title:'Newly approved stage',status:'doing',revision:2,updated_at:'2026-10-31T00:00:00Z',unwoken_doing:true,doing_wake:{revision:2,at:'2026-10-31T00:00:00Z',actor:{type:'user',id:'o'},assignee_id:'a'},root_node_id:'root',root_title:'North Star Goal',root_goal_summary:'Ship clean demo',conversation:{id:'c'},relative_url:'/tasks/g'}]}:{kind:'quiescent',tasks:[]});
  await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',features:{task_graph:true},toolAllowlist:['hold_step','task_graph']}],bindings:[]});
  await client.rpc.request('session.ensure',{sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home});
  await client.rpc.request('session.submit',{sessionId:'s',inputId:'work',mode:'followup',content:[{type:'text',text:'Continue this work'}],source:{kind:'human',actorId:'o',channel:'test',messageId:'work'}});
  await expect.poll(()=>readFile(join(home,'held'),'utf8').catch(()=>'')).toBe('ready');
  armed=true;
  await client.rpc.request('task.execution.changed',{agentId:'a'});
  await writeFile(join(home,'release'),'continue');
  const calls=async()=>(await readFile(join(home,'calls'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
  await expect.poll(async()=>(await calls()).length).toBeGreaterThanOrEqual(2);
  armed=false;
  const next=(await calls())[1];
  const message=next.find((entry:any)=>entry.source?.channel==='task-reminder');
  expect(message).toBeDefined();
  const text=JSON.stringify(message);
  expect(text).toContain('A Task newly entered doing or was assigned/resumed for you');
  expect(text).toContain('Newly approved stage');
  expect(text).toContain('North Star Goal');
  expect(text.match(/Current Task context:/g)).toHaveLength(1);
 } finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},20_000);

it('coalesces multiple unwoken doing tasks into one current Task package per native step while respecting execution block',async()=>{
 const home=await mkdtemp(join(tmpdir(),'nano-task-reminder-batch-'));let client:RuntimeClient|undefined;
 try {
  await writeFile(join(home,'probe.mjs'),`import {writeFile} from 'node:fs/promises';
export const name='task-batch-probe';export const inject=['llm'];
export function apply(ctx){ctx.on('llm/stream',async function*(o){await writeFile(process.env.DSH_HOME+'/call',JSON.stringify(o.messages));yield{type:'block-end',index:0,block:{type:'text',text:'NO_REPLY'}};yield{type:'finish',reason:{kind:'stop'}};});}`);
  await prepareProfile(home,[{insert:[{id:'task-batch-probe',name:join(home,'probe.mjs')}]}]);
  client=new RuntimeClient({home,cwd:home});registerNoopTaskContext(client);let active=false;
  client.rpc.handle('product.task_execution.ack',()=>null);
  client.rpc.handle('product.task_execution.snapshot',async()=>!active||await readFile(join(home,'call'),'utf8').catch(()=>'')?{kind:'quiescent',tasks:[]}:{kind:'continue',tasks:['one','two'].map((node_id,idx)=>({graph_id:'g',node_id,title:node_id,status:'doing' as const,revision:idx+2,updated_at:'2026-10-30T01:00:00Z',unwoken_doing:true,doing_wake:{revision:idx+2,at:'2026-10-30T01:00:00Z',actor:{type:'user' as const,id:'o'},assignee_id:'a'},conversation:{id:'c'},relative_url:'/tasks/g'}))});
  await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',features:{task_graph:true}}],bindings:[]});
  await client.rpc.request('session.ensure',{sessionId:'s',agentId:'a',ownerId:'o',revision:'1',cwd:home});
  await client.rpc.request('task.execution.block',{sessionId:'s',blocked:true});active=true;
  await client.rpc.request('task.execution.changed',{agentId:'a'});
  await new Promise(resolve=>setTimeout(resolve,80));
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
 } finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},20_000);
