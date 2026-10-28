import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import type { SessionEvent } from '@deepseek-ai/dsh-session';
import type { RuntimeStopHistory } from '../../product-contracts/src/index.js';
import { RuntimeClient, RuntimeSupervisor, prepareProfile } from '../src/client.js';

// These lifecycle fixtures intentionally share a workspace; document-mode owners use separate libraries.
const config = {agentId:'a',knowledge:{memoryMode:'legacy'},revision:'1',provider:'deepseek-official',model:'deepseek-flash',features:{task_graph:false,memory_curation:false,skill_creation:false}};
const binding = (home:string) => ({sessionId:'root',agentId:'a',revision:'1',ownerId:'owner',cwd:home});
const input = (id:string,mode='inject') => ({sessionId:'root',inputId:id,mode,content:[{type:'text',text:id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});

it('clears cold durable inbox once per disable revision and preserves fresh post-enable work on later restart', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-cold-disable-'));let client:RuntimeClient|undefined;
  const start=async(lifecycle?:unknown)=>{client=new RuntimeClient({home,cwd:home});await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding(home)],lifecycle:lifecycle?{a:lifecycle}:undefined});await client.rpc.request('session.ensure',binding(home));};
  try {
    await prepareProfile(home); await start();
    const {sessionId, ...rest}=binding(home);
    await expect(client!.rpc.request('session.ensure',{...rest,sessionId})).resolves.toMatchObject({sessionId:'root'});
    await expect(client!.rpc.request('session.ensure',{...rest,sessionId,ownerId:'other'})).rejects.toThrow('binding conflict');
    await client!.rpc.request('session.submit',input('old'));
    client!.process.kill('SIGKILL'); await client!.exited;
    await start({revision:3,disabledThroughRevision:2});
    expect(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:'old'})).toMatchObject({accepted:true,pending:false,terminal:{kind:'cancelled-before-consumption'}});
    const represented = {...input('new'),source:{...input('new').source,sender:{type:'user',id:'owner'},pa_agent_id:'pa-owner'}};
    await client!.rpc.request('session.submit',represented);
    client!.process.kill('SIGKILL'); await client!.exited;
    await start({revision:3,disabledThroughRevision:2});
    expect(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:'new'})).toMatchObject({accepted:true,pending:true});
    const history = await client!.rpc.request('session.observe',{sessionId:'root'}) as {events:SessionEvent[]};
    const restoredInput = history.events.flatMap(event=>event.type==='agent/inbox/spliced'?event.data.inserted:[]).find(message=>message.id==='new');
    expect(restoredInput?.source).toMatchObject({kind:'user',sender:{type:'user',id:'owner'},pa_agent_id:'pa-owner',lifecycle_revision:3});
  } finally {if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},30_000);

it('drains A descendants, Bash and PTY while B continues in the same host, then enables A without restarting', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-native-disable-'));
  let logs='';
  const bindings=[binding(home),{...binding(home),agentId:'b',sessionId:'root-b'}];
  const supervisor=new RuntimeSupervisor({home,cwd:home,onLog:t=>{logs+=t;},initialize:async rpc=>{
    await rpc.request('initialize',{protocol:1,agents:[config,{...config,agentId:'b'}],bindings});
    for(const item of bindings)await rpc.request('session.ensure',item);
  },onReady:async()=>{},onError:error=>{logs+=String(error);}});
  const content=(file:string)=>readFile(join(home,file),'utf8').catch(()=> '');
  try {
    await writeFile(join(home,'fixture.mjs'), `import {writeFile} from 'node:fs/promises';
export const inject=['llm','subagents','agents','subprocess','jobs','terminals'];
export function apply(ctx) {
  ctx.jobs.attachController('disable-fixture');
  ctx.on('llm/stream',async function*(o){await new Promise(resolve=>{if(o.signal?.aborted)resolve();else o.signal?.addEventListener('abort',resolve,{once:true});});yield {type:'finish',reason:{kind:'stop'}};});
  const started=new Set();
  ctx.on('agent/created',({agent})=>{if(!['root','root-b'].includes(agent.id)||started.has(agent.id))return;started.add(agent.id);setTimeout(async()=>{try {
    const home=process.env.DSH_HOME,id=agent.id;
    const child=await ctx.subagents.start('spawn',{parent:agent,prompt:[{type:'text',text:'hold child'}],signal:new AbortController().signal});
    const grandchild=await ctx.subagents.start('spawn',{parent:child.localAgent,prompt:[{type:'text',text:'hold grandchild'}],signal:new AbortController().signal});
    const continued=await ctx.subagents.startContinuable({provider:'spawn',label:'persistent child',request:{parent:agent,prompt:[{type:'text',text:'hold continued'}]},signal:new AbortController().signal});
    const shell=ctx.subprocess.spawn({argv:['/bin/bash','-c',"trap '' TERM; (trap '' TERM; while true; do echo tick >> "+id+"-bash; sleep .03; done) & wait"],cwd:home,stdio:{stdin:'ignore',stdout:'ignore',stderr:'ignore'},graceMs:150});
    const job=ctx.jobs.start({kind:'bash',label:'managed tree',owner:grandchild.id,run:()=>({cancel:()=>shell.terminate(),done:shell.done.then(()=>({status:'killed'}))})});
    const pty=await ctx.terminals.spawn(agent,{type:'shell',cwd:home});
    ctx.jobs.start({kind:'pty-send',label:'managed terminal',owner:agent.id,run:()=>{const send=ctx.terminals.startSend(agent,pty.sessionId,{text:'while true; do echo tick >> '+id+'-pty; sleep .03; done',submit:true});return {cancel:()=>send.cancel(),done:send.done.then(()=>({status:'killed'}))};}});
    await writeFile(home+'/'+id+'-ready',JSON.stringify({child:child.id,grandchild:grandchild.id,continued:continued.childId,job}));
  }catch(error){await writeFile(process.env.DSH_HOME+'/error',String(error));}},0);});
}`);
    const native = createRequire(new URL('../node_modules/@deepseek-ai/dsh/package.json',import.meta.url));
    await prepareProfile(home,[{insert:[{id:'terminals',name:native.resolve('@deepseek-ai/dsh-terminal')},{id:'terminal-bash',name:native.resolve('@deepseek-ai/dsh-terminal-bash')},{id:'disable-fixture',name:join(home,'fixture.mjs')}]}]);
    await supervisor.start();
    const pid=supervisor.process!.pid,instance=supervisor.processInstanceId;
    for(const id of ['root','root-b']) {
      await expect.poll(async()=>await content('error')||await content(id+'-ready'),{timeout:10000}).toContain('grandchild');
      await expect.poll(()=>content(id+'-bash')).toContain('tick');
      await expect.poll(()=>content(id+'-pty')).toContain('tick');
    }
    const before=await content('root-b-bash');
    const stopped=await supervisor.disableAgent('a',2,{root:0});
    expect(stopped,logs).toMatchObject({confirmed:true,processInstanceId:instance});
    expect(stopped.history).toHaveLength(4);
    expect(stopped.history!.every(row=>row.rootSessionId==='root')).toBe(true);
    expect(stopped.history!.some(row=>row.events.some(event=>event.type==='turn/end'))).toBe(true);
    const bash=await content('root-bash'),pty=await content('root-pty');
    await new Promise(resolve=>setTimeout(resolve,200));
    expect(await content('root-bash')).toBe(bash);expect(await content('root-pty')).toBe(pty);
    expect((await content('root-b-bash')).length).toBeGreaterThan(before.length);
    expect(supervisor.process!.pid).toBe(pid);expect(supervisor.available).toBe(true);
    await expect(supervisor.request('session.submit',input('blocked'))).rejects.toThrow('agent_disabled');
    await supervisor.request('agent.enable',{agentId:'a',revision:3,disabledThroughRevision:2});
    await supervisor.request('session.ensure',binding(home));
    await supervisor.request('session.submit',{...input('fresh'),lifecycle_revision:3});
    expect(await supervisor.request('session.lookup',{sessionId:'root',inputId:'fresh'})).toMatchObject({accepted:true,pending:true});
    expect(supervisor.process!.pid).toBe(pid);
    expect(await supervisor.disableAgent('b',2),logs).toMatchObject({confirmed:true});
  } catch(error) {throw new Error(String(error)+'\n'+logs,{cause:error});} finally {await supervisor.shutdown();await rm(home,{recursive:true,force:true});}
},30_000);

it('returns durable stop history for cold disabled roots after a Node restart without activating them', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-cold-stop-'));let client:RuntimeClient|undefined;
  try {
    await writeFile(join(home,'hold.mjs'), `import {appendFile} from 'node:fs/promises';export const inject=['llm'];export function apply(ctx){ctx.on('agent/created',({agent})=>{if(agent.id==='root')return appendFile(process.env.DSH_HOME+'/created','root\\n');});ctx.on('llm/stream',async function*(options){await new Promise(resolve=>{if(options.signal?.aborted)resolve();else options.signal?.addEventListener('abort',resolve,{once:true});});yield {type:'finish',reason:{kind:'stop'}};});}`);
    await prepareProfile(home,[{insert:[{id:'hold',name:join(home,'hold.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home});await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding(home)]});await client.rpc.request('session.ensure',binding(home));await client.rpc.request('session.submit',input('before-shutdown','followup'));
    await expect.poll(async()=>await client!.rpc.request('session.observe',{sessionId:'root'})).toMatchObject({status:'running'});
    await client.shutdown();
    client=new RuntimeClient({home,cwd:home});await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding(home)],lifecycle:{a:{revision:2,disabled:true,disabledThroughRevision:2}}});
    const result=await client.rpc.request('agent.disable',{agentId:'a',revision:2}) as {confirmed:boolean;history:{sessionId:string;events:{type:string}[]}[]};
    expect(result).toMatchObject({confirmed:true,history:[{sessionId:'root',events:expect.arrayContaining([expect.objectContaining({type:'turn/end'})])}]});
    expect(await readFile(join(home,'created'),'utf8')).toBe('root\n');
  } finally {if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},15000);

it('retries a slow managed job after the first cleanup deadline without restarting the host', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-cleanup-retry-'));
  const supervisor=new RuntimeSupervisor({home,cwd:home,initialize:async rpc=>{await rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding(home)]});await rpc.request('session.ensure',binding(home));},onReady:async()=>{},onError:()=>{}});
  try {
    await writeFile(join(home,'slow.mjs'), `export const inject=['jobs'];export function apply(ctx){ctx.jobs.attachController('slow');ctx.on('agent/created',({agent})=>{ctx.jobs.start({kind:'slow',label:'slow cancellation',owner:agent.id,run:()=>{let finish;const done=new Promise(resolve=>{finish=resolve;});return {done,cancel:()=>{setTimeout(()=>finish({status:'killed'}),5000);}};}});});}`);
    await prepareProfile(home,[{insert:[{id:'slow-cleanup',name:join(home,'slow.mjs')}]}]);await supervisor.start();
    const pid=supervisor.process!.pid;
    expect(await supervisor.disableAgent('a',2)).toMatchObject({confirmed:false,errorDetail:expect.stringContaining('Managed job did not settle')});
    expect(await supervisor.disableAgent('a',2)).toMatchObject({confirmed:true});
    expect(supervisor.process!.pid).toBe(pid);expect(supervisor.available).toBe(true);
  } finally {await supervisor.shutdown();await rm(home,{recursive:true,force:true});}
},15000);

it('reports unconfirmed when a managed owner cleanup throws even though Cordis disposal resolves', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-cleanup-error-'));const errors:string[]=[];
  const supervisor=new RuntimeSupervisor({home,cwd:home,initialize:async rpc=>{await rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding(home)]});await rpc.request('session.ensure',binding(home));},onReady:async()=>{},onError:error=>errors.push(String(error))});
  try {
    await writeFile(join(home,'cleanup.mjs'), `export function apply(ctx){ctx.on('agent/created',({agent})=>{agent.ctx.effect(()=>()=>{throw new Error('fixture-cleanup-failed');});});}`);
    await prepareProfile(home,[{insert:[{id:'cleanup-error',name:join(home,'cleanup.mjs')}]}]);await supervisor.start();
    expect(await supervisor.disableAgent('a',2)).toMatchObject({confirmed:false,errorDetail:expect.stringContaining('fixture-cleanup-failed')});
    expect(errors.join('')).toContain('fixture-cleanup-failed');
  } finally {await supervisor.shutdown();await rm(home,{recursive:true,force:true});}
},10000);

it('skips expired schedules before restore and stamps only new automatic inputs with the enabled revision', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-schedule-disable-'));let client:RuntimeClient|undefined;
  const scheduled={...config,toolAllowlist:['schedule_create','schedule_run']};
  const start=async(lifecycle?:unknown)=>{client=new RuntimeClient({home,cwd:home});await client.rpc.request('initialize',{protocol:1,agents:[scheduled],bindings:[binding(home)],lifecycle:lifecycle?{a:lifecycle}:undefined});await client.rpc.request('session.ensure',binding(home));};
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

it('expires only A durable owners before cold attach and preserves B work in the shared host', async () => {
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
  for (const [domain, tables] of [[model,['commands']],[fallback,['runs']],[workflow,['runs']],[knowledge,['reviews','facts']]]) {
    for (const name of tables) for (const [id, value] of [...domain.table(name).entries()]) {
      const copy=JSON.parse(JSON.stringify(value).replaceAll('old-','b-').replaceAll('"root"','"root-b"').replaceAll('"a"','"b"'));
      await domain.table(name).put(key(Buffer.from(id,'base64url').toString().replace('old-','b-')),copy);
    }
  }
  await writeFile(marker,'done');
}`);
    const seed={insert:[{id:'seed',name:join(home,'seed.mjs')}]};
    await prepareProfile(home,[{id:'nano-runtime',disabled:true},seed]);
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
    await expect.poll(()=>readFile(join(home,'seeded'),'utf8').catch(()=>logs),{timeout:5000}).toBe('done');
    client.process.kill('SIGKILL');await client.exited;
    await prepareProfile(home,[seed]);
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});await client.rpc.request('initialize',{protocol:1,agents:[config,{...config,agentId:'b'}],bindings:[binding(home),{...binding(home),agentId:'b',sessionId:'root-b'}],lifecycle:{a:{revision:3,disabledThroughRevision:2}}});
    await client.rpc.request('session.ensure',binding(home));
    expect(await client.rpc.request('session.command',{sessionId:'root',id:'old-command',action:'compact'})).toMatchObject({status:'completed',success:false});
    expect(await client.rpc.request('session.observe',{sessionId:'root'})).toMatchObject({modelRuns:[{id:'old-run',state:'completed',terminal:{kind:'cancelled',reason:'agent_disabled'}}]});
    expect(await client.rpc.request('workflow.pending',{})).toEqual([]);
    expect(await client.rpc.request('workflow.read',{sessionId:'root',runId:'old-workflow'})).toMatchObject([{state:'cancelled',cancelledByDisable:true}]);
    expect(await client.rpc.request('knowledge.facts',{})).toMatchObject({facts:[{id:'b-fact',agentId:'b'}],reviews:expect.arrayContaining([{id:'old-review',agentId:'a',rootSessionId:'root',kind:'memory',turn:0,status:'cancelled',at:1,diagnostic:'agent_disabled'}])});
    await client.rpc.request('session.ensure',{...binding(home),agentId:'b',sessionId:'root-b'});
    const bCommand=await client.rpc.request('session.command',{sessionId:'root-b',id:'b-command',action:'compact'});
    // B reaches native compaction; its empty history has no compactable range.
    expect(bCommand).toMatchObject({status:'completed',text:expect.stringContaining('no complete paired surface range')});
    expect(await client.rpc.request('session.observe',{sessionId:'root-b'})).toMatchObject({modelRuns:[{id:'b-run',state:'switching'}]});
    expect(await client.rpc.request('workflow.read',{sessionId:'root-b',runId:'b-workflow'})).toMatchObject([{state:'interrupted'}]);
  } catch(error) {throw new Error(String(error)+'\n'+logs,{cause:error});} finally {if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},20000);
