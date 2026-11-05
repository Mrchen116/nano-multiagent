import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it('uses visible short IDs to recover original tool text after native reset and process restart', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-short-ids-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  const fixture = `import {appendFile,readFile} from 'node:fs/promises';
export const name='short-ids-fixture';export const inject=['llm','tools'];
export function apply(ctx){
 ctx.tools.register({name:'material',description:'Read test evidence',parameters:{type:'object',properties:{}},output:{schema:{type:'object'},render:()=>[{type:'text',text:'HEAD '+ 'x'.repeat(10000)+' ORIGINAL_TAIL'}]},execute:()=>({ok:true})});
 ctx.on('agent/pre-step',async({agent},next)=>{const d=await next();ctx.get('toolResultPruner')?.pruneSession(agent.session);return d;});
 ctx.on('llm/stream',async function*(o){
  await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify(o.messages)+'\\n');
  const restore=o.messages.findLast(m=>m.content.some(b=>b.type==='text'&&b.text?.startsWith('RESTORE')));
  const recoverId=restore?.content.some(b=>b.text==='RESTORE_USER')?'recover-user':'recover';
  if(restore&&!o.messages.some(m=>m.role==='tool'&&m.toolCallId===recoverId)){
   const args=await readFile(process.env.DSH_HOME+'/target.json','utf8');
   yield{type:'block-end',index:0,block:{type:'tool-call',id:recoverId,name:'history',arguments:args}};yield{type:'finish',reason:{kind:'tool-calls'}};
  }else if(!restore&&!o.messages.some(m=>m.role==='tool')){
   yield{type:'block-end',index:0,block:{type:'tool-call',id:'material-one',name:'material',arguments:'{}'}};yield{type:'finish',reason:{kind:'tool-calls'}};
  }else{yield{type:'block-end',index:0,block:{type:'text',text:'finished'}};yield{type:'finish',reason:{kind:'stop'}};}
 });
}`;
  const config = {agentId:'a',revision:'1',workspace:home,provider:'fixture',model:'test',skillRoots:[{path:join(home,'skills'),source:'workspace'}],features:{intelligent_ui:false,task_graph:false,memory_curation:false,skill_creation:false},toolAllowlist:['material','skill']};
  const binding = {sessionId:'short-session',agentId:'a',revision:'1',ownerId:'owner',cwd:home};
  try {
    await mkdir(join(home,'.git'));
    await mkdir(join(home,'skills','fixture-skill'),{recursive:true});
    await writeFile(join(home,'skills','fixture-skill','SKILL.md'),'---\nname: fixture-skill\ndescription: Native catalog fixture\n---\nUse only for this test.');
    await writeFile(join(home,'AGENTS.md'),'NATIVE_WORKSPACE_INSTRUCTIONS');
    await writeFile(join(home,'fixture.mjs'),fixture);
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test',contextWindow:100000}]}}}},{insert:[{id:'short-ids-fixture',name:join(home,'fixture.mjs')}]}]);
    const start = async () => {
      client = new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
      registerNoopTaskHosts(client);
      await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});
      await client.rpc.request('session.ensure',binding);
    };
    const submit = async (id:string) => {
      await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId:id,mode:'followup',content:[{type:'text',text:id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});
      await expect.poll(async()=>((await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId:id})) as {terminal?:unknown}).terminal).toMatchObject({kind:'completed'});
    };
    const requests = async () => (await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line) as Array<{role:string;toolCallId?:string;source:{kind:string};content:Array<{type:string;text?:string}>}>);
    await start(); await submit('USER_REQUEST');
    const before=await requests();
    const user=before[0]!.find(m=>m.role==='user'&&m.content.some(b=>b.text==='USER_REQUEST'))!;
    expect(user.content.at(-1)!.text).toMatch(/^\n\[id: \d+\]$/);
    expect(before[0]!.some(m=>m.source.kind==='skill-catalog')).toBe(true);
    expect(before[0]!.some(m=>m.source.kind==='agent-instructions')).toBe(true);
    const userId=/\[id: (\d+)\]/.exec(user.content.at(-1)!.text!)![1]!;
    expect(userId).toBe('1');
    const tool=before[1]!.find(m=>m.role==='tool')!;
    const id=/\[id: (\d+)\]/.exec(tool.content.at(-1)!.text!)![1]!;
    expect(tool.content[0]!.text).toContain('middle pruned');
    await writeFile(join(home,'target.json'),JSON.stringify({action:'read',window_id:'short-session:initial',item_id:id,offset_chars:9950,limit_chars:200}));
    expect(await client!.rpc.request('session.command',{sessionId:binding.sessionId,id:'reset',action:'compact'})).toMatchObject({success:true});
    await client!.shutdown();client=undefined;await start();await submit('RESTORE');
    const final=(await requests()).at(-1)!;
    const restoreInput=final.find(m=>m.content.some(b=>b.text==='RESTORE'))!;
    expect(restoreInput.content.at(-1)!.text).toBe('\n[id: 1]');
    const restoredWindow=/Current context window id: ([^\n<]+)/.exec(final.flatMap(m=>m.content.map(b=>b.text??'')).join('\n'))![1]!;
    expect(restoredWindow).not.toBe('short-session:initial');
    const recovered=final.find(m=>m.toolCallId==='recover')!;
    expect(recovered.content.at(-1)!.text).toBe('\n[id: 3]');
    const body=JSON.parse(recovered.content[0]!.text!);
    expect(body).toMatchObject({item_id:id,truncated:true,next_offset_chars:10150});
    expect(body.content).toContain('ORIGINAL_TAIL');
    expect(body.content).not.toContain('[id:');
    await writeFile(join(home,'target.json'),JSON.stringify({action:'read',window_id:'short-session:initial',item_id:userId}));
    expect(await client!.rpc.request('session.command',{sessionId:binding.sessionId,id:'reset-user',action:'compact'})).toMatchObject({success:true});
    await client!.shutdown();client=undefined;await start();await submit('RESTORE_USER');
    const restoredAgain=(await requests()).at(-1)!;
    expect(restoredAgain.find(m=>m.content.some(b=>b.text==='RESTORE_USER'))!.content.at(-1)!.text).toBe('\n[id: 1]');
    const original=restoredAgain.find(m=>m.toolCallId==='recover-user')!;
    expect(JSON.parse(original.content[0]!.text!)).toMatchObject({item_id:userId,role:'user',content:'USER_REQUEST'});
    await writeFile(join(home,'target.json'),JSON.stringify({action:'read',window_id:restoredWindow,item_id:'1'}));
    await submit('RESTORE_SECOND_WINDOW');
    const secondWindowOriginal=(await requests()).at(-1)!.find(m=>m.toolCallId==='recover')!;
    expect(JSON.parse(secondWindowOriginal.content[0]!.text!)).toMatchObject({item_id:'1',window_id:restoredWindow,role:'user',content:'RESTORE'});
  } catch(error) {throw new Error(`${String(error)}\n${logs}`,{cause:error});}
  finally {if(client)await client.shutdown().catch(()=>{});await rm(home,{recursive:true,force:true});}
},30000);
