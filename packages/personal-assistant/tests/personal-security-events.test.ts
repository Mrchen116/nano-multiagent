import { expect, it } from 'vitest';
import { GlobalAgent } from '../src/global-agent.js';
import { NodeStore } from '../src/store.js';
import { InboxStore } from '../src/inbox.js';

it.each([true,false])('delivers automatic-block facts with owner-only instructions to the main PA (currently blocked=%s)',async blocked=>{
 const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
 store.bind({agentId:'pa',ownerId:'owner',sessionId:'main',conversationId:'global:pa',revision:'1'});
 const submitted:any[]=[];let acked=false;
 const config={agentId:'pa',revision:'1',provider:'test',model:'test',mode:'global' as const,personal:{bindingId:'binding',ownerId:'owner',conversationId:'c_owner',epoch:1}};
 const payload={incident_ref:'fifth',owner_only:true,owner_target:'conversation:c_owner',actor_id:'peer',source_message_id:'risk-5',automatic_block:{threshold:5,currently_blocked:blocked},owner_notice_message_id:null};
 const product=new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[config],store,inbox,image:async()=>'',onError:e=>{throw e;},
  runtime:{onNotification:()=>()=>{},request:async(method,args:any)=>{
   if(method==='session.submit')submitted.push(args);
   return {events:[],accepted:true,durable:true,status:'idle'};
  }},relay:{ready:true,request:async(type)=>{
   if(type==='pa.observations.ack')acked=true;
   return {type:'result',payload:{ok:true,result:type==='pa.observations.read'?{items:acked?[]:[{event_id:5,kind:'security.incident',payload}]}:{}}};
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
