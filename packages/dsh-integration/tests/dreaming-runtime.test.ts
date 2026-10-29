import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { expect, it } from 'vitest';

it.each([false, true])('runs empty-context manual Dreaming with real reads, staged application and a host receipt (personal=%s)', async personal => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-dreaming-runtime-')); let client: InstanceType<typeof RuntimeClient> | undefined; let logs='';
  await writeFile(join(home,'fixture.mjs'), `import {appendFileSync} from 'node:fs'; export const name='dream-fixture'; export const inject=['llm']; export function apply(ctx){const steps=new Map();ctx.on('llm/stream',async function*(o){appendFileSync(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify(o)+'\\n');const n=steps.get(o.sessionId)||0;steps.set(o.sessionId,n+1);let call;if(String(o.sessionId).startsWith('dreaming-')){const all=o.messages.map(m=>(m.content||[]).filter(b=>b.type==='text').map(b=>b.text).join('')).join('\\n');const units=[];const stage=all.match(/Editable copy: (.+?)\\. Only edit/)[1];const calls=[...units.map(u=>['read',{file_path:u.path}]),['read',{file_path:stage+'/MEMORY.md'}],['read',{file_path:stage+'/knowledge/dream.md'}],['write',{file_path:stage+'/knowledge/dream.md',content:'Verified lesson: compare actual tool outcomes with assistant claims.'}],['write',{file_path:stage+'/MEMORY.md',content:'# Expert memory\\n\\n[Verified lesson](knowledge/dream.md)'}]];call=calls[n];}else{const last=o.messages.findLast(m=>m.role==='user'&&m.source?.actorId==='owner');if(last?.content.some(b=>b.text==='maintain')&&!o.messages.some(m=>m.role==='tool'&&m.toolCallId==='manual-run'))call=['memory_maintenance',{action:'run',request_ref:'maintain'}];}if(call){yield {type:'block-end',index:0,block:{type:'tool-call',id:String(o.sessionId).startsWith('dreaming-')?'dream-'+n:'manual-run',name:call[0],arguments:JSON.stringify(call[1])}};yield {type:'finish',reason:{kind:'tool-calls'}};}else{yield {type:'block-end',index:0,block:{type:'text',text:'Experience recorded.'}};yield {type:'finish',reason:{kind:'stop'}};}});}`);
  try {
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}},{insert:[{id:'dream-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
    let refreshes=0;
    client.rpc.handle('product.call',async(value:any)=>{
      expect(value.method).toBe('memory.sources.refresh');expect(value.agentId).toBe('a');refreshes++;
      await client!.rpc.request('knowledge.sources.sync',{agentId:'a',snapshot:{revision:'1',allowed:['own'],excluded:[]}});
      return {refreshed:true};
    });
    const binding={sessionId:'dream-root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'};
    const configuration={protocol:1,agents:[{agentId:'a',workspace:home,revision:'1',mode:'global',provider:'fixture',model:'test',...(personal?{mode:'global',personal:{bindingId:'b',ownerId:'owner',conversationId:'own',epoch:1}}:{}),features:{dreaming:false},toolAllowlist:['read','write','edit','memory_maintenance'],knowledge:{dreaming:{maxInputTokens:24000}}}],bindings:[binding]};
    await client.rpc.request('initialize',configuration);
    await client.rpc.request('session.ensure',binding);
    const submit=async(id:string)=>{await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId:id,mode:'followup',content:[{type:'text',text:id==='experience'?'Long source outcome. '.repeat(300)+'END-OF-VERIFIED-SOURCE':id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId:id}) as {terminal?:unknown}).terminal,{timeout:15000}).toBeTruthy();};
    await submit('experience'); await submit('maintain');
    const facts=await client.rpc.request('knowledge.facts',{}) as {reviews:any[]};
    expect(refreshes).toBe(personal?2:0);
    expect(facts.reviews).toEqual([expect.objectContaining({kind:'dreaming',status:'completed'})]);
    expect(facts.reviews[0].summary).toContain('保存 2/2 页');
    expect(await readFile(join(home,'.nanoassistant/memory/knowledge/dream.md'),'utf8')).toContain('actual tool outcomes');
    const requests=(await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    const maintenance=requests.filter(request=>request.sessionId.startsWith('dreaming-'));
    expect(maintenance).toHaveLength(5);
    expect(JSON.stringify(maintenance)).toContain('END-OF-VERIFIED-SOURCE');
    expect(JSON.stringify(maintenance)).not.toContain('line truncated to');
    const input = maintenance[0].messages.find((message:any)=>message.source?.channel==='dreaming');
    expect(input.content.map((block:any)=>block.text).join('')).toContain('Long source outcome. '.repeat(300)+'END-OF-VERIFIED-SOURCE');
    expect(JSON.stringify(maintenance[0].messages).includes('input.md')).toBe(false);
    await expect(readFile(join(home,'.nanoassistant/maintenance/dreaming',facts.reviews[0].id,'input.md'))).rejects.toMatchObject({code:'ENOENT'});
    const names=maintenance[0].tools.map((tool:any)=>tool.name);
    expect(names).toEqual(expect.arrayContaining(['read','write','edit','source_history','notes','history','new_context','get_context_remaining']));
    expect(names).not.toContain('finish');
    expect(names).not.toEqual(expect.arrayContaining(['inbox','send_message','shell','subagents']));
    expect(JSON.stringify(maintenance[0].messages)).not.toContain('nano-skill-creation');
    expect(JSON.stringify(maintenance[0].messages)).not.toContain('user authorization');
    expect(JSON.stringify(maintenance[0].messages)).not.toContain('subagent/descriptor');
    const readTrajectory = async () => {
      const sessionId = facts.reviews[0].childSessionId;
      await client!.rpc.request('trajectory.prepare', { observerId: 'dream-view', rootAgentId: 'a', rootSessionId: binding.sessionId, sessionId, ownerId: 'owner', nodeId: 'node', nodeEpoch: 1 });
      const { streamId } = await client!.rpc.request('trajectory.open', { observerId: 'dream-view', method: 'session/follow', params: { args: { request: { maxMessages: 500 } } } }) as { streamId: string };
      const frame = await client!.rpc.request('trajectory.next', { observerId: 'dream-view', streamId }) as any;
      await client!.rpc.request('trajectory.close', { observerId: 'dream-view' });
      return frame;
    };
    const warm = await readTrajectory();
    expect(JSON.stringify(warm)).toContain('Experience recorded.');
    expect(JSON.stringify(warm)).toContain('nano-dreaming');
    expect(JSON.stringify(warm)).toContain('Host application receipt');
    // Durable viewer identity does not publish a model-manageable child.
    expect(await client.rpc.request('session.descendants', { sessionId: binding.sessionId })).toEqual([]);
    await client.shutdown();
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
    await client.rpc.request('initialize',configuration);
    const cold = await readTrajectory();
    expect(cold).toEqual(warm);
    expect(await client.rpc.request('session.descendants', { sessionId: binding.sessionId })).toEqual([]);
    await client.shutdown();client=undefined;
  }catch(error){throw new Error(`${String(error)}\n${logs}`,{cause:error});}
  finally{if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},25000);
