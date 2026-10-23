import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';

it('combines due maintenance in one native fork and persists its actual trajectory purpose', async () => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-combined-'));
  let client: InstanceType<typeof RuntimeClient> | undefined; let logs = '';
  const content = '---\nname: verified-method\ndescription: Reuse observed results\n---\nCheck the evidence before changing the method.';
  await writeFile(join(home, 'fixture.mjs'), `export const name='combined-fixture';export const inject=['llm'];export function apply(ctx){const steps=new Map();ctx.on('llm/stream',async function*(o){const last=o.messages.findLast(m=>m.role==='user'&&['user','nano-human'].includes(m.source?.kind));const prompt=last.content.filter(b=>b.type==='text').map(b=>b.text).join('');let name,args;const n=steps.get(last.id)||0;steps.set(last.id,n+1);if(prompt.startsWith('Review the conversation')){const calls=[['read',{file_path:${JSON.stringify(join(home,'.nanoassistant/memory/USER.md'))}}],['read',{file_path:${JSON.stringify(join(home,'.nanoassistant/memory/MEMORY.md'))}}],['memory',{action:'add',target:'user',content:'The user prefers concise answers.'}],['skill_manage',{action:'create',name:'verified-method',content:${JSON.stringify(content)}}]];if(n<calls.length)[name,args]=calls[n];}if(name){yield{type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-'+n,name,arguments:JSON.stringify(args)}};yield{type:'finish',reason:{kind:'tool-calls'}};}else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}});}`);
  const config = {agentId:'a',revision:'1',provider:'fixture',model:'test',mode:'global',features:{memory_curation:true,skill_creation:true},knowledge:{memoryInterval:1,skillInterval:1},toolAllowlist:['read','memory','skill_manage','skill']};
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
    const facts=async()=>await client!.rpc.request('knowledge.facts',{}) as {reviews:{kind:string;status:string}[];facts:{kind:string;source?:string}[]};
    await expect.poll(async()=>(await facts()).reviews.filter(r=>r.status==='completed').length,{timeout:8000}).toBeGreaterThan(0);
    expect((await facts()).reviews).toEqual([expect.objectContaining({kind:'combined',status:'completed'})]);
    expect((await facts()).facts.map(f=>f.kind).sort()).toEqual(['memory','skills']);
    expect((await facts()).facts.find(f=>f.kind==='skills')?.source).toBe('F3');
    expect(await readFile(join(home,'.nanoassistant/skills/verified-method/SKILL.md'),'utf8')).toBe(content);
    await client!.shutdown();client=undefined;await start();
    await client!.rpc.request('trajectory.prepare',{observerId:binding.sessionId,rootAgentId:'a',rootSessionId:binding.sessionId,sessionId:binding.sessionId,ownerId:'owner',nodeId:'node',nodeEpoch:1});
    const runs=await client!.rpc.request('trajectory.call',{observerId:binding.sessionId,method:'trajectory/runs'}) as {value:import('@nano/product-contracts').TrajectoryRun[]};
    expect(runs.value).toEqual([expect.objectContaining({kind:'combined',delegation:'background',provider:'fork',state:'completed'})]);
    expect(runs.value[0]!.launchSeq).toBeTypeOf('number');
    expect(runs.value[0]!.endSeq).toBeGreaterThan(runs.value[0]!.startSeq!);
  } catch(error) {throw new Error(`${error}\n${logs}`,{cause:error});}
  finally {if(client){await client.shutdown();}await rm(home,{recursive:true,force:true});}
},20000);

it('runs F4 only after two completed product sessions and binds patches to the automatic target', async () => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const { KnowledgeFiles } = await import('../src/knowledge/files.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-f4-'));
  const files = new KnowledgeFiles(home); const root = files.skillRoot;
  const content = '---\nname: verified-method\ndescription: Reuse observed results\n---\nCheck the original result.';
  await files.skill({action:'create', name:'verified-method',content},'F3');
  let client: InstanceType<typeof RuntimeClient> | undefined; let logs='';
  await writeFile(join(home,'fixture.mjs'), `export const name='f4-fixture';export const inject=['llm'];export function apply(ctx){const steps=new Map();ctx.on('llm/stream',async function*(o){const last=o.messages.findLast(m=>m.role==='user'&&['user','nano-human'].includes(m.source?.kind));const prompt=last.content.filter(b=>b.type==='text').map(b=>b.text).join('');const n=steps.get(last.id)||0;steps.set(last.id,n+1);let name,args;if(prompt.startsWith('Review only the existing automatic Skill')){const calls=[['skill_manage',{action:'patch',name:'verified-method',old_string:'original',new_string:'unread'}],['read',{file_path:${JSON.stringify(join(root,'verified-method/SKILL.md'))}}],['skill_manage',{action:'patch',name:'verified-method',old_string:'original',new_string:'verified'}]];if(n<calls.length)[name,args]=calls[n];}else if(n===0){name='skill';args={name:'verified-method'};}if(name){yield{type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-'+n,name,arguments:JSON.stringify(args)}};yield{type:'finish',reason:{kind:'tool-calls'}};}else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}});}`);
  const config={agentId:'a',revision:'1',provider:'fixture',model:'test',mode:'single_thread',features:{memory_curation:false,skill_creation:true},knowledge:{skillInterval:100000},toolAllowlist:['read','skill','skill_manage'],skillRoots:[{path:root,source:'workspace'}]};
  const bindings=['first','second'].map(sessionId=>({sessionId,agentId:'a',revision:'1',ownerId:'owner',cwd:home}));
  try {
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}},{insert:[{id:'f4-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:t=>{logs+=t;}});
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings});
    for(const binding of bindings) await client.rpc.request('session.ensure',binding);
    const use=async(sessionId:string,n:number)=>{
      const inputId=`use-${n}`;
      await client!.rpc.request('session.submit',{sessionId,inputId,mode:'followup',content:[{type:'text',text:'Use the verified method.'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:inputId}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId,inputId}) as {terminal?:unknown}).terminal).toBeTruthy();
    };
    const reviews=async()=>(await client!.rpc.request('knowledge.facts',{}) as {reviews:{status:string;source?:string;evidenceSessionIds?:string[];childSessionId?:string}[]}).reviews;
    for(let i=0;i<20;i++) await use('first',i);
    await expect.poll(async()=>({reviews:await reviews(),usage:JSON.parse(await readFile(join(root,'.usage.json'),'utf8'))}),{timeout:3000}).toMatchObject({reviews:expect.arrayContaining([expect.objectContaining({status:'skipped'})])});
    expect(await readFile(join(root,'verified-method/SKILL.md'),'utf8')).toBe(content);
    await use('second',20);
    await expect.poll(reviews,{timeout:8000}).toEqual(expect.arrayContaining([expect.objectContaining({source:'F4',status:'completed'})]));
    const completed=(await reviews()).find(r=>r.status==='completed')!;
    expect(completed.evidenceSessionIds?.sort()).toEqual(['first','second']);
    expect(await readFile(join(root,'verified-method/SKILL.md'),'utf8')).toContain('Check the verified result.');
    expect(JSON.parse(await readFile(join(root,'.curator_state.json'),'utf8')).reviewed_session_ids.sort()).toEqual(['first','second']);
    expect(JSON.parse(await readFile(join(root,'.usage.json'),'utf8'))['verified-method'].uses_since_last_B).toBe(0);
  }catch(error){throw new Error(`${error}\n${logs}`,{cause:error});}
  finally{if(client)await client.shutdown();await rm(home,{recursive:true,force:true});}
},30000);

it('keeps real writes but does not settle either interval after incomplete combined Memory reads', async () => {
  const { prepareProfile, RuntimeClient }=await import('../lib/client.js');
  const home=await mkdtemp(join(tmpdir(),'nano-incomplete-review-'));
  let client:InstanceType<typeof RuntimeClient>|undefined;let logs='';
  const user=join(home,'.nanoassistant/memory/USER.md'),memory=join(home,'.nanoassistant/memory/MEMORY.md');
  const content='---\nname: learned\ndescription: Verified steps\n---\nPreserve the observed result.';
  await writeFile(join(home,'fixture.mjs'),`export const name='incomplete-fixture';export const inject=['llm'];export function apply(ctx){let reviews=0;const steps=new Map();ctx.on('llm/stream',async function*(o){const last=o.messages.findLast(m=>m.role==='user'&&['user','nano-human'].includes(m.source?.kind));const prompt=last.content.filter(b=>b.type==='text').map(b=>b.text).join('');const n=steps.get(last.id)||0;steps.set(last.id,n+1);let name,args;if(prompt.startsWith('Review the conversation')){if(n===0)reviews++;const calls=reviews===1?[['read',{file_path:${JSON.stringify(user)}}],['skill_manage',{action:'create',name:'learned',content:${JSON.stringify(content)}}]]:[['read',{file_path:${JSON.stringify(user)}}],['read',{file_path:${JSON.stringify(memory)}}]];if(n<calls.length)[name,args]=calls[n];}if(name){yield{type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-'+n,name,arguments:JSON.stringify(args)}};yield{type:'finish',reason:{kind:'tool-calls'}};}else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}});}`);
  const config={agentId:'a',revision:'1',provider:'fixture',model:'test',mode:'global',features:{memory_curation:true,skill_creation:true},knowledge:{memoryInterval:2,skillInterval:2},toolAllowlist:['read','memory','skill_manage']};
  const binding={sessionId:'incomplete-root',agentId:'a',revision:'1',ownerId:'owner',cwd:home};
  try{
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}},{insert:[{id:'incomplete-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:t=>{logs+=t;}});
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});await client.rpc.request('session.ensure',binding);
    const submit=async(inputId:string)=>{await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId,mode:'followup',content:[{type:'text',text:inputId}],source:{kind:'human',actorId:'owner',channel:'test',messageId:inputId}});await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId})as{terminal?:unknown}).terminal).toBeTruthy();};
    const facts=async()=>await client!.rpc.request('knowledge.facts',{})as{reviews:{kind:string;status:string;diagnostic?:string}[];facts:{kind:string}[]};
    await submit('one');await submit('two');
    await expect.poll(async()=>(await facts()).reviews.filter(r=>r.status==='error')).toEqual([expect.objectContaining({kind:'combined',diagnostic:'memory_read_incomplete'})]);
    expect((await facts()).facts.map(f=>f.kind)).toEqual(['skills']);
    expect(await readFile(join(home,'.nanoassistant/skills/learned/SKILL.md'),'utf8')).toBe(content);
    await submit('three');
    await expect.poll(async()=>(await facts()).reviews.filter(r=>r.status==='completed')).toEqual([expect.objectContaining({kind:'combined'})]);
    await submit('four');expect((await facts()).reviews).toHaveLength(2);
    await client.rpc.request('trajectory.prepare',{observerId:binding.sessionId,rootAgentId:'a',rootSessionId:binding.sessionId,sessionId:binding.sessionId,ownerId:'owner',nodeId:'node',nodeEpoch:1});
    const runs=await client.rpc.request('trajectory.call',{observerId:binding.sessionId,method:'trajectory/runs'}) as {value:{kind:string;state:string}[]};
    expect(runs.value.map(r=>[r.kind,r.state])).toEqual([['combined','completed'],['combined','completed']]);
  }catch(error){throw new Error(`${error}\n${logs}`,{cause:error});}
  finally{if(client)await client.shutdown();await rm(home,{recursive:true,force:true});}
},20000);
