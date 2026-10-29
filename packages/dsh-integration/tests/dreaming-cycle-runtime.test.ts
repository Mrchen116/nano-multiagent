import {mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';

it('commits each successful prefix, then freezes a fresh target after a later batch fails',async()=>{
  const home=await mkdtemp(join(tmpdir(),'dreaming-cycle-'));let client:RuntimeClient|undefined;
  await writeFile(join(home,'fixture.mjs'),`
import {appendFile} from 'node:fs/promises';
export const inject=['llm'];
export function apply(ctx){
 const jobs=new Map();let failed=false;
 ctx.on('llm/stream',async function*(o){
  let call;
  if(String(o.sessionId).startsWith('dreaming-')){
   if(!jobs.has(o.sessionId)){
    jobs.set(o.sessionId,jobs.size+1);
    await appendFile(process.env.DSH_HOME+'/inputs.jsonl',JSON.stringify({id:o.sessionId,messages:o.messages})+'\\n');
   }
   if(jobs.get(o.sessionId)===2&&!failed){failed=true;throw new Error('Simulated failed batch');}
  }else{
   const last=o.messages.findLast(m=>m.role==='user'&&m.source?.actorId==='owner');const id=last?.source.messageId;
   if(id?.startsWith('maintain')&&!o.messages.some(m=>m.role==='tool'&&m.toolCallId===id))call=['memory_maintenance',{action:'run',request_ref:id},id];
  }
  if(call){yield{type:'block-end',index:0,block:{type:'tool-call',id:call[2],name:call[0],arguments:JSON.stringify(call[1])}};yield{type:'finish',reason:{kind:'tool-calls'}};}
  else{yield{type:'block-end',index:0,block:{type:'text',text:'Acknowledged temporary test material.'}};yield{type:'finish',reason:{kind:'stop'}};}
 });
}`);
  try{
    await prepareProfile(home,[{insert:[{id:'cycle-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home});
    const binding={sessionId:'root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'};
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',workspace:home,provider:'deepseek-official',model:'deepseek-flash',features:{dreaming:false},knowledge:{dreaming:{maxInputTokens:1000}},toolAllowlist:['read','write','edit','memory_maintenance'],approval:{dangerouslySkipPermissions:true}}],bindings:[binding]});
    await client.rpc.request('session.ensure',binding);
    const submit=async(id:string,text=id)=>{
      await client!.rpc.request('session.submit',{sessionId:'root',inputId:id,mode:'followup',content:[{type:'text',text}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:id}) as any).terminal,{timeout:30000}).toBeTruthy();
    };
    for(let i=0;i<7;i++)await submit(`source-${i}`,`SOURCE-${i}: temporary facts. ${'Original context stays readable. '.repeat(24)}`);
    await submit('maintain-first');
    let reviews=(await client.rpc.request('knowledge.facts',{}) as any).reviews;
    expect(reviews.map((r:any)=>r.status)).toEqual(['completed','failed']);
    await submit('arrived-later','SOURCE-LATER: arrived after the failed cycle and belongs in its fresh retry target.');
    await submit('maintain-retry');
    reviews=(await client.rpc.request('knowledge.facts',{}) as any).reviews;
    expect(reviews.slice(2).length).toBeGreaterThan(1);
    expect(reviews.slice(2).every((r:any)=>r.status==='completed')).toBe(true);
    const requests=(await readFile(join(home,'inputs.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    const material=(request:any)=>request.messages.filter((m:any)=>m.role==='user'&&m.source?.channel==='dreaming').map((m:any)=>m.content.map((b:any)=>b.text??'').join('')).join('');
    expect(material(requests[0])).toContain('SOURCE-0');
    expect(requests.slice(2).map(material).join('\n')).not.toContain('SOURCE-0');
    expect(requests.slice(2).map(material).join('\n')).toContain('SOURCE-LATER');
    expect(material(requests[1])).not.toContain('SOURCE-LATER');
  }finally{if(client)await client.shutdown();await rm(home,{recursive:true,force:true});}
},60000);
