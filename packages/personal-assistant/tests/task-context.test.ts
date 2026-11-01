import {expect,it} from 'vitest';
import type {AgentConfiguration,RelayInput} from '@nano/product-contracts';
import {NodeStore} from '../src/store.js';
import {InboxStore} from '../src/inbox.js';
import {TaskContext} from '../src/task-context.js';
import {SingleThread} from '../src/single-thread.js';
const agent:AgentConfiguration={agentId:'a',mode:'global',workspace:'/tmp',revision:'1',provider:'p',model:'m'};
const original=(id:string):RelayInput=>({agent_id:'a',conversation_id:'chat',idempotency_key:id,relay_task_id:id,message:{id,content:'Original '+id,sender_type:'system',sender_user_id:'human',attachments:[],system_notice:{kind:'task_graph',attention_actor_ids:['a']}},metadata:{task_context:true}});
const runtime={request:async()=>({}),onNotification:()=>()=>{}};
it('persists a fixed multi-page cut, then revalidates all unread originals before admission',async()=>{
 const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
 const binding=store.bind({agentId:'a',sessionId:'s',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
 let receivedPages=0,refreshed=0;const requests:Record<string,unknown>[]=[];
 const service=new TaskContext({nodeId:'node',ownerId:'owner',agents:[agent],store,inbox,runtime,refreshSources:async()=>{refreshed++;},relay:{request:async(_type,args)=>{
   requests.push(args);const after=args.after as number,through=args.through??33,pending=args.pending as string[];
   if(pending.length)return {type:'result',payload:{ok:true,result:{through,next:after,items:[],revoked_message_ids:pending.includes('m1')?['m1']:[]}}};
   receivedPages++;const end=Math.min(after+32,33);
   return {type:'result',payload:{ok:true,result:{through,next:end,items:Array.from({length:end-after},(_,n)=>{const seq=after+n+1;return {seq,message_id:'m'+seq,conversation_id:'chat',allowed:true,input:original('m'+seq)};}),revoked_message_ids:[]}}};
 }}});
 try{
  const identity={agentId:'a',ownerId:'owner',sessionId:binding.sessionId};
  const prepared=await service.prepare(identity);
  expect(receivedPages).toBe(2);expect(refreshed).toBe(1);expect(requests[1]!.through).toBe(33);
  expect(prepared.messages).toHaveLength(32);expect(prepared.messages.some(message=>message.inputId==='m1')).toBe(false);expect(prepared.revoked).toContain('m1');
  expect(store.taskContextCursor('a')).toBe(33);expect(store.systemContextInputs('a').filter(row=>row.state==='consumed')).toHaveLength(0);
  const message=prepared.messages[0]!;
  await expect(service.commit({...identity,evidence:[{inputId:message.inputId,content:[{type:'text',text:'forged'}],turn:1,consumedSeq:10}]})).resolves.toBeUndefined();
  expect(store.systemContextInputs('a').find(row=>row.message_id===message.inputId)?.state).toBe('prepared');
  await service.commit({...identity,evidence:[{inputId:message.inputId,content:message.content,turn:1,consumedSeq:10}]});
  expect(store.systemContextInputs('a').find(row=>row.message_id===message.inputId)?.state).toBe('consumed');
  expect(inbox.prepareSystemContext('a','s').some(item=>item.inputId===message.inputId)).toBe(false);
  // A delayed valid ACK cannot resurrect an original withdrawn before admission.
  await service.commit({...identity,evidence:[{inputId:'m1',content:[],turn:1,consumedSeq:11}]});
  expect(store.systemContextInputs('a').find(row=>row.message_id==='m1')?.state).toBe('revoked');
 }finally{inbox.close();store.close();}
});
it('keeps revoked-before-prepared references independent for multiple affected Agents',()=>{
 const store=new NodeStore(':memory:','owner');try{store.revokeSystemContext('a','original','chat');store.revokeSystemContext('b','original','chat');expect(store.systemContextInputs('a')[0]?.state).toBe('revoked');expect(store.systemContextInputs('b')[0]?.state).toBe('revoked');}finally{store.close();}
});
it('returns explicit unavailable while retaining pending originals, then recovers under current authority',async()=>{
 const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');let offline=true;
 store.bind({agentId:'a',sessionId:'s',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
 inbox.receive(original('pending'),false);
 const service=new TaskContext({nodeId:'node',ownerId:'owner',agents:[agent],store,inbox,runtime,refreshSources:async()=>{},relay:{request:async()=>{
  if(offline)throw new Error('CENTER_OFFLINE');
  return {type:'result',payload:{ok:true,result:{through:0,next:0,items:[],revoked_message_ids:[]}}};
 }}});
 const identity={agentId:'a',sessionId:'s',ownerId:'owner'};
 try {
  expect(await service.prepare(identity)).toEqual({unavailable:true,messages:[],revoked:[],unavailableInputs:[{inputId:'pending',conversationId:'chat'}]});
  expect(inbox.prepareSystemContext('a','s')).toHaveLength(1);
  offline=false;expect((await service.prepare(identity)).messages).toHaveLength(1);
  await expect(service.prepare({...identity,ownerId:'wrong'})).rejects.toThrow('identity');
 }finally{inbox.close();store.close();}
});
it('does not submit a second SingleThread identity or wake for a passive indexed Task notice',async()=>{
 const store=new NodeStore(':memory:','owner'),receipts:unknown[]=[];
 const product=new SingleThread({nodeId:'node',ownerId:'owner',agents:[{...agent,mode:'single_thread'}],store,runtime:{...runtime,request:async()=>{throw new Error('unexpected native wake');}},relay:{request:async(type,args)=>{receipts.push({type,args});return {type:'result',payload:{ok:true}};}},image:async()=>'',onError:error=>{throw error;}});
 try{await product.receive(original('original'));expect(receipts).toHaveLength(1);expect(store.bindings()).toHaveLength(0);}finally{await product.stop();store.close();}
});
