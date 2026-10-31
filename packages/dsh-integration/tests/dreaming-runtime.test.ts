import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { expect, it } from 'vitest';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it.each([{personal:false,automatic:false},{personal:true,automatic:false},{personal:false,automatic:true}])('runs isolated Dreaming with real reads, application and a host receipt (personal=$personal, automatic=$automatic)', async ({personal,automatic}) => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-dreaming-runtime-')); let client: InstanceType<typeof RuntimeClient> | undefined; let logs='';
  await writeFile(join(home,'fixture.mjs'), `import {appendFileSync} from 'node:fs'; export const name='dream-fixture'; export const inject=['llm']; export function apply(ctx){const steps=new Map();ctx.on('llm/stream',async function*(o){appendFileSync(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify(o)+'\\n');const n=steps.get(o.sessionId)||0;steps.set(o.sessionId,n+1);let call;if(String(o.sessionId).startsWith('dreaming-')){const all=o.messages.map(m=>(m.content||[]).filter(b=>b.type==='text').map(b=>b.text).join('')).join('\\n');const units=[];const stage=all.match(/Editable copy: (.+?)\\. Only edit/)[1];const calls=[...units.map(u=>['read',{file_path:u.path}]),['read',{file_path:stage+'/MEMORY.md'}],['read',{file_path:stage+'/knowledge/dream.md'}],['write',{file_path:stage+'/knowledge/dream.md',content:'Verified lesson: compare actual tool outcomes with assistant claims.'}],['write',{file_path:stage+'/MEMORY.md',content:'# Expert memory\\n\\n[Verified lesson](knowledge/dream.md)'}]];call=calls[n];}else{const last=o.messages.findLast(m=>m.role==='user'&&m.source?.actorId==='owner');if(last?.content.some(b=>b.text==='maintain')&&!o.messages.some(m=>m.role==='tool'&&m.toolCallId==='manual-run'))call=['memory_maintenance',{action:'run',request_ref:'maintain'}];}if(call){yield {type:'block-end',index:0,block:{type:'tool-call',id:String(o.sessionId).startsWith('dreaming-')?'dream-'+n:'manual-run',name:call[0],arguments:JSON.stringify(call[1])}};yield {type:'finish',reason:{kind:'tool-calls'}};}else{yield {type:'block-end',index:0,block:{type:'text',text:'Experience recorded.'}};yield {type:'finish',reason:{kind:'stop'}};}});}`);
  try {
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}},{insert:[{id:'dream-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
    registerNoopTaskHosts(client);
    let refreshes=0;
    client.rpc.handle('product.call',async(value:any)=>{
      expect(value.method).toBe('memory.sources.refresh');expect(value.agentId).toBe('a');refreshes++;
      await client!.rpc.request('knowledge.sources.sync',{agentId:'a',snapshot:{revision:'1',allowed:['own'],excluded:[]}});
      return {refreshed:true};
    });
    const binding={sessionId:'dream-root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'};
    const configuration={protocol:1,agents:[{agentId:'a',workspace:home,revision:'1',mode:'global',provider:'fixture',model:'test',...(personal?{mode:'global',personal:{bindingId:'b',ownerId:'owner',conversationId:'own',epoch:1}}:{}),features:{dreaming:false,intelligent_ui:false,task_graph:false,cron_scheduling:false,heartbeat:false},toolAllowlist:automatic?['read']:['read','write','edit','memory_maintenance'],knowledge:{dreaming:{maxInputTokens:24000,intervalMs:1,quietMs:0}}}],bindings:[binding]};
    await client.rpc.request('initialize',configuration);
    await client.rpc.request('session.ensure',binding);
    const submit=async(id:string)=>{await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId:id,mode:'followup',content:[{type:'text',text:id==='experience'?'Long source outcome. '.repeat(300)+'END-OF-VERIFIED-SOURCE':id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId:id}) as {terminal?:unknown}).terminal,{timeout:15000}).toBeTruthy();};
    await submit('experience');
    if(automatic){
      const root=configuration.agents[0]!;
      root.features.dreaming=true;root.revision='2';
      expect(await client.rpc.request('configuration.apply',root)).toMatchObject({effective:true});
      await expect.poll(async()=>(await client!.rpc.request('knowledge.facts',{}) as {reviews:any[]}).reviews.some(item=>item.status==='completed'),{timeout:15000}).toBe(true);
    }else await submit('maintain');
    const facts=await client.rpc.request('knowledge.facts',{}) as {reviews:any[]};
    expect(refreshes).toBe(personal?2:0);
    expect(facts.reviews).toEqual([expect.objectContaining({kind:'dreaming',status:'completed'})]);
    expect(facts.reviews[0].summary).toContain('保存 2/2 页');
    expect(await readFile(join(home,'.nanoassistant/memory/knowledge/dream.md'),'utf8')).toContain('actual tool outcomes');
    const requests=(await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    if(automatic){
      const foreground=requests.find(request=>request.sessionId===binding.sessionId);
      expect(foreground.tools.map((tool:any)=>tool.name).filter((name:string)=>['write','edit','memory_maintenance'].includes(name))).toEqual([]);
    }
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
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize',configuration);
    const cold = await readTrajectory();
    expect(cold).toEqual(warm);
    expect(await client.rpc.request('session.descendants', { sessionId: binding.sessionId })).toEqual([]);
    await client.shutdown();client=undefined;
  }catch(error){
    throw new Error(`${String(error)}\n${logs}`,{cause:error});
  }
  finally{if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},25000);

it.each([{contextWindow:256000,fixed:0,maxBatches:3},{contextWindow:1000000,fixed:0,maxBatches:1},{contextWindow:256000,fixed:120000,maxBatches:10}])('bounds the full first request with $contextWindow capacity and $fixed fixed overhead', async ({contextWindow,fixed,maxBatches}) => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'dreaming-capacity-'));
  let client: InstanceType<typeof RuntimeClient> | undefined;
  await writeFile(join(home, 'fixture.mjs'), `
import {appendFileSync} from 'node:fs';
export const inject=['llm'];
export function apply(ctx){
ctx.on('system-prompt/assemble',async(assembly,context,next)=>{
 const result=await next();
 if(String(context.scope?.id).startsWith('dreaming-'))result.tools=result.tools.map(tool=>tool.name==='read'?{...tool,description:tool.description+'固'.repeat(${fixed})}:tool);
 return result;
});
ctx.on('llm/stream',async function*(request){
  appendFileSync(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify(request)+'\\n');
  const last=request.messages.findLast(m=>m.role==='user'&&m.source?.actorId==='owner');
  if(request.sessionId==='root'&&last?.source.messageId==='maintain'&&!request.messages.some(m=>m.role==='tool'&&m.toolCallId==='run')){
    yield {type:'block-end',index:0,block:{type:'tool-call',id:'run',name:'memory_maintenance',arguments:JSON.stringify({action:'run',request_ref:'maintain'})}};
    yield {type:'finish',reason:{kind:'tool-calls'}};
  }else{
    yield {type:'block-end',index:0,block:{type:'text',text:'No durable update needed for this synthetic source.'}};
    yield {type:'finish',reason:{kind:'stop'}};
  }
});}
`);
  try {
    await prepareProfile(home, [
      {id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test',contextWindow}]}}}},
      {insert:[{id:'capacity-fixture',name:join(home,'fixture.mjs')}]},
    ]);
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'}});
    registerNoopTaskHosts(client);
    const binding={sessionId:'root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'};
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',workspace:home,revision:'1',provider:'fixture',model:'test',features:{dreaming:false},toolAllowlist:['read','write','edit','memory_maintenance']}],bindings:[binding]});
    await client.rpc.request('session.ensure',binding);
    const submit=async(id:string,text:string)=>{
      await client!.rpc.request('session.submit',{sessionId:'root',inputId:id,mode:'followup',content:[{type:'text',text}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:id}) as any).terminal,{timeout:30000}).toBeTruthy();
    };
    await submit('source','SOURCE-START\n'+'积压证据。'.repeat(60000)+'\nSOURCE-END');
    await submit('maintain','maintain');
    const facts=await client.rpc.request('knowledge.facts',{}) as any;
    expect(facts.reviews.length).toBeGreaterThan(0);
    expect(facts.reviews.every((r:any)=>r.status==='completed'),JSON.stringify(facts.reviews)).toBe(true);
    const requests=(await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    const stages=requests.filter(r=>r.sessionId.startsWith('dreaming-'));
    expect(stages.length).toBeLessThanOrEqual(maxBatches);
    const input=(r:any)=>r.messages.filter((m:any)=>m.source?.channel==='dreaming').map((m:any)=>m.content.map((b:any)=>b.text??'').join('')).join('');
    expect(Math.max(...stages.map(r=>Buffer.byteLength(input(r),'utf8')/3))).toBeGreaterThan(fixed?30000:90000);
    expect(stages.map(input).join('\n')).toContain('SOURCE-END');
    if(fixed){
      expect(stages[0].tools.find((tool:any)=>tool.name==='read').description).toContain('固'.repeat(fixed));
      expect(Math.max(...stages.map(r=>Buffer.byteLength(input(r),'utf8')/3))).toBeLessThan(60000);
    }
    for(const request of stages){
      const full=JSON.stringify({system:request.system,messages:request.messages,tools:request.tools});
      expect(Math.ceil(Buffer.byteLength(full,'utf8')/3)).toBeLessThanOrEqual(Math.floor(contextWindow*0.7));
    }
  }finally{
    if(client)await client.shutdown();
    await rm(home,{recursive:true,force:true});
  }
},60000);
