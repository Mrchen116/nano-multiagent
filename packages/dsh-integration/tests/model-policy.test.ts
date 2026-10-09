import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

it('keeps session effort, compacts with focus once and restores selected Skill instructions after native compaction', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-model-policy-')); let client: RuntimeClient | undefined; let logs='';
  await writeFile(join(home, 'fixture.mjs'), `import {appendFile}from'node:fs/promises';export const name='model-fixture';export const inject=['llm'];export function apply(ctx){ctx.on('llm/stream',async function*(o){await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify({purpose:o.purpose,effort:o.reasoningEffort,messages:o.messages,system:o.system})+'\\n');yield{type:'block-end',index:0,block:{type:'text',text:o.purpose==='compaction'?'Preserve AUTH_FOCUS and continue the original task.':'A useful response. '.repeat(100)}};yield{type:'finish',reason:{kind:'stop'},usage:{inputTokens:100,outputTokens:20}};});}`);
  await mkdir(join(home,'skills/retained'),{recursive:true});
  await writeFile(join(home,'skills/retained/SKILL.md'),'---\nname: retained\ndescription: Guidance that must survive compaction\n---\nKEEP_SELECTED_SKILL_BODY');
  const config={agentId:'a',revision:'1',provider:'fixture',model:'test',features:{memory_curation:false,skill_creation:false},toolAllowlist:[],skillRoots:[{path:join(home,'skills'),source:'workspace'}],reasoningEffort:'low'};
  const binding={sessionId:'model-session',agentId:'a',revision:'1',ownerId:'owner',cwd:home};
  try {
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test',contextWindow:100000,reasoningEfforts:{low:'low',high:'high'}}]}}}},{id:'nano-compaction',config:{retainTokens:0,headroomTokens:100,maxTokens:256}},{insert:[{id:'model-fixture',name:join(home,'fixture.mjs')}]}]);
    const start=async()=>{client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});await client.rpc.request('session.ensure',binding);};
    await start();
    const submit=async(id:string)=>{await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId:id,mode:'followup',content:[{type:'text',text:(id==='one'?'/skill:retained\n':'')+'Retain my authentication strategy. '.repeat(100)}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId:id})as{terminal?:unknown}).terminal).toBeTruthy();};
    await submit('one');await submit('two');
    const command={sessionId:binding.sessionId,id:'compact-once',action:'compact',argument:'AUTH_FOCUS'};
    const result=await client!.rpc.request('session.command',command);expect(result,JSON.stringify(result)).toMatchObject({success:true});
    expect(await client!.rpc.request('session.command',command)).toEqual(result);
    const events=async()=>(await client!.rpc.request('session.observe',{sessionId:binding.sessionId})as{events:{type:string;data:Record<string,unknown>}[]}).events;
    expect((await events()).filter(e=>e.type==='compaction/summary')).toHaveLength(1);
    expect(await client!.rpc.request('session.command',{sessionId:binding.sessionId,id:'effort',action:'effort',argument:'high'})).toMatchObject({success:true});
    await submit('three');await client!.shutdown();client=undefined;await start();
    expect(await client!.rpc.request('session.command',command)).toEqual(result);
    config.revision='2';await client!.rpc.request('configuration.apply',config);await submit('four');
    const requests=(await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    expect(requests.filter(r=>r.purpose==='compaction')).toHaveLength(1);
    expect(JSON.stringify(requests.find(r=>r.purpose==='compaction').messages)).toContain('For this summarization only');
    expect(requests.at(-1).effort).toBe('high');
    expect(JSON.stringify(requests.at(-1))).toContain('Previously used Skills, restored after compaction');
    expect(JSON.stringify(requests.at(-1))).toContain('KEEP_SELECTED_SKILL_BODY');
    expect((await events()).filter(e=>e.type==='user/message').some(e=>JSON.stringify(e.data).includes('For this summarization only'))).toBe(false);
    await client!.shutdown();client=undefined;
  }catch(error){throw new Error(`${String(error)}\n${logs}`,{cause:error});}
  finally{if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},20000);
