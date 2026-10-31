import assert from 'node:assert/strict';
import {expect,it} from 'vitest';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';import {join} from 'node:path';
import {RuntimeClient,prepareProfile} from '../lib/client.js';
import {PersonalAssistant} from '../../personal-assistant/src/personal-assistant.ts';
import {NodeStore} from '../../personal-assistant/src/store.ts';
import {InboxStore} from '../../personal-assistant/src/inbox.ts';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';
it('rejects child public messaging while reviewing Task changes with parent and child evidence',async()=>{
const home=await mkdtemp(join(tmpdir(),'pa-child-delivery-'));let client:any;const logs:string[]=[];
const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
try{
 await writeFile(join(home,'fixture.mjs'),`import{writeFile,appendFile}from'node:fs/promises';
export const name='child-delivery';export const inject=['agents','subagents','tools','llm','nanoProduct'];
export function apply(ctx){const seen=new Set();
ctx.on('agent/pre-step',async({agent,signal},next)=>{
 if(agent.id==='root'&&agent.session.deriveMessages().length&&!seen.has('root')){
  seen.add('root');const run=await ctx.subagents.start('fork',{parent:agent,signal,label:'coordinate-peer',prompt:[{type:'text',text:'Deliver the authorized coordination message'}]});
  try{await run.result;}finally{await run.dispose();}
 }return next();
});
ctx.on('llm/stream',async function*(o){
 const isReview=String(o.sessionId??'').startsWith('nano-codex-');
 if(isReview)await appendFile(process.env.DSH_HOME+'/reviews.jsonl',JSON.stringify({system:o.system,messages:o.messages})+'\\n');
 const agent=o.sessionId?ctx.agents.get(o.sessionId):undefined;
 if(agent?.session.header.parentSession==='root'&&!seen.has(agent.id)){
  seen.add(agent.id);const names=ctx.tools.schemas(agent).map(t=>t.name);
  let representation;try{await ctx.nanoProduct.call('send_user_message',{target:'c_peer',text:'Forbidden child representation'},{agent,signal:o.signal,callId:'child-owner'});}catch(error){representation=String(error);}
  const result=await ctx.tools.execute({name:'send_message',callId:'child-send',arguments:{target:'c_peer',text:'Authorized coordination'},agent,signal:o.signal});
  const task=await ctx.tools.execute({name:'task_graph',callId:'child-task',arguments:{action:'create',target:'c_peer',title:'Shared coordination',mode:'dag',request_key:'child-task'},agent,signal:o.signal});
  await writeFile(process.env.DSH_HOME+'/result.json',JSON.stringify({child:agent.id,names,result,task,representation}));
 }
 yield{type:'block-end',index:0,block:{type:'text',text:isReview?'{"decision":"allow","reason":"Authorized"}':'done'}};
 yield{type:'finish',reason:{kind:'stop'}};
});}`);
 await prepareProfile(home,[{insert:[{id:'child-delivery',name:join(home,'fixture.mjs')}]}]);
 client=new RuntimeClient({home,cwd:home,onLog:(x:string)=>logs.push(x)});
 registerNoopTaskHosts(client);
 const config:any={agentId:'pa',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',personal:{bindingId:'b',ownerId:'owner',conversationId:'c_owner',epoch:1},features:{memory_curation:false,skill_creation:false,task_graph:true},approval:{dangerouslySkipPermissions:true}};
 const binding:any={agentId:'pa',sessionId:'root',ownerId:'owner',cwd:home,revision:'1',conversationId:'global:pa'};store.bind(binding);
 const calls:any[]=[];const errors:any[]=[];const executionEvidence:any[]=[];
 const pa=new PersonalAssistant({nodeId:'node',ownerId:'owner',agents:[config],store,inbox,onError:e=>errors.push(String(e)),runtime:{request:async(m,p)=>{const r=await client.rpc.request(m,p);if(m==='pa.review')executionEvidence.push(p);return r;},onNotification:()=>()=>{}},relay:{request:async(m,p)=>{calls.push({m,p});const result=m==='pa.action.prepare'?{proposal_ref:'p',payload_digest:'frozen',evidence_digest:'evidence',state:'prepared',evidence:{owner_user_id:'owner',recipient:{conversation_id:'c_peer',name:'Peer',conversation_type:'direct',channel:'web',members:[{id:'peer',user_id:'peer',display_name:'Peer',type:'user'}]},policy:{excluded_conversation_ids:[]},sources:[],recipient_risks:[],payload:{content:p.content??'Shared task change',...(p.task?{task:p.task}:{})}}}:m==='pa.action.review-result'?{verdict_ref:'v'}:m==='pa.action.commit'?{state:'confirmed',message_id:'delivered',result:{id:'graph'}}:{};return{type:m+'.result',payload:{ok:true,result}};}}});
 client.rpc.handle('product.call',async(call:any)=>{assert.equal(call.rootSessionId,'root');assert.equal(call.agentId,'pa');assert.equal(call.ownerId,'owner');if(call.method==='send_message')return pa.send(config,binding,call);if(call.method==='task_graph')return pa.task(config,call,{action:call.args.action,arguments:call.args});throw Error('Unexpected '+call.method);});
 await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});await client.rpc.request('session.ensure',binding);
 await client.rpc.request('session.submit',{sessionId:'root',inputId:'seed',mode:'followup',content:[{type:'text',text:'Coordinate through a child'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'seed'}});
 await expect.poll(async()=>(await client.rpc.request('session.lookup',{sessionId:'root',inputId:'seed'})).terminal).toBeTruthy();
 await client.rpc.request('session.submit',{sessionId:'root',inputId:'root-work',mode:'followup',content:[{type:'text',text:'Coordinate through a child'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'root-work'}});
 let result:any;const end=Date.now()+15000;while(Date.now()<end){try{result=JSON.parse(await readFile(join(home,'result.json'),'utf8'));break;}catch{}await new Promise(r=>setTimeout(r,50));}assert(result,'child result missing');assert(result.names.includes('send_message'));
 expect(result.names).not.toContain('send_user_message');
 expect(result.representation).toContain('Only the bound root PA');
 const rootEvidence=await client.rpc.request('pa.evidence',{agentId:'pa',sessionId:'root'});assert(rootEvidence.contexts!==undefined);
 expect(result.result.isError).toBe(true);
 expect(result.task.isError).not.toBe(true);
 expect(calls.filter(c=>c.m==='pa.action.commit'),JSON.stringify({calls,errors})).toHaveLength(1);
 expect(executionEvidence[0]).toMatchObject({sessionId:result.child,kind:'action'});
 const reviewerInputs=await readFile(join(home,'reviews.jsonl'),'utf8');
 expect(reviewerInputs).toContain('Do not apply coding-tool low-risk auto-allow defaults');
 expect(reviewerInputs).toContain('Coordinate through a child');
 expect(reviewerInputs).toContain('Deliver the authorized coordination message');
 await expect(client.rpc.request('pa.evidence',{agentId:'different-agent',sessionId:result.child})).rejects.toThrow('Unknown personal evidence binding');
 await expect(client.rpc.request('pa.evidence',{agentId:'pa',sessionId:'not-a-session'})).rejects.toThrow('Unknown personal evidence binding');
}catch(e){throw new Error(String(e)+'\n'+logs.join('').slice(-1500),{cause:e});}
finally{if(client)await client.shutdown();inbox.close();store.close();await rm(home,{recursive:true,force:true});}

},20000);
