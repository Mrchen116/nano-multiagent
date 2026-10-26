import {expect,it} from 'vitest';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {RuntimeClient,prepareProfile} from '../lib/client.js';

it.each(['task','observer'] as const)('enforces the native PA %s child handoff boundary',async role=>{
 const home=await mkdtemp(join(tmpdir(),'pa-child-boundary-'));let client:RuntimeClient|undefined;let logs='';
 try{
  await writeFile(join(home,'private.txt'),'PRIVATE-ROOT-SENTINEL');
  await writeFile(join(home,'input.txt'),'PUBLIC-HANDOFF-CONTENT');
  await writeFile(join(home,'fixture.mjs'),`import{writeFile}from'node:fs/promises';import{join}from'node:path';
export const name='child-boundary';export const inject=['agents','tools','llm'];
export function apply(ctx){const seen=new Set();ctx.on('llm/stream',async function*(o){
 const agent=o.sessionId?ctx.agents.get(o.sessionId):undefined;
 if(agent?.id==='root'&&!seen.has('root')){
  seen.add('root');yield{type:'block-end',index:0,block:{type:'tool-call',id:'spawn',name:'subagent',arguments:JSON.stringify({description:'Read scoped task input',prompt:'Read copied input and prepare a short answer.',handoff_files:${JSON.stringify(role==='task'?['input.txt']:[])},handoff_role:${JSON.stringify(role)},run_in_background:true})}};yield{type:'finish',reason:{kind:'tool-calls'}};return;
 }
 if(agent?.session.header.origin==='subagent'&&!seen.has(agent.id)){
  seen.add(agent.id);const directory=join(process.env.DSH_HOME,'.nanoassistant','delegations',Buffer.from(agent.id).toString('base64url'));
  const run=(name,args)=>ctx.tools.execute({name,callId:'test-'+name+'-'+Math.random(),arguments:args,agent,signal:o.signal});
  const results={privateRead:await run('read',{file_path:join(process.env.DSH_HOME,'private.txt')}),privateGlob:await run('glob',{pattern:'**/*',path:process.env.DSH_HOME}),memory:await run('memory',{action:'search',query:'owner'}),terminal:await run('bash',{command:'cat private.txt'}),publicSend:await run('send_message',{target:'c_peer',text:'private'}),
   input:await run('read',{file_path:join(directory,'1-input.txt')}),write:await run('write',{file_path:join(directory,'answer.txt'),content:'Prepared task result'}),parent:await run('send_message',{agent_id:'root',message:'Prepared answer.txt in my task directory.'})};
  await writeFile(process.env.DSH_HOME+'/result.json',JSON.stringify({results,system:o.system,messages:o.messages,names:ctx.tools.schemas(agent).map(t=>t.name),directory}));
 }
 yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};
});}`);
  await prepareProfile(home,[{insert:[{id:'child-boundary',name:join(home,'fixture.mjs')}]}]);
  client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
  const config={agentId:'pa',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',systemPrompt:'PRIVATE-ROOT-PERSONA',personal:{bindingId:'b',ownerId:'owner',conversationId:'c_owner',epoch:1},features:{memory_curation:false,skill_creation:false,task_graph:false},approval:{dangerouslySkipPermissions:true}};
  const binding={agentId:'pa',sessionId:'root',ownerId:'owner',cwd:home,revision:'1'};
  client.rpc.handle('product.call',()=>{throw new Error('A child must not reach a public product tool');});
  await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});await client.rpc.request('session.ensure',binding);
  await client.rpc.request('session.submit',{sessionId:'root',inputId:'seed',mode:'followup',content:[{type:'text',text:'Prepare a scoped result'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'seed'}});
  let data:any;
  await expect.poll(async()=>{try{data=JSON.parse(await readFile(join(home,'result.json'),'utf8'));return true;}catch{return false;}},{timeout:15000}).toBe(true);
  for(const name of ['privateRead','privateGlob','memory','terminal','publicSend'])expect(data.results[name].isError,name).toBe(true);
  for(const name of (role==='task'?['input','write','parent']:[]))expect(data.results[name].isError,JSON.stringify(data.results[name])).not.toBe(true);
  if(role==='task'){expect(JSON.stringify(data.results.input)).toContain('PUBLIC-HANDOFF-CONTENT');expect(await readFile(join(data.directory,'answer.txt'),'utf8')).toBe('Prepared task result');}
  else {for(const name of ['input','write','parent'])expect(data.results[name].isError,name).toBe(true);for(const name of ['read','write','notes','history','web_search','send_message'])expect(data.names).not.toContain(name);}
  expect(JSON.stringify({system:data.system,messages:data.messages})).not.toContain('PRIVATE-ROOT-PERSONA');
  expect(data.names).not.toContain('memory');expect(data.names).not.toContain('send_user_message');expect(data.names).not.toContain('bash');
 }catch(error){throw new Error(`${error}\n${logs}`,{cause:error});}
 finally{await client?.shutdown().catch(()=>{});await rm(home,{recursive:true,force:true});}
},25000);
