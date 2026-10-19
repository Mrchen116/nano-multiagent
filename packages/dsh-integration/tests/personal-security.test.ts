import { mkdtemp, mkdir, readFile, realpath, writeFile, symlink, rm } from 'node:fs/promises';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { personalFilePath, assertPersonalConfiguration, reviewPersonal } from '../lib/personal-security.js';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

it('supplies server owner scopes and choices to ordinary approval without bypassing its denial',async()=>{
 const home=await mkdtemp(join(tmpdir(),'pa-owner-approval-'));let client:RuntimeClient|undefined;
 try {
  await writeFile(join(home,'fixture.mjs'),`import{writeFile}from'node:fs/promises';
export const name='pa-owner-approval';export const inject=['tools','llm'];export function apply(ctx){
ctx.on('llm/stream',async function*(o){const prompt=o.messages[0].content[0].text;const allow=prompt.includes('SERVER_OWNER_CHOICE')&&!prompt.includes('FORBIDDEN_DISCLOSURE');yield{type:'block-end',index:0,block:{type:'text',text:allow?'<block>no</block>':'<block>yes</block><reason>Not authorized</reason>'}};yield{type:'finish',reason:{kind:'stop'}};});
ctx.on('agent/created',({agent})=>{if(agent.id!=='root')return;setTimeout(async()=>{const results=[];for(const text of ['Chosen reservation','FORBIDDEN_DISCLOSURE'])results.push(await ctx.tools.execute({name:'send_message',callId:'send-'+results.length,arguments:{target:'peer',text},agent,signal:new AbortController().signal}));await writeFile(process.env.DSH_HOME+'/results.json',JSON.stringify(results));},0);});}`);
  await prepareProfile(home,[{insert:[{id:'pa-owner-approval',name:join(home,'fixture.mjs')}]}]);
  client=new RuntimeClient({home,cwd:home});
  const sent:string[]=[];let authorityReads=0;
  client.rpc.handle('product.call',value=>{const call=value as any;
   if(call.method==='send_message.context')return {target:'peer',sender:{type:'agent',agent_id:'pa'},recipient:{kind:'user'},channel:'web'};
   if(call.method==='pa.authorization'){authorityReads++;return {scopes:[{task_ref:'goal',revoked:0,scope:{allowed_action_kinds:['message'],allowed_conversation_ids:['peer']}}],assistance:[{task_ref:'goal',paused:false}],owner_decisions:[{status:'resolved',owner_resolution:{option:'SERVER_OWNER_CHOICE'}}]};}
   if(call.method==='send_message'){sent.push(call.args.text);return {status:'sent',message_id:'actual'};}
   throw Error('Unexpected product call '+call.method);
  });
  const config={agentId:'pa',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',personal:{bindingId:'binding',ownerId:'owner',conversationId:'dm',epoch:1},approval:{...approvalDefaults,globalRoot:home}};
  await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
  await client.rpc.request('session.ensure',{sessionId:'root',agentId:'pa',ownerId:'owner',revision:'1',cwd:home});
  await expect.poll(async()=>readFile(join(home,'results.json'),'utf8').catch(()=>''),{timeout:10000}).not.toBe('');
  const results=JSON.parse(await readFile(join(home,'results.json'),'utf8'));
  expect(sent).toEqual(['Chosen reservation']);expect(results[1].isError).toBe(true);expect(JSON.stringify(results[1])).toContain('Not authorized');expect(authorityReads).toBeGreaterThan(0);
 }finally{if(client)await client.shutdown();await rm(home,{recursive:true,force:true});}
},20000);

it('keeps private document paths out of control files and symlink escapes',async()=>{
  const home=await mkdtemp(join(tmpdir(),'pa-files-'));
  try{
    await mkdir(join(home,'workspace'));await writeFile(join(home,'secret'),'private');await symlink(home,join(home,'workspace','escape'));
    await expect(personalFilePath(join(home,'workspace'),'escape/secret')).rejects.toThrow('symbolic');
    await expect(personalFilePath(join(home,'workspace'),'../secret')).rejects.toThrow('outside');
    await expect(personalFilePath(join(home,'workspace'),'.nanoassistant/config.yaml',true)).rejects.toThrow('outside');
    await expect(personalFilePath(join(home,'workspace'),'AGENTS.md',true)).rejects.toThrow('outside');
    expect(await personalFilePath(join(home,'workspace'),'drafts/plan.md',true)).toBe(join(await realpath(home),'workspace','drafts/plan.md'));
  }finally{await rm(home,{recursive:true,force:true});}
});

it('enforces the personal gate in actual DSH dispatch despite skip permissions and never imports rejected plugins',async()=>{
  const home=await mkdtemp(join(tmpdir(),'pa-native-security-'));let client:RuntimeClient|undefined;let logs='';
  const requests:string[]=[];
  const server=createServer((request,response)=>{requests.push(request.url!);response.setHeader('content-type','application/json');response.end(JSON.stringify({results:[{url:'https://example.com',title:'Public result',content:'Useful',score:1}]}));});
  await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));
  const env={SEARXNG_URL:`http://127.0.0.1:${(server.address() as {port:number}).port}`,DSH_WEB_SEARCH_PROVIDER:'searxng'};
  const workspace=join(home,'workspace');await mkdir(workspace);
  const personal={bindingId:'binding',ownerId:'owner',conversationId:'dm',epoch:1};
  const config={agentId:'pa',revision:'1',workspace,personal,mode:'global' as const,provider:'deepseek-official',model:'deepseek-flash',
    features:{memory_curation:true,skill_creation:false},approval:{...approvalDefaults,dangerouslySkipPermissions:true,globalRoot:home}};
  try{
    await writeFile(join(home,'forbidden.mjs'),`import {writeFileSync} from 'node:fs';writeFileSync(${JSON.stringify(join(home,'imported'))},'bad');export function apply(){}`);
    await writeFile(join(home,'plugins.json'),JSON.stringify([{module:'./forbidden.mjs'}]));
    await writeFile(join(home,'fixture.mjs'),`import{writeFile}from'node:fs/promises';
export const name='pa-fixture';export const inject=['tools','llm'];export function apply(ctx){
ctx.on('llm/stream',async function*(o){if(o.system?.includes('independently review')){if(o.tools?.length||o.sessionId)throw new Error('Reviewer got executable context');yield{type:'block-end',index:0,block:{type:'text',text:JSON.stringify({decision:'deny',reason:'private detail'})}};yield{type:'finish',reason:{kind:'stop'}};return;}yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};});
ctx.on('agent/created',({agent})=>{if(agent.id!=='root')return;setTimeout(async()=>{const results=[];for(const [name,args]of [
['web_search',{queries:['PRIVATE_CANARY']}],['send_message',{target:'peer',text:'PRIVATE_CANARY'}],['send_message',{target:'owner',text:'Prepared'}],
['bash',{command:'touch '+${JSON.stringify(join(home,'executed'))}}],['run_code',{code:'return 1'}],
['personal_files',{action:'write',path:'draft.md',content:'private draft'}],['memory',{action:'add',target:'memory',content:'Observed a supplier claim'}],['web_search',{queries:['public topic']}]
])results.push({name,result:await ctx.tools.execute({name,callId:'probe-'+results.length,arguments:args,agent,signal:new AbortController().signal})});await writeFile(process.env.DSH_HOME+'/results.json',JSON.stringify(results));},0);});}`);
    await prepareProfile(home,[{insert:[{id:'pa-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,env,onLog:text=>{logs+=text;}});
    const calls:any[]=[]; const delivered:any[]=[];
    client.rpc.handle('product.call',value=>{const call=value as any;calls.push(call);if(call.method==='pa.action.guard')return {decision:call.args.args?.text==='PRIVATE_CANARY'||call.args.args?.queries?.includes('PRIVATE_CANARY')?'deny':'allow',reason:'fixture privacy policy',...(call.args.args?.network?{permit:{proposal_ref:'host-permit',requestKey:call.args.args.network.requestKey,requestDigest:call.args.args.network.requestDigest}}:{})};if(call.method==='send_message'){if(call.args.text==='PRIVATE_CANARY')return {status:'denied'};delivered.push(call);}return {status:'sent',message_id:'delivery'};});
    client.rpc.handle('model.check',()=>({published:false}));
    await expect(client.rpc.request('initialize',{protocol:1,agents:[{...config,extensions:{global:join(home,'plugins.json')}}],bindings:[]})).rejects.toThrow('arbitrary');
    await expect(readFile(join(home,'imported'),'utf8')).rejects.toThrow();
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'root',agentId:'pa',ownerId:'owner',revision:'1',cwd:workspace});
    await expect.poll(async()=>readFile(join(home,'results.json'),'utf8').catch(()=>''),{timeout:10000}).not.toBe('');
    const results=JSON.parse(await readFile(join(home,'results.json'),'utf8'));
    expect(results[0].result.isError).toBe(true);
    expect(JSON.stringify(results[1].result)).toContain('denied');
    expect(results.slice(3,5).every((entry:any)=>entry.result.isError)).toBe(true);
    expect(delivered).toEqual([expect.objectContaining({args:{target:'owner',text:'Prepared'}})]);
    expect(calls.find(call=>call.method==='pa.action.guard').args.executionEvidence).toHaveProperty('contexts');
    expect(requests).toHaveLength(1); expect(requests[0]).toContain('public+topic');
    expect(calls.find(call=>call.method==='pa.action.complete').args).toMatchObject({state:'confirmed',permit:{proposal_ref:'host-permit'}});
    expect(await readFile(join(workspace,'draft.md'),'utf8')).toBe('private draft');
    expect(await readFile(join(workspace,'.nanoassistant','memory','MEMORY.md'),'utf8')).toContain('"kind":"derived"');
    await expect(readFile(join(home,'executed'),'utf8')).rejects.toThrow();
    expect(await client.rpc.request('pa.review',{agentId:'pa',kind:'action',evidence:{draft:'private'}})).toEqual({decision:'deny',reason:'private detail'});
    const capabilities=await client.rpc.request('session.capabilities',{sessionId:'root'}) as any;
    expect(capabilities.tools).toContain('personal_assistant');expect(capabilities.tools).not.toContain('run_code');expect(capabilities.tools).not.toContain('bash');
    const catalog = await client.rpc.request('configuration.catalog',{agentId:'pa',cwd:workspace}) as any;
    expect(catalog.tools.map((tool:any)=>tool.name)).not.toContain('bash');
    await expect(client.rpc.request('configuration.apply',{...config,revision:'2',toolAllowlist:['bash']})).rejects.toThrow('no controlled adapter');
    expect(await client.rpc.request('pa.evidence',{agentId:'pa',sessionId:'root'})).toHaveProperty('contexts');
    expect(await client.rpc.request('pa.invalidate',{agentId:'pa',sessionId:'root'})).toMatchObject({invalidated:true,retiredSessionIds:['root']});
    expect(await readFile(join(workspace,'.nanoassistant','memory','MEMORY.md'),'utf8')).toBe('');
    await expect(readFile(join(workspace,'draft.md'),'utf8')).rejects.toThrow();
    await expect(client.rpc.request('session.ensure',{sessionId:'root',agentId:'pa',ownerId:'owner',revision:'1',cwd:workspace})).rejects.toThrow('retired');
    await client.shutdown();client=undefined;
    client=new RuntimeClient({home,cwd:home,env,onLog:text=>{logs+=text;}});
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[{sessionId:'root',agentId:'pa',ownerId:'owner',revision:'1',cwd:workspace}]});
    await expect(client.rpc.request('session.observe',{sessionId:'root'})).rejects.toThrow('retired');
    await client.rpc.request('session.ensure',{sessionId:'fresh',agentId:'pa',ownerId:'owner',revision:'1',cwd:workspace});
    await client.shutdown();client=undefined;
  }catch(error){throw new Error(`${error}\n${logs}`,{cause:error});}
  finally{if(client){client.process.kill('SIGKILL');await client.exited;}await new Promise<void>(resolve=>server.close(()=>resolve()));await rm(home,{recursive:true,force:true});}
},25000);

it('checks each concrete search destination and stops a denied redirect before network delivery',async()=>{
  const {createServer}=await import('node:http');
  const {searchProviders}=await import('../lib/web.js');
  const hits:string[]=[];const reviewed:string[]=[];
  const server=createServer((request,response)=>{
    hits.push(request.url!);
    if(request.url!.startsWith('/search')){response.writeHead(302,{location:'/receiver?secret=private'});response.end();}
    else response.end(JSON.stringify({results:[]}));
  });
  await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));
  try{
    const env={SEARXNG_URL:`http://127.0.0.1:${(server.address() as {port:number}).port}`};
    const provider=searchProviders(env,async request=>{reviewed.push(request.url);if(request.url.includes('/receiver'))throw new Error('recipient is not authorized');}).find(provider=>provider.id==='searxng')!;
    await expect(provider.search({query:'ordinary public query'},new AbortController().signal)).rejects.toThrow('not authorized');
    expect(reviewed).toHaveLength(2);expect(hits).toHaveLength(1);expect(hits[0]).toContain('ordinary+public+query');
  }finally{await new Promise<void>(resolve=>server.close(()=>resolve()));}
});

// DeepSeek declares high/max, while other reviewers support low or no reasoning.
it.each([['high','max'],['low','high'],[]])('uses a supported independent-review effort: %j',async (...efforts:string[])=>{
  let request:any;
  const ctx={llm:{resolveModelInfo:async()=>({reasoning:efforts.length?{efforts:efforts.map(id=>({id})),defaultEffort:efforts[0]}:undefined}),stream:async function*(options:any){request=options;yield{type:'block-end',index:0,block:{type:'text',text:'{"decision":"allow","reason":"public lookup"}'}};yield{type:'finish',reason:{kind:'stop'}};}}};
  const result=await reviewPersonal(ctx as any,{personal:{bindingId:'b'},provider:'p',model:'m'} as any,'action',{query:'public'});
  expect(result.decision).toBe('allow');expect(request.reasoningEffort).toBe(efforts.includes('low')?'low':efforts[0]);
  expect(request.tools).toBeUndefined();expect(request.sessionId).toBeUndefined();
});
