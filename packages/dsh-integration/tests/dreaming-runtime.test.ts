import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { expect, it } from 'vitest';

it('runs empty-context manual Dreaming with real reads, staged application and a host receipt', async () => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-dreaming-runtime-')); let client: InstanceType<typeof RuntimeClient> | undefined; let logs='';
  await writeFile(join(home,'fixture.mjs'), `import {appendFileSync} from 'node:fs'; export const name='dream-fixture'; export const inject=['llm']; export function apply(ctx){const steps=new Map();ctx.on('llm/stream',async function*(o){appendFileSync(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify(o)+'\\n');const n=steps.get(o.sessionId)||0;steps.set(o.sessionId,n+1);let call;if(String(o.sessionId).startsWith('dreaming-')){const all=o.messages.map(m=>(m.content||[]).filter(b=>b.type==='text').map(b=>b.text).join('')).join('\\n');const units=JSON.parse(all.match(/File list \\(data\\):\\n([^\\n]+)/)[1]);const stage=all.match(/Editable copy: (.+?)\\. Only edit/)[1];const calls=[...units.map(u=>['read',{file_path:u.path}]),['read',{file_path:stage+'/MEMORY.md'}],['read',{file_path:stage+'/knowledge/dream.md'}],['write',{file_path:stage+'/knowledge/dream.md',content:'Verified lesson: compare actual tool outcomes with assistant claims.'}],['write',{file_path:stage+'/MEMORY.md',content:'# Expert memory\\n\\n[Verified lesson](knowledge/dream.md)'}],['finish',{units:units.map(u=>({id:u.id,outcome:'reviewed',outputs:['knowledge/dream.md','MEMORY.md']}))}]];call=calls[n];}else{const last=o.messages.findLast(m=>m.role==='user'&&m.source?.actorId==='owner');if(last?.content.some(b=>b.text==='maintain')&&!o.messages.some(m=>m.role==='tool'&&m.toolCallId==='manual-run'))call=['memory_maintenance',{action:'run',request_ref:'maintain'}];}if(call){yield {type:'block-end',index:0,block:{type:'tool-call',id:String(o.sessionId).startsWith('dreaming-')?'dream-'+n:'manual-run',name:call[0],arguments:JSON.stringify(call[1])}};yield {type:'finish',reason:{kind:'tool-calls'}};}else{yield {type:'block-end',index:0,block:{type:'text',text:'Experience recorded.'}};yield {type:'finish',reason:{kind:'stop'}};}});}`);
  try {
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}},{insert:[{id:'dream-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
    const binding={sessionId:'dream-root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'};
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',workspace:home,revision:'1',provider:'fixture',model:'test',features:{dreaming:false},toolAllowlist:['read','write','edit','memory_maintenance'],knowledge:{dreaming:{maxSteps:24,maxRunMs:10000}}}],bindings:[binding]});
    await client.rpc.request('session.ensure',binding);
    const submit=async(id:string)=>{await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId:id,mode:'followup',content:[{type:'text',text:id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId:id}) as {terminal?:unknown}).terminal,{timeout:15000}).toBeTruthy();};
    await submit('experience'); await submit('maintain');
    const facts=await client.rpc.request('knowledge.facts',{}) as {reviews:any[]};
    expect(facts.reviews).toEqual([expect.objectContaining({kind:'dreaming',status:'completed'})]);
    expect(facts.reviews[0].summary).toContain('保存 2/2 页');
    expect(await readFile(join(home,'.nanoassistant/memory/knowledge/dream.md'),'utf8')).toContain('actual tool outcomes');
    const requests=(await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    const maintenance=requests.filter(request=>request.sessionId.startsWith('dreaming-'));
    expect(maintenance.length).toBeGreaterThan(1);
    expect(maintenance[0].tools.map((tool:any)=>tool.name).sort()).toEqual(['edit','finish','glob','grep','read','write']);
    expect(JSON.stringify(maintenance[0].messages)).not.toContain('nano-skill-creation');
    expect(JSON.stringify(maintenance[0].messages)).not.toContain('user authorization');
    await client.shutdown();client=undefined;
  }catch(error){throw new Error(`${String(error)}\n${logs}`,{cause:error});}
  finally{if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},25000);
