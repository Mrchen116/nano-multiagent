import {mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';

it('reuses a task extraction after consolidation fails, then replaces it after continuation; recovery tools retain source scope',async()=>{
  const home=await mkdtemp(join(tmpdir(),'dreaming-task-runtime-'));let client:RuntimeClient|undefined;let logs='';
  await writeFile(join(home,'fixture.mjs'),`
import {appendFile,writeFile} from 'node:fs/promises';
export const inject=['llm','subagents','agents'];
export function apply(ctx){
  let child;let resumed=false;let withdrawn=false;let consolidationFailed=false;const steps=new Map();
  ctx.on('agent/pre-step',async({agent,messages,signal},next)=>{
    if(agent.id==='root'){
      const last=messages.findLast(m=>m.role==='user'&&m.source?.actorId==='owner');
      const text=last?.content.find(b=>b.type==='text')?.text;
      if(text==='launch-child'&&!child){
        child=await ctx.subagents.startContinuable({provider:'fork',label:'travel-options',request:{parent:agent,prompt:[{type:'text',text:'Compare hotels using the inherited travel conditions; do not book.'}]},signal});
        await writeFile(process.env.DSH_HOME+'/child-id',child.childId);
        await ctx.agents.get(child.childId)?.whenIdle();
      }else if(text==='withdraw-child'&&!withdrawn){
        withdrawn=true;await ctx.subagents.sendMessage(agent,child.childId,[{type:'text',text:'All hotel outputs were synthetic and withdrawn. Do not retain a recommendation.'}],{signal});
        await ctx.agents.get(child.childId)?.whenIdle();
      }else if(text==='resume-child'&&!resumed){
        resumed=true;
        await ctx.subagents.sendMessage(agent,child.childId,[{type:'text',text:'The first option is unavailable. Compare another refundable option; still do not book.'}],{signal});
        await ctx.agents.get(child.childId)?.whenIdle();
      }
    }
    return next();
  });
  ctx.on('llm/stream',async function*(o){
    await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify(o)+'\\n');
    const n=steps.get(o.sessionId)||0;steps.set(o.sessionId,n+1);let call;
    const text=o.messages.flatMap(m=>m.content||[]).filter(b=>b.type==='text').map(b=>b.text).join('\\n');
    if(String(o.sessionId).startsWith('dreaming-')){
      const extraction=text.includes('Call finish with exactly two string fields');
      if(extraction){
        if(n===0)call=['finish',{rollout_summary:withdrawn?'':resumed?'Second refundable hotel compared after first became unavailable. Budget 5000, parents travel Saturday; still not booked.':'Compared refundable hotels under budget 5000 for parents travelling Saturday. Not booked.',rollout_slug:withdrawn?'':'travel-options'}];
      }else if(!consolidationFailed){consolidationFailed=true;}
      else{
        const stage=text.match(/Editable copy: (.+?)\\. Only edit/)[1];
        const directory=JSON.parse(text.match(/Source directory \\(data\\): ([^\\n]+)/)[1]);
        const root=directory.find(item=>item.purpose.startsWith('Global'));
        const calls=[['read',{file_path:stage+'/MEMORY.md'}],
          ['source_history',{action:'search',session_id:root.session_id,query:'free cancellation',limit:10}],
          ['notes',{action:'write',path:'progress.md',text:'Verified inherited cancellation condition; no booking evidence.'}],
          ['new_context',{}],['notes',{action:'read',path:'progress.md'}],
          ['source_history',{action:'search',session_id:root.session_id,query:'free cancellation',limit:10}],
          ['read',{file_path:stage+'/knowledge/travel.md'}],
          ...Array.from({length:25},()=>['source_history',{action:'search',session_id:root.session_id,query:'free cancellation',limit:10}]),
          ['write',{file_path:stage+'/knowledge/travel.md',content:resumed?'Updated option, still refundable and not booked.':'Parents Saturday, budget 5000, free cancellation; not booked.'}],
          ['write',{file_path:stage+'/MEMORY.md',content:resumed?'# Expert memory\\nUpdated [travel conditions](knowledge/travel.md).':'# Expert memory\\n[Travel conditions](knowledge/travel.md).'}],['finish',{}]];
        call=calls[n];
      }
    }else if(o.sessionId==='root'){
      const last=o.messages.findLast(m=>m.role==='user'&&m.source?.actorId==='owner');
      const id=last?.source.messageId;
      if(id?.startsWith('maintain')&&!o.messages.some(m=>m.role==='tool'&&m.toolCallId===id))call=['memory_maintenance',{action:'run',request_ref:id},id];
    }
    if(call){yield{type:'block-end',index:0,block:{type:'tool-call',id:call[2]||'step-'+n,name:call[0],arguments:JSON.stringify(call[1])}};yield{type:'finish',reason:{kind:'tool-calls'}};}
    else{yield{type:'block-end',index:0,block:{type:'text',text:o.sessionId==='root'?'Private working note.':resumed?'Second option compared; still not booked.':'Refundable options compared, not booked.'}};yield{type:'finish',reason:{kind:'stop'}};}
  });
}`);
  try{
    await prepareProfile(home,[{insert:[{id:'task-memory-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
    const binding={sessionId:'root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'};
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',workspace:home,provider:'deepseek-official',model:'deepseek-flash',features:{dreaming:false},knowledge:{dreaming:{maxSteps:24,maxRunMs:1}},toolAllowlist:['read','write','edit','memory_maintenance','subagent','subagent_fork'],approval:{dangerouslySkipPermissions:true}}],bindings:[binding]});
    await client.rpc.request('session.ensure',binding);
    const submit=async(id:string,text=id)=>{
      await client!.rpc.request('session.submit',{sessionId:'root',inputId:id,mode:'followup',content:[{type:'text',text}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:id}) as any).terminal,{timeout:20000}).toBeTruthy();
    };
    await submit('conditions','Budget 5000, parents can travel Saturday; hotel must have free cancellation. Do not book.');
    await submit('launch-child');
    await submit('after-child');
    await submit('maintain-first');
    let reviews=(await client.rpc.request('knowledge.facts',{}) as any).reviews;
    expect(reviews,JSON.stringify(reviews)).toEqual(expect.arrayContaining([expect.objectContaining({status:'completed',summary:expect.stringContaining('提炼 completed')})]));
    expect(reviews.some((review:any)=>review.status==='failed'&&review.summary?.includes('without finish'))).toBe(true);
    await submit('maintain-retry');
    const readRequests=async()=>(await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    const extractionIds=(requests:any[])=>new Set(requests.filter(r=>r.sessionId.startsWith('dreaming-')&&JSON.stringify(r.messages).includes('Call finish with exactly two string fields')).map(r=>r.sessionId));
    let requests=await readRequests();
    expect(extractionIds(requests).size).toBe(1);
    expect(await readFile(join(home,'.nanoassistant/memory/knowledge/travel.md'),'utf8')).toContain('not booked');
    const extraction=requests.find(r=>extractionIds(requests).has(r.sessionId));
    expect(JSON.stringify(extraction.messages)).toContain('Inherited background');
    expect(JSON.stringify(extraction.messages)).toContain('free cancellation');
    expect(JSON.stringify(extraction.messages)).toContain('Own experience');
    expect(extraction.tools.map((tool:any)=>tool.name)).not.toContain('write');
    const maintenance=requests.filter(r=>r.sessionId.startsWith('dreaming-')&&!extractionIds(requests).has(r.sessionId));
    expect(Math.max(...[...new Set(maintenance.map(r=>r.sessionId))].map(id=>maintenance.filter(r=>r.sessionId===id).length))).toBeGreaterThan(24);
    expect(maintenance.some(r=>r.messages.some((m:any)=>m.role==='tool'&&m.toolCallId==='step-5'&&!m.isError))).toBe(true);
    expect(maintenance.some(r=>JSON.stringify(r.messages).includes('Verified inherited cancellation condition'))).toBe(true);
    await submit('resume-child');await submit('maintain-update');
    requests=await readRequests();expect(extractionIds(requests).size).toBe(2);
    const lastExtraction=requests.findLast(r=>extractionIds(requests).has(r.sessionId));
    expect(JSON.stringify(lastExtraction.messages)).toContain('first option is unavailable');
    expect(JSON.stringify(lastExtraction.messages)).toContain('free cancellation');
    expect(await readFile(join(home,'.nanoassistant/memory/knowledge/travel.md'),'utf8')).toContain('Updated option');
    reviews=(await client.rpc.request('knowledge.facts',{}) as any).reviews;
    expect(reviews.filter((review:any)=>review.status==='completed').length).toBeGreaterThanOrEqual(4);
    await submit('withdraw-child');await submit('maintain-withdrawn');
    requests=await readRequests();expect(extractionIds(requests).size).toBe(3);
    expect(requests.some(r=>JSON.stringify(r.messages).includes('No-signal replacement; old summary retired'))).toBe(true);
    reviews=(await client.rpc.request('knowledge.facts',{}) as any).reviews;
    expect(reviews.some((review:any)=>review.status==='completed'&&review.summary?.includes('无值得保留的新信号'))).toBe(true);
  }catch(error){await writeFile('/tmp/feat676-task-debug.jsonl',await readFile(join(home,'requests.jsonl'),'utf8').catch(()=>''));if(client)await writeFile('/tmp/feat676-task-debug-facts.json',JSON.stringify(await client.rpc.request('knowledge.facts',{})));throw new Error(`${String(error)}\n${logs}`,{cause:error});}
  finally{if(client)await client.shutdown();await rm(home,{recursive:true,force:true});}
},60000);
