import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import type { RuntimeStopHistory } from '../../product-contracts/src/index.js';
import { RuntimeClient, RuntimeSupervisor, prepareProfile } from '../src/client.js';

const config = {agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',features:{task_graph:false,memory_curation:false,skill_creation:false}};
const binding = (home:string) => ({sessionId:'root',agentId:'a',revision:'1',ownerId:'owner',cwd:home});
const input = (id:string,mode='inject') => ({sessionId:'root',inputId:id,mode,content:[{type:'text',text:id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});

it('clears cold durable inbox once per disable revision and preserves fresh post-enable work on later restart', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-cold-disable-'));let client:RuntimeClient|undefined;
  const start=async(lifecycle?:unknown)=>{client=new RuntimeClient({home,cwd:home});await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding(home)],lifecycle});await client.rpc.request('session.ensure',binding(home));};
  try {
    await prepareProfile(home); await start();
    const {sessionId, ...rest}=binding(home);
    await expect(client!.rpc.request('session.ensure',{...rest,sessionId})).resolves.toMatchObject({sessionId:'root'});
    await expect(client!.rpc.request('session.ensure',{...rest,sessionId,ownerId:'other'})).rejects.toThrow('binding conflict');
    await client!.rpc.request('session.submit',input('old'));
    client!.process.kill('SIGKILL'); await client!.exited;
    await start({revision:3,disabledThroughRevision:2});
    expect(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:'old'})).toMatchObject({accepted:true,pending:false,terminal:{kind:'cancelled-before-consumption'}});
    await client!.rpc.request('session.submit',input('new'));
    client!.process.kill('SIGKILL'); await client!.exited;
    await start({revision:3,disabledThroughRevision:2});
    expect(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:'new'})).toMatchObject({accepted:true,pending:true});
  } finally {if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},30_000);

it('drains real one-shot and continuable descendants, background Bash process trees and PTY while another host keeps running', async () => {
  const homes=await Promise.all([0,1].map(()=>mkdtemp(join(tmpdir(),'nano-native-disable-'))));
  const logs:string[]=[];const supervisors:RuntimeSupervisor[]=[];const finalHistory:RuntimeStopHistory[][]=[];
  const content=async(home:string,file:string)=>readFile(join(home,file),'utf8').catch(()=> '');
  try {
    for(const home of homes) {
      await writeFile(join(home,'fixture.mjs'), `import {writeFile} from 'node:fs/promises';
export const inject=['llm','subagents','agents','subprocess','jobs'];
export function apply(ctx) {
  ctx.jobs.attachController('disable-fixture');
  ctx.on('llm/stream',async function*(o){await new Promise(resolve=>{if(o.signal?.aborted)resolve();else o.signal?.addEventListener('abort',resolve,{once:true});});yield {type:'finish',reason:{kind:'stop'}};});
  ctx.on('agent/created',({agent})=>{if(agent.id!=='root')return;setTimeout(async()=>{try {
    const home=process.env.DSH_HOME;
    await ctx.agents.create({sessionId:'internal-review',meta:{cwd:home,agentPreset:'nano:a:1'}});
    const child=await ctx.subagents.start('spawn',{parent:agent,prompt:[{type:'text',text:'hold child'}],signal:new AbortController().signal});
    const grandchild=await ctx.subagents.start('spawn',{parent:child.localAgent,prompt:[{type:'text',text:'hold grandchild'}],signal:new AbortController().signal});
    const continued=await ctx.subagents.startContinuable({provider:'spawn',label:'persistent child',request:{parent:agent,prompt:[{type:'text',text:'hold continued'}]},signal:new AbortController().signal});
    const shell=ctx.subprocess.spawn({argv:['/bin/bash','-c',"trap '' TERM; (trap '' TERM; while true; do echo tick >> bash-ticks; sleep .03; done) & wait"],cwd:home,stdio:{stdin:'ignore',stdout:'ignore',stderr:'ignore'},graceMs:150});
    const job=ctx.jobs.start({kind:'bash',label:'managed tree',owner:grandchild.id,run:()=>({cancel:()=>shell.terminate(),done:shell.done.then(()=>({status:'killed'}))})});
    const pty=await ctx.subprocess.spawnTerminal({argv:['/bin/bash','--noprofile','--norc','-i'],cwd:home,rows:24,cols:80,terminalType:'xterm',graceMs:250});
    await pty.write('(while true; do echo tick >> pty-ticks; sleep .03; done);\\n');
    await writeFile(home+'/ready.json',JSON.stringify({child:child.id,grandchild:grandchild.id,continued:continued.childId,job}));
  }catch(error){await writeFile(process.env.DSH_HOME+'/error',String(error));}},0);});
}`);
      await prepareProfile(home,[{insert:[{id:'disable-fixture',name:join(home,'fixture.mjs')}]}]);
      const supervisor=new RuntimeSupervisor({home,cwd:home,disableCursors:()=>({root:0}),onDisabledHistory:history=>{finalHistory.push(history);},onLog:t=>logs.push(t),initialize:async rpc=>{await rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding(home)],lifecycle:{revision:3,disabledThroughRevision:2}});await rpc.request('session.ensure',binding(home));},onReady:async()=>{},onError:error=>logs.push(String(error))});
      supervisors.push(supervisor);await supervisor.start();
      await expect.poll(async()=>await content(home,'error')||await content(home,'ready.json'),{timeout:10000}).toContain('grandchild');
      await expect.poll(()=>content(home,'bash-ticks')).toContain('tick');
      await expect.poll(()=>content(home,'pty-ticks')).toContain('tick');
    }
    const before=await content(homes[1]!,'bash-ticks');const started=Date.now();
    expect(await supervisors[0]!.disable(),logs.join('')).toMatchObject({confirmed:true});
    expect(Date.now()-started).toBeLessThan(5000);
    expect(finalHistory[0]).toHaveLength(4);
    expect(finalHistory[0]!.map(row=>row.rootSessionId)).toEqual(['root','root','root','root']);
    expect(finalHistory[0]!.filter(row=>row.parentSessionId)).toHaveLength(3);
    expect(finalHistory[0]!.find(row=>row.sessionId==='root')!.events.every(event=>event.seq>0)).toBe(true);
    expect(finalHistory[0]!.some(row=>row.events.some(event=>event.type==='turn/end'))).toBe(true);
    const bash=await content(homes[0]!,'bash-ticks'),pty=await content(homes[0]!,'pty-ticks');
    await new Promise(resolve=>setTimeout(resolve,200));
    expect(await content(homes[0]!,'bash-ticks')).toBe(bash);
    expect(await content(homes[0]!,'pty-ticks')).toBe(pty);
    expect((await content(homes[1]!,'bash-ticks')).length).toBeGreaterThan(before.length);
    expect(await supervisors[1]!.disable(),logs.join('')).toMatchObject({confirmed:true});
  } finally {for(const s of supervisors){await s.disable();s.process?.kill('SIGKILL');}await Promise.all(homes.map(home=>rm(home,{recursive:true,force:true})));}
},30_000);

it('reports unconfirmed when a managed owner cleanup throws even though Cordis disposal resolves', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-cleanup-error-'));const errors:string[]=[];
  const supervisor=new RuntimeSupervisor({home,cwd:home,initialize:async rpc=>{await rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding(home)]});await rpc.request('session.ensure',binding(home));},onReady:async()=>{},onError:error=>errors.push(String(error))});
  try {
    await writeFile(join(home,'cleanup.mjs'), `export function apply(ctx){ctx.on('agent/created',({agent})=>{agent.ctx.effect(()=>()=>{throw new Error('fixture-cleanup-failed');});});}`);
    await prepareProfile(home,[{insert:[{id:'cleanup-error',name:join(home,'cleanup.mjs')}]}]);await supervisor.start();
    expect(await supervisor.disable()).toMatchObject({confirmed:false,errorDetail:expect.stringContaining('fixture-cleanup-failed')});
    expect(errors.join('')).toContain('fixture-cleanup-failed');
  } finally {supervisor.process?.kill('SIGKILL');await rm(home,{recursive:true,force:true});}
},10000);

it('skips expired schedules before restore and stamps only new automatic inputs with the enabled revision', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-schedule-disable-'));let client:RuntimeClient|undefined;
  const scheduled={...config,toolAllowlist:['schedule_create','schedule_run']};
  const start=async(lifecycle?:unknown)=>{client=new RuntimeClient({home,cwd:home});await client.rpc.request('initialize',{protocol:1,agents:[scheduled],bindings:[binding(home)],lifecycle});await client.rpc.request('session.ensure',binding(home));};
  try {
    await writeFile(join(home,'model.mjs'), `export const inject=['llm'];export function apply(ctx){ctx.on('llm/stream',async function*(){yield {type:'block-end',index:0,block:{type:'text',text:'done'}};yield {type:'finish',reason:{kind:'stop'}};});}`);
    await prepareProfile(home,[{insert:[{id:'model',name:join(home,'model.mjs')}]}]);await start();
    const expired=await client!.rpc.request('schedule.command',{agentId:'a',sessionId:'root',action:'create',args:{title:'Missed',prompt:'must not catch up',after_seconds:1}}) as {id:string};
    client!.process.kill('SIGKILL');await client!.exited;
    await new Promise(resolve=>setTimeout(resolve,1100));await start({revision:3,disabledThroughRevision:2});
    expect(await client!.rpc.request('schedule.command',{agentId:'a',action:'catalog'})).toEqual(expect.arrayContaining([expect.objectContaining({id:expired.id,status:'inactive'})]));
    expect(await client!.rpc.request('schedule.evidence',{sessionId:'root'})).toEqual([]);
    await expect(client!.rpc.request('session.submit',{...input('stale'),lifecycle_revision:1})).rejects.toThrow('stale_lifecycle');
    await client!.rpc.request('session.submit',{...input('new-human'),mode:'followup'});
    const future=await client!.rpc.request('schedule.command',{agentId:'a',sessionId:'root',action:'create',args:{title:'New',prompt:'new schedule',after_seconds:1}}) as {id:string};
    await expect.poll(async()=>await client!.rpc.request('schedule.evidence',{sessionId:'root'}),{timeout:5000}).toEqual(expect.arrayContaining([expect.objectContaining({scheduleId:future.id,accepted:true})]));
    const view=await client!.rpc.request('session.observe',{sessionId:'root'}) as {events:{type:string;data:{id:string;source?:{kind:string;lifecycle_revision?:number}}}[]};
    expect(view.events.find(event=>event.type==='user/message'&&event.data.id==='new-human')?.data.source).toMatchObject({lifecycle_revision:3});
    await expect.poll(async()=>{const observed=await client!.rpc.request('session.observe',{sessionId:'root'}) as typeof view;return observed.events.find(event=>event.type==='user/message'&&event.data.source?.kind==='schedule')?.data.source;}).toMatchObject({lifecycle_revision:3});
  } finally {if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},15000);

it('expires durable model commands, fallback, Workflow and knowledge work before cold owners attach', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-owners-disable-'));let client:RuntimeClient|undefined;let logs='';
  const moduleUrl=(file:string)=>new URL(`../lib/${file}.js`,import.meta.url).href;
  try {
    await writeFile(join(home,'seed.mjs'), `import {access,writeFile} from 'node:fs/promises';
import {modelDomain} from ${JSON.stringify(moduleUrl('model-policy'))};
import {modelRunsDomain} from ${JSON.stringify(moduleUrl('model-fallback'))};
import {workflowDomain} from ${JSON.stringify(moduleUrl('workflow/state'))};
import {knowledgeDomain} from ${JSON.stringify(moduleUrl('knowledge/state'))};
export const inject=['storageDomain'];
export async function apply(ctx){const marker=process.env.DSH_HOME+'/seeded';try{await access(marker);return;}catch{}
  const key=x=>Buffer.from(x).toString('base64url');
  const model=await ctx.storageDomain.open(modelDomain);await model.table('commands').put(key('old-command'),{sessionId:'root',action:'compact',argument:'',status:'pending'});
  const fallback=await ctx.storageDomain.open(modelRunsDomain);await fallback.table('runs').put(key('old-run'),{id:'old-run',sessionId:'root',revision:'1',turn:0,inputs:['old'],attempts:[],state:'switching'});
  const workflow=await ctx.storageDomain.open(workflowDomain);await workflow.table('runs').put(key('old-workflow'),{id:'old-workflow',parentSessionId:'root',inputIds:['old'],budgetId:'budget',guideline:'',script:'',args:{},meta:{},route:{provider:'deepseek-official',model:'deepseek-flash'},state:'paused',startedAt:1,revision:1,calls:[],logs:[]});
  const knowledge=await ctx.storageDomain.open(knowledgeDomain);await knowledge.table('reviews').put(key('old-review'),{id:'old-review',agentId:'a',rootSessionId:'root',kind:'memory',turn:0,status:'running',at:1});await knowledge.table('facts').put(key('old-fact'),{id:'old-fact',agentId:'a',rootSessionId:'root',sessionId:'root',kind:'memory',turn:0,action:'add',path:'MEMORY.md'});
  await writeFile(marker,'done');
}`);
    const seed={insert:[{id:'seed',name:join(home,'seed.mjs')}]};
    await prepareProfile(home,[{id:'nano-runtime',disabled:true},seed]);
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
    await expect.poll(()=>readFile(join(home,'seeded'),'utf8').catch(()=>logs),{timeout:5000}).toBe('done');
    client.process.kill('SIGKILL');await client.exited;
    await prepareProfile(home,[seed]);
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding(home)],lifecycle:{revision:3,disabledThroughRevision:2}});
    await client.rpc.request('session.ensure',binding(home));
    expect(await client.rpc.request('session.command',{sessionId:'root',id:'old-command',action:'compact'})).toMatchObject({status:'completed',success:false});
    expect(await client.rpc.request('session.observe',{sessionId:'root'})).toMatchObject({modelRuns:[{id:'old-run',state:'completed',terminal:{kind:'cancelled',reason:'agent_disabled'}}]});
    expect(await client.rpc.request('workflow.pending',{})).toEqual([]);
    expect(await client.rpc.request('workflow.read',{sessionId:'root',runId:'old-workflow'})).toMatchObject([{state:'cancelled',cancelledByDisable:true}]);
    expect(await client.rpc.request('knowledge.facts',{})).toMatchObject({facts:[],reviews:[{id:'old-review',status:'cancelled',diagnostic:'agent_disabled'}]});
  } catch(error) {throw new Error(String(error)+'\n'+logs,{cause:error});} finally {if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},20000);
