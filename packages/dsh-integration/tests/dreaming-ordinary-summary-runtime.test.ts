import {mkdir,mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';
import {registerNoopTaskHosts} from './helpers/noop-task-hosts.js';


it.each(['document','legacy'])('isolates %s memory from the Global work worker',async mode=>{
  const home=await mkdtemp(join(tmpdir(),'dreaming-ordinary-summary-'));
  let client:RuntimeClient|undefined;
  const conditions='Budget 5000, parents can travel Saturday; hotel must have free cancellation. Do not book.';
  const delegated=`Compare the hotel options in hotel-options.md. The owner said: "${conditions}" Return the comparison; do not book.`;
  try{
    const skillRoot=join(home,'skills');
    await mkdir(join(skillRoot,'nano-memory'),{recursive:true});
    await writeFile(join(skillRoot,'nano-memory','SKILL.md'),'---\nname: nano-memory\ndescription: MEMORY_SKILL_SENTINEL\n---\nInternal memory guide.');
    if(mode==='legacy'){
      await mkdir(join(home,'.nanoassistant','memory-legacy'),{recursive:true});
      await writeFile(join(home,'.nanoassistant','memory-legacy','MEMORY.md'),'LEGACY_MEMORY_SENTINEL');
    }
    await writeFile(join(home,'hotel-options.md'),'# Synthetic hotel options\nOption A: 4200 total, refundable until Friday. Option B: 4700 total, non-refundable. No reservation has been made.\n');
    await writeFile(join(home,'fixture.mjs'),`
import {appendFile,writeFile} from 'node:fs/promises';
export const inject=['llm','agents'];
export function apply(ctx){
  const steps=new Map();
  ctx.on('llm/stream',async function*(o){
    const agent=ctx.agents.get(o.sessionId);
    const descriptor=agent.session.snapshotEvents().find(e=>e.type==='subagent/descriptor');
    await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify({...o,sourceAgent:{parent:agent.session.header.parentSession,provider:descriptor?.data.provider}})+'\\n');
    const n=steps.get(o.sessionId)||0;steps.set(o.sessionId,n+1);
    const text=o.messages.flatMap(m=>m.content||[]).filter(b=>b.type==='text').map(b=>b.text).join('\\n');
    let call,output='Private working note.';
    if(String(o.sessionId).startsWith('dreaming-')){
      if(text.includes('Return a JSON object with exactly two string fields'))output=JSON.stringify({rollout_summary:'The parent relayed a budget of 5000 and a requirement for refundable hotels for Saturday. Read the supplied options: A costs 4200 and is refundable until Friday; B costs 4700 and is non-refundable. Compared options; no booking was made.',rollout_slug:'hotel-comparison'});
      else output='No additional memory changes in this capture.';
    }else if(o.sessionId==='root'){
      const last=o.messages.findLast(m=>m.role==='user'&&m.source?.actorId==='owner');
      const id=last?.source.messageId;
      if(id==='launch-child'&&!o.messages.some(m=>m.role==='tool'&&m.toolCallId==='delegate'))call=['delegate_worker',{action:'start',message:${JSON.stringify(delegated)},label:'Compare refundable hotel options'},'delegate'];
      if(id==='maintain'&&!o.messages.some(m=>m.role==='tool'&&m.toolCallId==='maintain'))call=['memory_maintenance',{action:'run',request_ref:'maintain'},'maintain'];
    }else if(n===0)call=['read',{file_path:process.env.DSH_HOME+'/hotel-options.md'},'read-options'];
    else if(n===1)call=['send_message',{agent:'lead',message:'Option A fits the relayed budget and refund requirement; Option B does not. No booking was made.'},'report-options'];
    else {await writeFile(process.env.DSH_HOME+'/child-reported','done'); output='Option A fits the relayed budget and refund requirement; Option B does not. No booking was made.';}
    if(call){yield{type:'block-end',index:0,block:{type:'tool-call',id:call[2],name:call[0],arguments:JSON.stringify(call[1])}};yield{type:'finish',reason:{kind:'tool-calls'}};}
    else{yield{type:'block-end',index:0,block:{type:'text',text:output}};yield{type:'finish',reason:{kind:'stop'}};}
  });
}`);
    await prepareProfile(home,[{insert:[{id:'ordinary-summary-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home});registerNoopTaskHosts(client);
    const binding={sessionId:'root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'};
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',features:{dreaming:false},knowledge:{memoryMode:mode},skillRoots:[{path:skillRoot,source:'builtin'}],toolAllowlist:['read','write','edit','memory','memory_maintenance','skill','delegate_worker'],approval:{dangerouslySkipPermissions:true}}],bindings:[binding]});
    await client.rpc.request('session.ensure',binding);
    const submit=async(id:string,text=id)=>{
      await client!.rpc.request('session.submit',{sessionId:'root',inputId:id,mode:'followup',content:[{type:'text',text}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:id}) as any).terminal,{timeout:20000}).toBeTruthy();
    };
    await submit('conditions',conditions+' ROOT_ONLY_CONTEXT_SENTINEL: unrelated private root context.');
    await submit('launch-child');
    await expect.poll(()=>readFile(join(home,'child-reported'),'utf8').catch(()=>''),{timeout:20000}).toBe('done');
    await submit('after-child');if(mode==='document')await submit('maintain');
    const requests=(await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    const root=requests.find(r=>r.sessionId==='root');
    expect(root.tools.map((tool:any)=>tool.name)).toContain('delegate_worker');
    expect(root.tools.map((tool:any)=>tool.name)).not.toContain('subagent_fork');
    const child=requests.find(r=>r.sourceAgent.parent==='root'&&!String(r.sessionId).startsWith('dreaming-'));
    expect(child.sourceAgent.provider).toBe('spawn');
    const report=requests.filter(r=>r.sessionId===child.sessionId).flatMap(r=>r.messages).find((m:any)=>m.role==='tool'&&m.toolCallId==='report-options');
    expect(report).toMatchObject({isError:false});
    expect(JSON.stringify(child.messages)).toContain(delegated.replaceAll('"','\\"'));
    expect(JSON.stringify(child.messages)).not.toContain('ROOT_ONLY_CONTEXT_SENTINEL');
    const extraction=requests.find(r=>String(r.sessionId).startsWith('dreaming-')&&JSON.stringify(r.messages).includes('Return a JSON object with exactly two string fields'));
    expect(extraction).toBeUndefined();
    expect(JSON.stringify(child.messages)).not.toContain('Memory directory:');
    expect(child.tools.map((tool:any)=>tool.name)).not.toContain('memory_maintenance');
    expect(child.tools.map((tool:any)=>tool.name)).not.toContain('memory');
    expect(JSON.stringify(child)).not.toContain('MEMORY_SKILL_SENTINEL');
    expect(JSON.stringify(root)).toContain('MEMORY_SKILL_SENTINEL');
    if(mode==='legacy'){
      expect(JSON.stringify(root)).toContain('LEGACY_MEMORY_SENTINEL');
      expect(JSON.stringify(child)).not.toContain('LEGACY_MEMORY_SENTINEL');
      return;
    }
    const consolidation=requests.find(r=>String(r.sessionId).startsWith('dreaming-'));
    expect(consolidation).toBeDefined();
    const reviews=(await client.rpc.request('knowledge.facts',{}) as any).reviews;
    expect(reviews.length).toBeGreaterThan(0);
    await client.rpc.request('trajectory.prepare',{observerId:'maintenance',rootAgentId:'a',rootSessionId:'root',sessionId:'root',ownerId:'owner',nodeId:'node',nodeEpoch:1});
    const runs=await client.rpc.request('trajectory.call',{observerId:'maintenance',method:'trajectory/runs'}) as {value:import('@nano/product-contracts').TrajectoryRun[]};
    expect(runs.value.filter(run=>run.kind==='dreaming')).toEqual(expect.arrayContaining(reviews.map((review:any)=>
      expect.objectContaining({sessionId:review.childSessionId,label:review.title,state:review.status}))));
    await client.rpc.request('trajectory.close',{observerId:'maintenance'});
    expect(JSON.stringify(consolidation.messages)).toContain('Option A fits the relayed budget');
    expect(JSON.stringify(consolidation.messages)).not.toContain('4200 total, refundable until Friday');
  }finally{if(client)await client.shutdown();await rm(home,{recursive:true,force:true});}
},60000);
