import {mkdtemp, readFile, rm, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {setTimeout as delay} from 'node:timers/promises';
import {expect,it} from 'vitest';
import {registerNoopTaskHosts} from './helpers/noop-task-hosts.js';

it.each(['timeout','cancel'])('stops native Dreaming Bash before finishing after %s',async mode=>{
  const {prepareProfile,RuntimeClient}=await import('../lib/client.js');
  const home=await mkdtemp(join(tmpdir(),'dreaming-bash-'));let client:InstanceType<typeof RuntimeClient>|undefined;
  await writeFile(join(home,'fixture.mjs'),`
import {appendFileSync} from 'node:fs';
export const inject=['llm','agents'];
export function apply(ctx){
 ctx.on('tools/execute',async(exec,next)=>{
  if(exec.name==='bash'&&${JSON.stringify(mode)}==='cancel')setTimeout(()=>exec.agent.cancel({kind:'hook',reason:'cancel command'}),100);
  return next();
 });
 ctx.on('llm/stream',async function*(r){
  appendFileSync(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify(r)+'\\n');
  let call;
  if(r.sessionId.startsWith('dreaming-')){
   if(!r.messages.some(m=>m.toolCallId==='slow'))call=['bash',{description:'Check foreground command lifecycle under timeout',command:'sleep 2; printf late > late.md',timeoutMs:100},'slow'];
  }else{
   const input=r.messages.findLast(m=>m.source?.actorId==='owner');
   if(input?.source.messageId==='maintain'&&!r.messages.some(m=>m.toolCallId==='maintain'))call=['memory_maintenance',{action:'run',request_ref:'maintain'},'maintain'];
  }
  yield {type:'block-end',index:0,block:call?{type:'tool-call',id:call[2],name:call[0],arguments:JSON.stringify(call[1])}:{type:'text',text:'Done.'}};
  yield {type:'finish',reason:{kind:call?'tool-calls':'stop'}};
 });
}`);
  try{
    await prepareProfile(home,[{insert:[{id:'bash-lifecycle',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home});registerNoopTaskHosts(client);
    const binding={sessionId:'root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'};
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',workspace:home,revision:'1',provider:'deepseek-official',model:'deepseek-flash',features:{dreaming:false},toolAllowlist:['memory_maintenance','bash'],approval:{dangerouslySkipPermissions:true}}],bindings:[binding]});
    await client.rpc.request('session.ensure',binding);
    for(const inputId of ['experience','maintain']){
      await client.rpc.request('session.submit',{sessionId:'root',inputId,mode:'followup',content:[{type:'text',text:inputId}],source:{kind:'human',actorId:'owner',channel:'test',messageId:inputId}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId}) as any).terminal,{timeout:10000}).toBeTruthy();
    }
    const allRequests=(await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    const requests=allRequests.filter(r=>r.sessionId.startsWith('dreaming-'));
    expect(allRequests.find(r=>r.sessionId==='root').tools.find((tool:any)=>tool.name==='bash').parameters.properties).toHaveProperty('run_in_background');
    expect(requests[0].tools.find((tool:any)=>tool.name==='bash').parameters.properties).not.toHaveProperty('run_in_background');
    expect(requests[0].tools.find((tool:any)=>tool.name==='bash').parameters.properties.timeoutMs.description).toContain('kills the command');
    const reviews=(await client.rpc.request('knowledge.facts',{}) as any).reviews;
    expect(reviews).toHaveLength(1);
    expect(reviews[0].status).toBe(mode==='timeout'?'completed':'failed');
    await delay(2200);
    await expect(readFile(join(home,'.nanoassistant/memory/late.md'),'utf8')).rejects.toMatchObject({code:'ENOENT'});
  }finally{if(client)await client.shutdown();await rm(home,{recursive:true,force:true});}
},20000);
