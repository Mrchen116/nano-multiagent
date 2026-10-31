import {expect,it} from 'vitest';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {Context} from '@deepseek-ai/cordis';
import {LocalFileSystem} from '@deepseek-ai/dsh-fs-local';
import {MemoryDocuments} from '../src/knowledge/memory-documents.js';
import {RuntimeClient,prepareProfile} from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it('refreshes the same native child after host-applied correction and pending/revoked source authority',async()=>{
  const home=await mkdtemp(join(tmpdir(),'memory-child-refresh-'));let client:RuntimeClient|undefined;let logs='';
  const library=await MemoryDocuments.open(home,'expert',new LocalFileSystem(new Context(),{cwd:home,diffBasisMaxBytes:10485760}));
  await library.apply({operationId:'entry',path:'MEMORY.md',beforeHash:(await library.versions())['MEMORY.md']!,content:'# Expert memory\nOLD PERMISSION: public updates permitted.'});
  await library.checkpoint(await library.versions(),0);await library.close();
  await writeFile(join(home,'fixture.mjs'),`import {appendFile,readFile,writeFile} from 'node:fs/promises';
export const name='child-memory-fixture';export const inject=['llm','subagents'];
export function apply(ctx){let launched=false;const steps=new Map();
ctx.on('agent/pre-step',async({agent,signal},next)=>{if(agent.id==='root'&&agent.session.deriveMessages().length&&!launched){launched=true;const child=await ctx.subagents.start('fork',{parent:agent,signal,label:'original-worker',prompt:[{type:'text',text:'Continue the existing work using current memory.'}]});try{await child.result;}finally{await child.dispose();}}return next();});
ctx.on('llm/stream',async function*(o){const child=o.sessionId!=='root';const n=steps.get(o.sessionId)||0;steps.set(o.sessionId,n+1);await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify(o)+'\\n');
if(child&&n<2){await writeFile(process.env.DSH_HOME+'/waiting-'+n,'ready');while(true){try{await readFile(process.env.DSH_HOME+'/release-'+n);break;}catch{}await new Promise(r=>setTimeout(r,20));}yield{type:'block-end',index:0,block:{type:'tool-call',id:'read-'+n,name:'read',arguments:JSON.stringify({file_path:process.env.DSH_HOME+'/.nanoassistant/memory/MEMORY.md'})}};yield{type:'finish',reason:{kind:'tool-calls'}};}else if(child&&n===2){yield{type:'block-end',index:0,block:{type:'tool-call',id:'child-write',name:'write',arguments:JSON.stringify({file_path:process.env.DSH_HOME+'/.nanoassistant/memory/MEMORY.md',content:'Forbidden child overwrite'})}};yield{type:'finish',reason:{kind:'tool-calls'}};}else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}});}`);
  try{
    await prepareProfile(home,[{insert:[{id:'child-memory-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,onLog:s=>{logs+=s;}});
    registerNoopTaskHosts(client);
    const binding={sessionId:'root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'};
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',workspace:home,revision:'1',provider:'deepseek-official',model:'deepseek-flash',features:{dreaming:false},toolAllowlist:['read','write','subagent']}],bindings:[]});
    await client.rpc.request('session.ensure',binding);
    await client.rpc.request('session.submit',{sessionId:'root',inputId:'seed',mode:'followup',content:[{type:'text',text:'Prepare for work'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'seed'}});
    await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:'seed'}) as any).terminal,{timeout:10000}).toBeTruthy();
    await client.rpc.request('session.submit',{sessionId:'root',inputId:'work',mode:'followup',content:[{type:'text',text:'Continue work through one child'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'work'}});
    await expect.poll(()=>readFile(join(home,'waiting-0'),'utf8').catch(()=>''),{timeout:10000}).toBe('ready');
    await writeFile(join(home,'.nanoassistant/memory/MEMORY.md'),'# Expert memory\nCURRENT: private only.');
    await client.rpc.request('knowledge.sources.pending',{agentId:'a'});
    await writeFile(join(home,'release-0'),'go');
    await expect.poll(()=>readFile(join(home,'waiting-1'),'utf8').catch(()=>''),{timeout:10000}).toBe('ready');
    await client.rpc.request('knowledge.sources.sync',{agentId:'a',snapshot:{revision:'2',allowed:[],excluded:['room']}});
    await writeFile(join(home,'release-1'),'go');
    await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:'work'}) as any).terminal,{timeout:10000}).toBeTruthy();
    const requests=(await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    const child=requests.filter(request=>request.sessionId!=='root');
    expect(new Set(child.map(request=>request.sessionId)).size).toBe(1);expect(child).toHaveLength(4);
    expect(JSON.stringify(child[0].messages)).toContain('OLD PERMISSION');
    expect(JSON.stringify(child[1])).toContain('source_eligibility_pending');
    expect(JSON.stringify(child[1])).toContain('CURRENT: private only.');
    expect(JSON.stringify(child[2])).toContain('entry_basis_stale');
    expect(JSON.stringify(child[2])).toContain('Source generation: 1');
    expect(await readFile(join(home,'.nanoassistant/memory/MEMORY.md'),'utf8')).toBe('# Expert memory\nCURRENT: private only.');
    expect(JSON.stringify(child[3])).toContain('Only Dreaming');
    const currentSystem=child[2].messages.filter((message:any)=>message.role==='system');
    expect(JSON.stringify(currentSystem)).not.toContain('<memory_content>');
  }catch(error){throw new Error(String(error)+'\n'+logs,{cause:error});}
  finally{if(client){await client.shutdown();}await rm(home,{recursive:true,force:true});}
},35000);
