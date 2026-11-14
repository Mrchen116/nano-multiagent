import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createServer,type ServerResponse} from 'node:http';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeSupervisor} from '../../../packages/dsh-integration/src/client.js';
import {GlobalAgent,InboxStore,NodeStore,type ProductCall} from '@nano/personal-assistant';
import type {RelayInput,AgentConfiguration} from '@nano/product-contracts';

it.each(['resume','stopped'])('recovers FS progress and new Inbox input with %s original task',async mode=>{
 const home=await mkdtemp(join(tmpdir(),'nano-fs-product-'));
 const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
 const requests:{messages:any[];response:ServerResponse}[]=[];let generations=0,recoveries=0;let stoppedAt:string|undefined;
 const server=createServer(async(req,res)=>{let body='';for await(const chunk of req)body+=chunk;requests.push({messages:JSON.parse(body),response:res});});
 await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));const port=(server.address() as {port:number}).port;
 const config:AgentConfiguration={agentId:'a',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',features:{dreaming:false},approval:{dangerouslySkipPermissions:true}};
 let product!:GlobalAgent;const errors:unknown[]=[];
 const supervisor=new RuntimeSupervisor({home,cwd:home,health:{tickMs:25,timeoutMs:500,intervalMs:50},
  initialize:async rpc=>{await rpc.request('initialize',{protocol:1,agents:[config],bindings:store.bindings(),taskStopFences:stoppedAt?store.bindings().map(binding=>({sessionId:binding.sessionId,stoppedAt})):[]});},
  onReady:async()=>{generations++;await product.recover();recoveries++;},onUnavailable:async()=>product.runtimeUnavailable([config.agentId]),onError:error=>errors.push(error)});
 product=new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[config],store,inbox,runtime:supervisor,image:async()=>'',onError:error=>errors.push(error),relay:{request:async(type,p:any)=>{
  if(type==='agent.work.append')return{type:'ack',payload:{through_seq:p.events.at(-1).seq}};
  if(type==='conversation.query'&&p.action==='describe')return{type:'ack',payload:{ok:true,result:{conversations:p.targets.map((target:string)=>({target,name:'Owner'}))}}};
  return{type:'ack',payload:{ok:true,result:{target:p.target,name:'Owner',type:'direct',channel:'web',members:[{type:'user',user_id:'owner'}]}}};
 }}});
 supervisor.handle('product.call',value=>product.call(value as ProductCall));supervisor.handle('model.check',()=>({published:false}));
 supervisor.handle('product.task_context.prepare',()=>({messages:[],revoked:[]}));supervisor.handle('product.task_context.commit',()=>null);supervisor.handle('product.task_execution.snapshot',()=>({kind:'quiescent',tasks:[],repair_task_ids:[]}));
 const input=(id:string):RelayInput=>({agent_id:'a',conversation_id:'dm',relay_task_id:id,idempotency_key:id,metadata:{conversation_type:'direct'},message:{id,content:'BODY_'+id,sender_type:'user',sender_user_id:'owner',attachments:[]}});
 const respond=(index:number,read=false)=>requests[index]!.response.end(JSON.stringify(read?[{type:'block-end',index:0,block:{type:'tool-call',id:'read-'+index,name:'inbox',arguments:JSON.stringify({action:'read',target:'dm'})}},{type:'finish',reason:{kind:'tool-calls'}}]:[{type:'block-end',index:0,block:{type:'text',text:'Completed original task.'}},{type:'finish',reason:{kind:'stop'}}]));
 try {
  await writeFile(join(home,'fixture.mjs'),`import fs from 'node:fs';import fsp from 'node:fs/promises';import {syncBuiltinESMExports} from 'node:module';const marker=${JSON.stringify(join(home,'stall'))};const recovered=fs.existsSync(marker);if(recovered)fs.unlinkSync(marker);const stat=fsp.stat;fsp.stat=(...args)=>!recovered&&fs.existsSync(marker)?new Promise(()=>{}):stat(...args);syncBuiltinESMExports();export const inject=['llm'];export function apply(ctx){ctx.on('llm/stream',async function*(o){const r=await fetch('http://127.0.0.1:${port}',{method:'POST',body:JSON.stringify(o.messages),signal:o.signal});for(const chunk of await r.json())yield chunk;});}`);
  await prepareProfile(home,[{insert:[{id:'fs-product-fixture',name:join(home,'fixture.mjs')}]}]);await supervisor.start();
  await product.receive(input('original'));await expect.poll(()=>requests.length).toBe(1);respond(0,true);
  await expect.poll(()=>requests.length).toBe(2);expect(JSON.stringify(requests[1]!.messages)).toContain('BODY_original');
  await expect.poll(()=>inbox.check('a').sources.length).toBe(0);
  if(mode==='stopped')stoppedAt=new Date().toISOString();
  await writeFile(join(home,'stall'),'1');await expect.poll(()=>generations,{timeout:15000}).toBe(2);
  await expect.poll(()=>recoveries,{timeout:6000}).toBe(2);
  let next=2;
  if(mode==='resume'){
    await expect.poll(()=>requests.length,{timeout:6000}).toBe(3);expect(JSON.stringify(requests[2]!.messages)).toContain('BODY_original');respond(2);next=3;
  }else expect(requests).toHaveLength(2);
  await product.receive(input('new'));await expect.poll(()=>requests.length).toBe(next+1);respond(next,true);
  await expect.poll(()=>requests.length).toBe(next+2);expect(JSON.stringify(requests[next+1]!.messages)).toContain('BODY_new');respond(next+1);
 }finally{await supervisor.shutdown();await product.stop();server.closeAllConnections();await new Promise<void>(resolve=>server.close(()=>resolve()));inbox.close();store.close();await rm(home,{recursive:true,force:true});}
},30000);
