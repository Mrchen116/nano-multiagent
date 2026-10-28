import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';

it('keeps maintenance out of agent discovery while preserving its cold trajectory and tool evidence', async () => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-combined-'));
  let client: InstanceType<typeof RuntimeClient> | undefined; let logs = '';
  const content = '---\nname: verified-method\ndescription: Reuse observed results\n---\nCheck the evidence before changing the method.';
  await writeFile(join(home, 'fixture.mjs'), `import{appendFileSync}from'node:fs';export const name='combined-fixture';export const inject=['llm'];export function apply(ctx){const steps=new Map();ctx.on('llm/stream',async function*(o){appendFileSync(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify({sessionId:o.sessionId,messages:o.messages,tools:o.tools})+String.fromCharCode(10));const last=o.messages.findLast(m=>m.role==='user'&&['user','nano-human'].includes(m.source?.kind));const prompt=last.content.filter(b=>b.type==='text').map(b=>b.text).join('');let name,args;const n=steps.get(last.id)||0;steps.set(last.id,n+1);if(prompt==='list agents after maintenance'&&n===0){name='list_agents';args={scope:'descendants'};}if(prompt.startsWith('Review the conversation')){const calls=[['read',{file_path:${JSON.stringify(join(home,'.nanoassistant/memory-legacy/USER.md'))}}],['read',{file_path:${JSON.stringify(join(home,'.nanoassistant/memory-legacy/MEMORY.md'))}}],['memory',{action:'add',target:'user',content:'The user prefers concise answers.'}]];if(n<calls.length)[name,args]=calls[n];}if(name){yield{type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-'+n,name,arguments:JSON.stringify(args)}};yield{type:'finish',reason:{kind:'tool-calls'}};}else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}});}`);
  const config = {agentId:'a',revision:'1',provider:'fixture',model:'test',mode:'global',features:{intelligent_ui:false,task_graph:false,memory_curation:true,skill_creation:true},knowledge:{memoryMode:'legacy',legacyMemory:{enabled:true,interval:1},skillInterval:1},toolAllowlist:['read','memory','skill_manage','skill','list_agents']};
  const binding = {sessionId:'combined-root',agentId:'a',revision:'1',ownerId:'owner',cwd:home};
  try {
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}},{insert:[{id:'combined-fixture',name:join(home,'fixture.mjs')}]}]);
    const start = async () => {
      client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
      await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});
      await client.rpc.request('session.ensure',binding);
    };
    await start();
    await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId:'learn',mode:'followup',content:[{type:'text',text:'Learn the verified method and my preference.'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'learn'}});
    const facts=async()=>await client!.rpc.request('knowledge.facts',{}) as {reviews:{kind:string;status:string;turn:number;childSessionId?:string}[];facts:{kind:string;source?:string}[]};
    await expect.poll(async()=>(await facts()).reviews.filter(r=>r.status==='completed').length,{timeout:8000}).toBeGreaterThan(0);
    expect((await facts()).reviews).toEqual([expect.objectContaining({kind:'memory',status:'completed'})]);
    expect((await facts()).facts.map(f=>f.kind).sort()).toEqual(['memory']);
    const root = await client!.rpc.request('session.observe',{sessionId:binding.sessionId}) as {events:{type:string;data:any}[]};
    const childId = (await facts()).reviews[0]!.childSessionId!;
    expect(root.events.filter(event=>event.type==='subagent/catalog').map(event=>event.data.childId)).not.toContain(childId);
    expect(await client!.rpc.request('session.descendants',{sessionId:binding.sessionId})).toEqual([]);
    const requests=(await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    const main=requests.find(request=>request.sessionId===binding.sessionId);
    const maintenance=requests.filter(request=>request.sessionId===childId);
    const system=main.messages.find((message:any)=>message.role==='system');
    expect(system).toBeDefined(); expect(main.tools).toBeDefined(); expect(maintenance.length).toBeGreaterThan(0);
    for(const request of maintenance){
      expect(request.messages.find((message:any)=>message.role==='system')).toEqual(system);
      expect(request.tools).toEqual(main.tools);
    }
    // Exercise the unchanged native discovery tool after accepted work settles.
    config.knowledge.legacyMemory.enabled=false;config.features.skill_creation=false;
    await client!.rpc.request('configuration.apply',config);
    await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId:'list',mode:'followup',content:[{type:'text',text:'list agents after maintenance'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'list'}});
    await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId:'list'}) as {terminal?:unknown}).terminal).toBeTruthy();
    const listed=await client!.rpc.request('session.observe',{sessionId:binding.sessionId}) as typeof root;
    const call=listed.events.findLast(event=>event.type==='tool/call'&&event.data.name==='list_agents')!;
    expect(call).toBeDefined();
    const result=listed.events.find(event=>event.type==='tool/result'&&event.data.message.toolCallId===call.data.callId)!;
    expect(result.data.message.isError).not.toBe(true);
    expect(JSON.stringify(result.data.message.content)).toContain('(no subagents)');
    await client!.shutdown();client=undefined;await start();
    await client!.rpc.request('trajectory.prepare',{observerId:binding.sessionId,rootAgentId:'a',rootSessionId:binding.sessionId,sessionId:binding.sessionId,ownerId:'owner',nodeId:'node',nodeEpoch:1});
    const runs=await client!.rpc.request('trajectory.call',{observerId:binding.sessionId,method:'trajectory/runs'}) as {value:import('@nano/product-contracts').TrajectoryRun[]};
    expect(runs.value).toEqual([expect.objectContaining({kind:'memory',delegation:'background',provider:'fork',state:'completed'})]);
    expect(runs.value[0]!.launchSeq).toBeTypeOf('number');
    expect(runs.value[0]!.endSeq).toBeGreaterThan(runs.value[0]!.startSeq!);
    await client!.rpc.request('trajectory.prepare',{observerId:'maintenance',rootAgentId:'a',rootSessionId:binding.sessionId,sessionId:childId,ownerId:'owner',nodeId:'node',nodeEpoch:1});
    const opened=await client!.rpc.request('trajectory.open',{observerId:'maintenance',method:'session/follow',params:{args:{request:{maxMessages:50}}}}) as {streamId:string};
    const batch=await client!.rpc.request('trajectory.next',{observerId:'maintenance',streamId:opened.streamId}) as {frames:{type:string;cursor:number}[]};
    const snapshot=batch.frames.find(frame=>frame.type==='snapshot')!;
    expect(snapshot).toBeDefined();
    const page=await client!.rpc.request('trajectory.call',{observerId:'maintenance',method:'session/page',params:{args:{request:{throughSeq:snapshot.cursor,maxMessages:50}}}});
    expect(JSON.stringify(page)).toContain('Learn the verified method and my preference.');
    expect(JSON.stringify(page)).toContain('The user prefers concise answers.');
    const sessions=await client!.rpc.request('trajectory.call',{observerId:'maintenance',method:'session/list'}) as {value:{items:{agentAvailable:boolean}[]}};
    expect(sessions.value.items[0]!.agentAvailable).toBe(false);
    await client!.rpc.request('trajectory.close',{observerId:'maintenance'});
  } catch(error) {throw new Error(`${error}\n${logs}\n${JSON.stringify(await client?.rpc.request('knowledge.facts',{}).catch(()=>null))}`,{cause:error});}
  finally {if(client){await client.shutdown();}await rm(home,{recursive:true,force:true});}
},20000);
it('rejects configuration cancellation of accepted maintenance and preserves successful writes after process stop', async () => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-review-lifecycle-'));
  let client: InstanceType<typeof RuntimeClient> | undefined; let logs = '';
  const content = '---\nname: partial-method\ndescription: Preserve completed work\n---\nKeep the successful step.';
  await writeFile(join(home, 'fixture.mjs'), `import {existsSync,writeFileSync} from 'node:fs';
export const name='lifecycle-fixture';export const inject=['llm'];
export function apply(ctx){const steps=new Map();ctx.on('llm/stream',async function*(o){
 const last=o.messages.findLast(m=>m.role==='user'&&['user','nano-human'].includes(m.source?.kind));
 const prompt=last.content.filter(b=>b.type==='text').map(b=>b.text).join('');const n=steps.get(last.id)||0;steps.set(last.id,n+1);
 let name,args;
 if(prompt.startsWith('Review the conversation')&&existsSync(process.env.DSH_HOME+'/hold-combined')){
  if(n<2){name='read';args={file_path:${JSON.stringify(join(home,'.nanoassistant/memory-legacy/'))}+(n===0?'USER.md':'MEMORY.md')};}else if(n===2){name='memory';args={action:'add',target:'user',content:'Keep the successful step.'};}
  else{writeFileSync(process.env.DSH_HOME+'/write-done','done');await new Promise(resolve=>{if(o.signal.aborted)resolve();else o.signal.addEventListener('abort',resolve,{once:true});});
   name='memory';args={action:'add',target:'user',content:'after-close'};}
 }
 if(name){yield{type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-'+n,name,arguments:JSON.stringify(args)}};yield{type:'finish',reason:{kind:'tool-calls'}};}
 else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}
});}`);
  const config = {agentId:'a',revision:'1',provider:'fixture',model:'test',mode:'global',features:{intelligent_ui:false,task_graph:false,memory_curation:true,skill_creation:true},knowledge:{memoryMode:'legacy',legacyMemory:{enabled:true,interval:2},skillInterval:3},toolAllowlist:['read','memory','skill_manage','skill']};
  const binding = {sessionId:'lifecycle-root',agentId:'a',revision:'1',ownerId:'owner',cwd:home};
  try {
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}},{insert:[{id:'lifecycle-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:t=>{logs+=t;}});
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});await client.rpc.request('session.ensure',binding);
    const submit=async(inputId:string)=>{
      await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId,mode:'followup',content:[{type:'text',text:inputId}],source:{kind:'human',actorId:'owner',channel:'test',messageId:inputId}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId}) as {terminal?:unknown}).terminal).toBeTruthy();
    };
    const facts=async()=>await client!.rpc.request('knowledge.facts',{}) as {reviews:{kind:string;status:string;turn:number;childSessionId?:string}[];facts:{kind:string;name?:string}[]};
    const completed=async()=>(await facts()).reviews.filter(r=>r.status==='completed').sort((a,b)=>a.turn-b.turn).map(r=>r.kind);
    await submit('one');expect(await completed()).toEqual([]);
    await submit('two');await expect.poll(completed).toEqual(['memory']);
    await submit('three');expect(await completed()).toEqual(['memory']);
    await submit('four');await expect.poll(completed).toEqual(['memory','memory']);
    await submit('five');
    await writeFile(join(home,'hold-combined'),'hold');await submit('six');
    await expect.poll(()=>readFile(join(home,'write-done'),'utf8').catch(()=>''),{timeout:8000}).toBe('done');
    expect((await facts()).reviews.filter(r=>r.status==='running')).toEqual([expect.objectContaining({kind:'memory'})]);
    // New foreground activity must survive both the running slot and its cancellation.
    await submit('seven');
    expect(await client.rpc.request('configuration.prepare',{operationId:'close-review',fingerprint:'2',config:{...config,knowledge:{...config.knowledge,legacyMemory:{enabled:false,interval:2}},features:{intelligent_ui:false,task_graph:false,memory_curation:false,skill_creation:true}}})).toMatchObject({ready:false,blocks:expect.arrayContaining([{code:'capability_busy',target:{kind:'feature',name:'memory_curation'}}])});
    expect((await facts()).reviews.filter(r=>r.status==='running')).toHaveLength(1);
    await client.shutdown(); client=undefined;
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:t=>{logs+=t;}});
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]}); await client.rpc.request('session.ensure',binding);
    await expect.poll(async()=>(await facts()).reviews.filter(r=>r.status==='cancelled').length).toBe(1);
    expect((await facts()).facts).toEqual([expect.objectContaining({kind:'memory'})]);
    expect(await readFile(join(home,'.nanoassistant/memory-legacy/USER.md'),'utf8')).toContain('Keep the successful step.');
    expect(await readFile(join(home,'.nanoassistant/memory-legacy/USER.md'),'utf8')).not.toContain('after-close');
    await rm(join(home,'hold-combined'));
    await submit('eight');await expect.poll(completed).toEqual(['memory','memory','memory']);
    await client.rpc.request('configuration.apply',config);
    await submit('nine');expect(await completed()).toEqual(['memory','memory','memory']);
  } catch(error) {throw new Error(`${error}\n${logs}\n${JSON.stringify(await client?.rpc.request('knowledge.facts',{}).catch(()=>null))}`,{cause:error});}
  finally {if(client)await client.shutdown();await rm(home,{recursive:true,force:true});}
},30000);

it.each(['legacy','document'])('keeps F3 and F4 paused across usage thresholds, multiple roots and restart in %s mode', async (memoryMode) => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const { KnowledgeFiles } = await import('../src/knowledge/files.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-f4-'));
  const files = new KnowledgeFiles(home); const root = files.skillRoot;
  const content = '---\nname: verified-method\ndescription: Reuse observed results\n---\nCheck the original result.';
  await files.skill({action:'create', name:'verified-method',content},'F3');
  // A real discovered library contributes catalog metadata, not task evidence.
  for(let i=0;i<24;i++) await files.skill({action:'create',name:`catalog-${i}`,content:`---\nname: catalog-${i}\ndescription: ${'Catalog description. '.repeat(40)}\n---\nUnrelated reusable method.`},'F1');
  let client: InstanceType<typeof RuntimeClient> | undefined; let logs='';
  await writeFile(join(home,'fixture.mjs'), `export const name='f4-fixture';export const inject=['llm'];export function apply(ctx){const seen=new Set();ctx.on('llm/stream',async function*(o){const last=o.messages.findLast(m=>m.role==='user'&&['user','nano-human'].includes(m.source?.kind));if(!seen.has(last.id)){seen.add(last.id);yield{type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-skill',name:'skill',arguments:JSON.stringify({name:'verified-method'})}};yield{type:'finish',reason:{kind:'tool-calls'}};}else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}});}`);
  const config={agentId:'a',revision:'1',provider:'fixture',model:'test',mode:'single_thread',features:{intelligent_ui:false,task_graph:false,memory_curation:false,skill_creation:true},knowledge:{memoryMode,skillInterval:1},toolAllowlist:['read','skill','skill_manage'],skillRoots:[{path:root,source:'workspace'}]};
  const bindings=['first','second','other-owner'].map(sessionId=>({sessionId,agentId:'a',revision:'1',ownerId:sessionId==='other-owner'?'outsider':'owner',cwd:home}));
  try {
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}},{insert:[{id:'f4-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:t=>{logs+=t;}});
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings});
    for(const binding of bindings) {
      await client.rpc.request('session.ensure',binding);
      await expect.poll(async()=>((await client!.rpc.request('session.capabilities',{sessionId:binding.sessionId})) as {skills:{name:string}[]}).skills.filter(skill=>skill.name.startsWith('catalog-')).length).toBe(24);
    }
    const use=async(sessionId:string,n:number,wait=true)=>{
      const inputId=`use-${n}`;
      await client!.rpc.request('session.submit',{sessionId,inputId,mode:'followup',content:[{type:'text',text:'Use the verified method.'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:inputId}});
      if(wait) await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId,inputId}) as {terminal?:unknown}).terminal).toBeTruthy();
    };
    const reviews=async()=>(await client!.rpc.request('knowledge.facts',{}) as {reviews:{status:string;source?:string;evidenceSessionIds?:string[];childSessionId?:string}[]}).reviews;
    await use('other-owner',1000);
    await files.use(root,'verified-method','a','missing-history','missing-call',join(root,'verified-method/SKILL.md'));
    for(let i=0;i<20;i++) await use('first',i);
    await use('second',20);
    expect(await reviews()).toEqual([]);
    expect(await readFile(join(root,'verified-method/SKILL.md'),'utf8')).toBe(content);
    expect(JSON.parse(await readFile(join(root,'.usage.json'),'utf8'))['verified-method'].use_count).toBeGreaterThanOrEqual(22);
    await client.shutdown();client=undefined;
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:t=>{logs+=t;}});
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings});
    await client.rpc.request('session.ensure',bindings[0]);
    await use('first',21);
    expect(await reviews()).toEqual([]);
    expect(await readFile(join(root,'verified-method/SKILL.md'),'utf8')).toBe(content);
  }catch(error){throw new Error(`${error}\n${logs}\n${JSON.stringify(await client?.rpc.request('knowledge.facts',{}).catch(()=>null))}`,{cause:error});}
  finally{if(client)await client.shutdown();await rm(home,{recursive:true,force:true});}
},30000);

it('rejects legacy Memory writes and retains the interval after incomplete reads', async () => {
  const { prepareProfile, RuntimeClient }=await import('../lib/client.js');
  const home=await mkdtemp(join(tmpdir(),'nano-incomplete-review-'));
  let client:InstanceType<typeof RuntimeClient>|undefined;let logs='';
  const user=join(home,'.nanoassistant/memory-legacy/USER.md'),memory=join(home,'.nanoassistant/memory-legacy/MEMORY.md');
  const content='---\nname: learned\ndescription: Verified steps\n---\nPreserve the observed result.';
  await writeFile(join(home,'fixture.mjs'),`export const name='incomplete-fixture';export const inject=['llm'];export function apply(ctx){let reviews=0;const steps=new Map();ctx.on('llm/stream',async function*(o){const last=o.messages.findLast(m=>m.role==='user'&&['user','nano-human'].includes(m.source?.kind));const prompt=last.content.filter(b=>b.type==='text').map(b=>b.text).join('');const n=steps.get(last.id)||0;steps.set(last.id,n+1);let name,args;if(prompt.startsWith('Review the conversation')){if(n===0)reviews++;const calls=reviews===1?[['read',{file_path:${JSON.stringify(user)}}],['memory',{action:'add',target:'user',content:'Preserve the observed result.'}]]:[['read',{file_path:${JSON.stringify(user)}}],['read',{file_path:${JSON.stringify(memory)}}]];if(n<calls.length)[name,args]=calls[n];}if(name){yield{type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-'+n,name,arguments:JSON.stringify(args)}};yield{type:'finish',reason:{kind:'tool-calls'}};}else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}});}`);
  const config={agentId:'a',revision:'1',provider:'fixture',model:'test',mode:'global',features:{intelligent_ui:false,task_graph:false,memory_curation:true,skill_creation:true},knowledge:{memoryMode:'legacy',legacyMemory:{enabled:true,interval:2},skillInterval:2},toolAllowlist:['read','memory','skill_manage','skill']};
  const binding={sessionId:'incomplete-root',agentId:'a',revision:'1',ownerId:'owner',cwd:home};
  try{
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}},{insert:[{id:'incomplete-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:t=>{logs+=t;}});
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});await client.rpc.request('session.ensure',binding);
    const submit=async(inputId:string)=>{await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId,mode:'followup',content:[{type:'text',text:inputId}],source:{kind:'human',actorId:'owner',channel:'test',messageId:inputId}});await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId})as{terminal?:unknown}).terminal).toBeTruthy();};
    const facts=async()=>await client!.rpc.request('knowledge.facts',{})as{reviews:{kind:string;status:string;diagnostic?:string}[];facts:{kind:string}[]};
    await submit('one');await submit('two');
    await expect.poll(async()=>(await facts()).reviews.filter(r=>r.status==='error'),{timeout:8000}).toEqual([expect.objectContaining({kind:'memory',diagnostic:'memory_read_incomplete'})]);
    expect((await facts()).facts.map(f=>f.kind)).toEqual([]);
    await expect(readFile(user,'utf8')).rejects.toThrow('ENOENT');
    await submit('three');
    await expect.poll(async()=>(await facts()).reviews.filter(r=>r.status==='completed'),{timeout:8000}).toEqual([expect.objectContaining({kind:'memory'})]);
    await submit('four');expect((await facts()).reviews).toHaveLength(2);
    await client.rpc.request('trajectory.prepare',{observerId:binding.sessionId,rootAgentId:'a',rootSessionId:binding.sessionId,sessionId:binding.sessionId,ownerId:'owner',nodeId:'node',nodeEpoch:1});
    const runs=await client.rpc.request('trajectory.call',{observerId:binding.sessionId,method:'trajectory/runs'}) as {value:{kind:string;state:string}[]};
    expect(runs.value.map(r=>[r.kind,r.state])).toEqual([['memory','completed'],['memory','completed']]);
  }catch(error){throw new Error(`${error}\n${logs}\n${JSON.stringify(await client?.rpc.request('knowledge.facts',{}).catch(()=>null))}`,{cause:error});}
  finally{if(client)await client.shutdown();await rm(home,{recursive:true,force:true});}
},20000);
