import { expect, it } from 'vitest';
import { InboxStore } from '../src/inbox.js';
import type { RelayInput } from '@nano/product-contracts';
const input=(id:string):RelayInput=>({agent_id:'pa',conversation_id:'chat',relay_task_id:id,idempotency_key:id,metadata:{personal_unclassified:true},message:{id,content:id,sender_type:'user',sender_user_id:'peer',attachments:[]}});
it('keeps rejected and failed messages out of reads without removing another admitted input',()=>{
 const inbox=new InboxStore(':memory:');
 try {
  for(const id of ['good','bad','down'])inbox.acceptRelay(input(id),false);
  for(const [id,state] of [['good','admitted'],['bad','rejected'],['down','failed']] as const){
   const generation=inbox.reviews.begin('pa',id)!;
   inbox.reviews.settle('pa',id,generation,{state,reason:state,error_code:state==='failed'?'model_unavailable':undefined});
  }
  const accepted=input('good');accepted.metadata={personal_delivery:'participant'};inbox.classify(accepted,true);
  expect(inbox.read('pa','main','call',{target:'chat'})).toMatchObject({messages:[{id:'good'}]});
  expect(inbox.check('pa',true).review_failures).toEqual([expect.objectContaining({message_id:'down',state:'failed'})]);
  expect(inbox.reviews.begin('pa','down')).toBeUndefined();
  const next=inbox.reviews.begin('pa','down',true)!;
  expect(next).toBe(2);
  expect(inbox.reviews.settle('pa','down',1,{state:'admitted'})).toBe(false);
 }finally{inbox.close();}
});

import { mkdtempSync,rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import { GlobalAgent } from '../src/global-agent.js';
import { NodeStore } from '../src/store.js';

it('recovers an interrupted review as a discoverable failure and keeps migration idempotent',()=>{
 const home=mkdtempSync(join(tmpdir(),'inbox-review-')),path=join(home,'inbox.db');
 try {
  let inbox=new InboxStore(path);inbox.acceptRelay(input('interrupted'),false);inbox.reviews.begin('pa','interrupted');inbox.close();
  inbox=new InboxStore(path);
  expect(inbox.reviews.get('pa','interrupted')).toMatchObject({state:'failed',error_code:'interrupted'});
  expect(inbox.reviews.pending('pa')).toEqual([]);inbox.close();
  const db=new DatabaseSync(path);
  for(const [id,consumed,metadata] of [['unknown',0,{}],['settled',1,{}],['allowed',0,{personal_delivery:'participant'}]] as const)
   db.prepare('INSERT INTO inbox(agent_id,target,message_id,payload,attention,consumed) VALUES(?,?,?,?,0,?)').run('pa','chat',id,JSON.stringify({...input(id),metadata}),consumed);
  db.close();
  inbox=new InboxStore(path);inbox.reviews.migrate(['pa']);
  expect(inbox.reviews.get('pa','unknown')).toMatchObject({state:'failed',error_code:'legacy_unreviewed'});
  expect(inbox.reviews.get('pa','settled')).toMatchObject({state:'failed',error_code:'legacy_settled',event_delivered:true});
  expect(inbox.reviews.get('pa','allowed')).toMatchObject({state:'admitted'});
  expect(inbox.reviews.failures('pa').map(row=>row.message_id)).not.toContain('settled');
  expect(inbox.reviews.begin('pa','settled',true)).toBeUndefined();
  const before=inbox.check('pa',true);inbox.reviews.migrate(['pa']);expect(inbox.check('pa',true)).toEqual(before);inbox.close();
 }finally{rmSync(home,{recursive:true,force:true});}
});

it('does not retry a failed input during Inbox reads or recovery and explicitly retries only that message',async()=>{
 const inbox=new InboxStore(':memory:'),store=new NodeStore(':memory:','owner');let available=false,reviews=0;
 const submissions:any[]=[];
 const config={agentId:'pa',mode:'global' as const,workspace:'/tmp',revision:'1',provider:'p',model:'m',personal:{bindingId:'b',ownerId:'owner',conversationId:'owner-chat',epoch:1}};
 const product=new GlobalAgent({nodeId:'n',ownerId:'owner',agents:[config],store,inbox,image:async()=>'',onError:()=>{},
  runtime:{onNotification:()=>()=>{},request:async(method,args:any)=>{
   if(method==='pa.review'){reviews++;return {decision:available?'allow':'unavailable',reason:'temporary model outage'};}
   if(method==='session.submit'){submissions.push(args);return {accepted:true,durable:true};}
   if(method==='session.descendants')return [];
   return {events:[],status:'idle',durable:true};
  }},relay:{request:async(type,args:any)=>{
   const result=type==='pa.source.admit'?{allowed:true,is_owner:args.source_message_id==='good',delivery:'participant',conversation_type:'direct',channel:'web'}
    :type==='pa.sources'?{items:[{id:'chat',excluded:false}]}:type==='pa.incidents.pending'?{items:[{incident_ref:'incident',peer_notice_message_id:null}]}:type==='pa.observations.read'?{items:[]}:type==='conversation.query'?{name:'Chat',conversations:[]}:{};
   return {type:'ack',payload:{ok:true,result}};
  }}});
 try {
  await product.receive(input('down'));await product.receive(input('good'));
  expect(reviews).toBe(1);expect(submissions.filter(x=>x.source.channel==='input-review')).toHaveLength(1);
  const binding=store.bindingFor('pa','global:pa')!;
  const call=(action:string,extras={})=>product.call({method:'inbox',args:{action,...extras},operationId:action,callId:action,sessionId:binding.sessionId,rootSessionId:binding.sessionId,agentId:'pa',ownerId:'owner'});
  expect(await call('check')).toMatchObject({review_failures:[{message_id:'down'}],sources:[{unread:1}],security_incidents:[{incident_ref:'incident',peer_notice_message_id:null}]});
  expect(await call('read',{target:'chat'})).toMatchObject({messages:[{id:'good'}]});
  await product.recover();expect(reviews).toBe(1);
  available=true;
  expect(await call('review',{message_id:'down'})).toMatchObject({kind:'admitted',message_id:'down'});
  expect(reviews).toBe(2);expect(inbox.check('pa',true).review_failures).toEqual([]);
 }finally{await product.stop();inbox.close();store.close();}
});

it('plans without writes and rolls back historical admission migration before its marker commits',async()=>{
 const {backup}=await import('node:sqlite');
 const {inspectInputMigration,verifyInputMigration}=await import('../src/migrate-input-review.js');
 const root=mkdtempSync(join(tmpdir(),'input-migration-')),path=join(root,'inbox.db');
 let inbox:InboxStore|undefined,db:DatabaseSync|undefined,before:DatabaseSync|undefined;
 try {
  inbox=new InboxStore(path);inbox.close();inbox=undefined;
  db=new DatabaseSync(path);
  db.prepare('INSERT INTO inbox(agent_id,target,message_id,payload,attention,consumed) VALUES(?,?,?,?,0,0)').run('pa','chat','legacy',JSON.stringify(input('legacy')));
  db.prepare("INSERT INTO publications VALUES('sent','peer','body','confirmed','{\"message_id\":\"real\"}','pa')").run();
  await backup(db,join(root,'before.db'));before=new DatabaseSync(join(root,'before.db'),{readOnly:true});
  expect(inspectInputMigration(before).state).toBe('pending');
  db.exec("CREATE TRIGGER interrupt_input_migration BEFORE INSERT ON metadata WHEN NEW.key='input-review-v1' BEGIN SELECT RAISE(ABORT,'test interruption'); END;");db.close();db=undefined;
  inbox=new InboxStore(path);
  expect(()=>inbox!.reviews.migrate(['pa'])).toThrow('test interruption');
  expect(inbox.reviews.get('pa','legacy')).toBeUndefined();inbox.close();inbox=undefined;
  db=new DatabaseSync(path);db.exec('DROP TRIGGER interrupt_input_migration');db.close();db=undefined;
  inbox=new InboxStore(path);inbox.reviews.migrate(['pa']);inbox.close();inbox=undefined;
  db=new DatabaseSync(path,{readOnly:true});expect(verifyInputMigration(db,before).verified).toBe(true);
 }finally{inbox?.close();db?.close();before?.close();rmSync(root,{recursive:true,force:true});}
});
