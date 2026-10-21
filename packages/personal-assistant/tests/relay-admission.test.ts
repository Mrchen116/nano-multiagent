import { expect, test } from 'vitest';
import { InboxStore } from '../src/inbox.js';
import { NodeStore } from '../src/store.js';
import { GlobalAgent } from '../src/global-agent.js';
import type { RelayInput } from '@nano/product-contracts';
const input:RelayInput={agent_id:'a',conversation_id:'chat',relay_task_id:'r',idempotency_key:'key',metadata:{conversation_type:'direct'},message:{id:'m',content:'hello',sender_type:'user',sender_user_id:'owner',attachments:[]}};
test('durable admission precedes unavailable runtime and a lost receipt does not block wake',async()=>{
 const inbox=new InboxStore(':memory:'),store=new NodeStore(':memory:','owner');let unavailable=true,wakes=0,work=0;
 const product=new GlobalAgent({nodeId:'n',ownerId:'owner',agents:[{agentId:'a',workspace:'/tmp',revision:'1',mode:'global',provider:'test',model:'test'}],store,inbox,
 runtime:{onNotification:()=>()=>{},async request(method){if(method==='session.ensure'&&unavailable)throw Error('runtime offline');if(method==='session.submit')wakes++;return method==='session.descendants'?[]:{durable:true,events:[]};}},
 relay:{ready:true,async request(type){if(type==='agent.work.append'){work++;throw Error('bulk unavailable');}if(type==='node.delivery_receipt')throw Error('ACK lost');return {type:'ack',payload:{}};}},image:async()=>'',onError:()=>{}});
 try{await product.receive(structuredClone(input)).catch(()=>{});expect(inbox.check('a').sources[0]?.unread).toBe(1);unavailable=false;await product.recover();expect(wakes).toBe(1);expect(work).toBe(0);await product.receive(structuredClone(input));expect(wakes).toBe(1);}finally{await product.stop();inbox.close();store.close();}
});
test('a duplicated relay retains each receipt identity while rejecting mutated input',()=>{
 const inbox=new InboxStore(':memory:');try{
 inbox.acceptRelay(input,true);inbox.acceptRelay({...input,relay_task_id:'r2'},true);
 expect(inbox.check('a').sources[0]?.unread).toBe(1);expect(inbox.pendingRelays().map(r=>r.input.relay_task_id)).toEqual(['r','r2']);
 expect(()=>inbox.acceptRelay({...input,message:{...input.message,content:'changed'}},true)).toThrow(/conflict/);
 }finally{inbox.close();}
});

test('stop-like ordinary text cannot reserve a control position or block later inputs',async()=>{
 const inbox=new InboxStore(':memory:'),store=new NodeStore(':memory:','owner');const submitted:unknown[]=[];
 const product=new GlobalAgent({nodeId:'n',ownerId:'owner',agents:[{agentId:'a',workspace:'/tmp',revision:'1',mode:'global',provider:'test',model:'test'}],store,inbox,
 runtime:{onNotification:()=>()=>{},async request(method,payload){if(method==='session.submit')submitted.push(payload);return method==='session.descendants'?[]:{durable:true,events:[]};}},relay:{async request(){return {type:'ack',payload:{}};}},image:async()=>'',onError:()=>{}});
 try{
  const first=product.receive({...input,message:{...input.message,content:'/stop now'}});
  const second=product.receive({...input,relay_task_id:'next',idempotency_key:'next',message:{...input.message,id:'next',content:'continue'}});
  await Promise.race([Promise.all([first,second]),new Promise((_,reject)=>setTimeout(()=>reject(Error('ordinary input blocked')),200))]);
  expect(inbox.pendingControls()).toEqual([]);expect(submitted.length).toBeGreaterThan(0);expect(inbox.check('a').sources[0]?.unread).toBe(2);
 }finally{await product.stop();inbox.close();store.close();}
});

test('a revoked receipt cannot starve a later valid conversation',async()=>{
 const inbox=new InboxStore(':memory:'),store=new NodeStore(':memory:','owner');const ids:string[]=[];
 inbox.acceptRelay(input,true);inbox.acceptRelay({...input,relay_task_id:'valid',conversation_id:'other',message:{...input.message,id:'valid'}},true);
 const {RelayDeliveryError}=await import('@nano/channels');
 const product=new GlobalAgent({nodeId:'n',ownerId:'owner',agents:[],store,inbox,runtime:{onNotification:()=>()=>{},request:async()=>({})},relay:{async request(_type,payload){ids.push(String(payload.relay_task_id));if(payload.relay_task_id==='r')throw new RelayDeliveryError('revoked','rejected','scope_not_allowed');return {type:'ack',payload:{}};}},image:async()=>'',onError:()=>{}});
 try{await product.recover();expect(ids).toEqual(['r','valid']);expect(inbox.pendingRelays()).toEqual([]);}finally{await product.stop();inbox.close();store.close();}
});
