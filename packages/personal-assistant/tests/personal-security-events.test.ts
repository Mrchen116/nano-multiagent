import { expect, it } from 'vitest';
import { GlobalAgent } from '../src/global-agent.js';
import { NodeStore } from '../src/store.js';
import { InboxStore } from '../src/inbox.js';

it.each([true,false])('delivers automatic-block facts with owner-only instructions to the main PA (currently blocked=%s)',async blocked=>{
 const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
 store.bind({agentId:'pa',ownerId:'owner',sessionId:'main',conversationId:'global:pa',revision:'1'});
 const submitted:any[]=[];let acked=false;
 const config={agentId:'pa',revision:'1',provider:'test',model:'test',mode:'global' as const,personal:{bindingId:'binding',ownerId:'owner',conversationId:'c_owner',epoch:1}};
 const payload={incident_ref:'fifth',owner_only:true,owner_target:'conversation:c_owner',actor_id:'peer',actor_name:'Lin',conversation:{id:'group',name:'Book club',type:'group'},source_message_id:'risk-5',automatic_block:{threshold:5,currently_blocked:blocked},owner_notice_message_id:null};
 const product=new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[config],store,inbox,image:async()=>'',onError:e=>{throw e;},
  runtime:{onNotification:()=>()=>{},request:async(method,args:any)=>{
   if(method==='session.submit'&&!submitted.some(item=>item.inputId===args.inputId))submitted.push(args);
   return {events:[],accepted:true,durable:true,status:'idle'};
  }},relay:{ready:true,request:async(type)=>{
   if(type==='pa.observations.ack')acked=true;
   return {type:'result',payload:{ok:true,result:type==='pa.observations.read'?{items:acked?[]:[{event_id:5,kind:'security.incident',payload}]}:type==='pa.incidents.pending'?{items:[payload]}:{}}};
  }}});
 try {
  await product.recoverPersonalObservations();await product.recoverPersonalObservations();
  expect(submitted).toHaveLength(1);
  expect(submitted[0]).toMatchObject({sessionId:'main',source:{kind:'system',channel:'personal-state'}});
  expect(submitted[0].content[0].text).toContain('five');
  expect(submitted[0].content[0].text).toContain('Only notify the owner');
  expect(submitted[0].content[0].text).toContain('currently_blocked');
  expect(submitted[0].content[0].text).not.toContain('then refuse');
  expect(JSON.parse(submitted[0].content[1].text.split('external evidence: ')[1])).toEqual({kind:'security.incident',payload});
 }finally{await product.stop();inbox.close();store.close();}
});

it('recovers an unconfirmed automatic notice after disable/enable without reviving old ordinary inputs',async()=>{
 const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
 const config={agentId:'pa',revision:'1',provider:'test',model:'test',mode:'global' as const,personal:{bindingId:'binding',ownerId:'owner',conversationId:'c_owner',epoch:1}};
 const snapshot=(revision:number,desired:'enabled'|'disabled')=>({agent_id:'pa',desired,revision,disabled_through_revision:revision>1?2:0,request_id:'r',actor_user_id:'owner',requested_at:new Date().toISOString(),applied_revision:revision,observed:desired,process_instance_id:null,confirmed_at:null,error_code:null,error_detail:null});
 const submitted:any[]=[];const accepted=new Set<string>();let confirmed=false;
 const product=new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[config],store,inbox,image:async()=>'',onError:e=>{throw e;},
  runtime:{onNotification:()=>()=>{},request:async(method,args:any)=>{
   if(method==='session.submit'&&!accepted.has(args.inputId)){accepted.add(args.inputId);submitted.push(args);}
   return {events:[],accepted:true,durable:true,status:'idle'};
  }},relay:{ready:true,request:async(type)=>({type:'result',payload:{ok:true,result:{items:type==='pa.incidents.pending'&&!confirmed?[{incident_ref:'fifth',owner_only:true,owner_target:'conversation:c_owner',automatic_block:{threshold:5,currently_blocked:true}}]:[]}}})}});
 try {
  await product.recoverPersonalObservations();
  expect(submitted).toHaveLength(1);
  store.lifecycle.save(snapshot(2,'disabled'));store.cancelAgent('pa');
  await product.recoverPersonalObservations();expect(submitted).toHaveLength(1);
  store.lifecycle.save(snapshot(3,'enabled'));
  await product.recoverPersonalObservations();await product.recoverPersonalObservations();
  expect(submitted).toHaveLength(2);
  expect(submitted[1].lifecycle_revision).toBe(3);
  expect(submitted[1].inputId).not.toBe(submitted[0].inputId);
  expect(submitted[1].content[0].text).toContain('Only notify the owner');
  confirmed=true;await product.recoverPersonalObservations();expect(submitted).toHaveLength(2);
 }finally{await product.stop();inbox.close();store.close();}
});
