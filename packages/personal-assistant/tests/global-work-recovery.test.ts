import {execFileSync} from 'node:child_process';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import { expect, it } from 'vitest';
import type { RelayInput } from '@nano/product-contracts';
import { NodeStore } from '../src/store.js';
import { InboxStore } from '../src/inbox.js';
import { GlobalAgent } from '../src/global-agent.js';
import { logicalEvents } from '../src/presentation.js';
import { projectWorkEvent } from '../src/work-projection.js';

it('reconciles only the changed Global execution after initial recovery', async () => {
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  store.bind({agentId:'a',sessionId:'main',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
  let notify!: (method: string, value: unknown) => void;
  const calls: string[] = [];
  const errors: unknown[] = [];
  let failNext=false;
  const changed = {kind:'child',id:'child',parentId:'main',throughSeq:4,modelVersion:'done'};
  const product = new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[{agentId:'a',workspace:'/tmp',revision:'1',provider:'p',model:'m',mode:'global'}],store,inbox,
    runtime:{onNotification:listener=>{notify=listener;return ()=>{};},request:async(method)=>{
      calls.push(method);
      if(method==='session.work.children')return {children:[]};
      if(method==='session.work.targets') {
        if(failNext) {failNext=false;throw Error('parent flush failed');}
        return {children:[changed]};
      }
      return {durable:true,events:[],throughSeq:4,modelVersion:'done',modelRuns:[]};
    }},relay:{ready:false,request:async()=>({type:'ack',payload:{}})},image:async()=>'',onError:error=>errors.push(error)});
  try {
    await product.recover();
    await expect.poll(()=>inbox.workProcessingPending).toBe(false);
    calls.length=0;
    notify('session.event',{sessionId:'main',rootSessionId:'main',event:{seq:5,type:'step/start'}});
    await expect.poll(()=>inbox.workProcessingPending).toBe(false);
    expect(calls).toEqual(['session.work.root']);
    calls.length=0;
    notify('session.work.changed',{sessionId:'main',rootSessionId:'main',childId:'child'});
    await expect.poll(()=>inbox.workCut('child')).toMatchObject({throughSeq:4});
    expect(calls).toEqual(['session.work.targets','session.work.child']);
    calls.length=0;failNext=true;
    notify('session.work.changed',{sessionId:'main',rootSessionId:'main',childId:'child'});
    await expect.poll(()=>errors).toHaveLength(1);
    notify('session.event',{sessionId:'main',rootSessionId:'main',event:{seq:6,type:'step/start'}});
    await expect.poll(()=>calls.includes('session.work.root')).toBe(true);
    expect(inbox.workProcessingPending).toBe(true);
    await expect.poll(()=>inbox.workProcessingPending,{timeout:3000}).toBe(false);
    expect(calls).toEqual(['session.work.targets','session.work.root','session.work.targets']);
  } finally {await product.stop();inbox.close();store.close();}
});

it('retains child processing positions when the GlobalAgent is recreated, without treating Work ACK as processing', async () => {
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  store.bind({agentId:'a',sessionId:'main',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
  const calls:any[]=[];
  const events=[{seq:1,time:1,type:'turn/start',data:{turn:1}},
    {seq:2,time:2,type:'user/message',data:{source:{kind:'subagent'}}},
    {seq:3,time:3,type:'assistant/message',data:{turn:1,message:{id:'reply',content:[{type:'text',text:'done'}]},usage:{inputTokens:10,outputTokens:3,cacheReadTokens:2}}},
    {seq:4,time:4,type:'turn/end',data:{turn:1,reason:{kind:'completed'}}}];
  const create=()=>new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[{agentId:'a',workspace:'/tmp',revision:'1',provider:'p',model:'m',mode:'global'}],store,inbox,
    runtime:{onNotification:()=>()=>{},request:async(method,args:any)=>{
      if(method==='session.work.children')return {children:[{kind:'child',id:'child',parentId:'main',throughSeq:4,modelVersion:'done'}]};
      if(method==='session.work.child'){calls.push(structuredClone(args));return {durable:true,events,throughSeq:4,modelVersion:'done',modelRuns:[]};}
      return {events:[],durable:true,status:'idle'};
    }},relay:{ready:false,request:async()=>({type:'ack',payload:{}})},image:async()=>'',onError:error=>{throw error;}});
  let product=create();
  try {
    await product.recover();
    await expect.poll(()=>inbox.workProcessingPending).toBe(false);
    await product.stop(); product=create();
    await product.recover();
    await expect.poll(()=>inbox.workProcessingPending).toBe(false);
    expect(calls).toHaveLength(1);
    expect(inbox.workCheckpoints('main').child).toMatchObject({throughSeq:4,modelVersion:'done'});
    expect(inbox.throughSeq).toBe(0);
    expect(inbox.journal(0).filter(event=>event.type==='turn_end')).toHaveLength(1);
    expect(inbox.journal(0).find(event=>event.type==='turn_end')).toMatchObject({payload:{usage:{context_used:12,output:3,cache_read_tokens:2}}});
  }finally{await product.stop();inbox.close();store.close();}
});

it.each(['settled','changed-child','active-child'])('uses metadata recovery for %s without hydrating completed root history', async state=>{
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  store.bind({agentId:'a',sessionId:'main',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
  inbox.commitWork('main',{rootSessionId:'main',throughSeq:5,replayFrom:6,modelVersion:'m'},[]);
  inbox.commitWork('child',{rootSessionId:'main',throughSeq:3,replayFrom:4,modelVersion:'m'},[]);
  const calls:string[]=[];
  const product=new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[{agentId:'a',workspace:'/tmp',revision:'1',provider:'p',model:'m',mode:'global'}],store,inbox,
    runtime:{onNotification:()=>()=>{},request:async(method,args:any)=>{
      calls.push(method);
      if(method==='session.work.check')return {rootSettled:state!=='active-child'};
      if(method==='session.work.children')return {children:[{kind:'child',id:'child',parentId:'main',throughSeq:state==='settled'?3:5,modelVersion:'m'}]};
      if(method==='session.work.child')return {durable:true,throughSeq:5,modelVersion:'m',events:[],modelRuns:[]};
      return {events:[],durable:true,status:'idle',throughSeq:5,modelVersion:'m'};
    }},relay:{request:async()=>({type:'ack',payload:{}})},image:async()=>'',onError:error=>{throw error;}});
  try {
    expect(inbox.workProcessingPending).toBe(true);
    await product.recover();
    await expect.poll(()=>inbox.workProcessingPending).toBe(false);
    expect(calls.includes('session.ensure')).toBe(state==='active-child');
    expect(calls.includes('session.work.root')).toBe(state==='active-child');
    expect(calls.includes('session.work.child')).toBe(state!=='settled');
    expect(inbox.workProcessingPending).toBe(false);
  }finally{await product.stop();inbox.close();store.close();}
});

it('repairs a root projection crash after native receipt and preserves open-turn pairing across restart',async()=>{
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  store.bind({agentId:'a',sessionId:'main',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
  const source:any[]=[
    {seq:0,time:0,type:'request/header',data:{header:{config:{model:'retained-model'}}}},
    {seq:1,time:1,type:'request/context',data:{contextWindow:8192}},
    {seq:2,time:2,type:'turn/start',data:{turn:1}},
    {seq:3,time:3,type:'user/message',data:{turn:1,source:{kind:'human'},content:[]}},
    {seq:4,time:4,type:'tool/call',data:{turn:1,callId:'read',name:'read',arguments:'{"path":"file"}'}},
    {seq:5,time:5,type:'assistant/message',data:{turn:1,message:{id:'reply',content:[]},usage:{inputTokens:10,outputTokens:3,cacheReadTokens:2}}},
  ];
  const errors:unknown[]=[];
  const create=()=>new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[{agentId:'a',workspace:'/tmp',revision:'1',provider:'p',model:'m',mode:'global'}],store,inbox,
    runtime:{onNotification:()=>()=>{},request:async(method,args:any)=>method==='session.work.children'?{children:[]}:{events:source.filter(event=>event.seq>(args.afterSeq??-1)),durable:true,status:'idle',throughSeq:source.at(-1).seq}},
    relay:{request:async()=>({type:'ack',payload:{}})},image:async()=>'',onError:error=>{errors.push(error);}});
  const commit=inbox.commitWork.bind(inbox);let fail=true;
  inbox.commitWork=(...args)=>{if(fail){fail=false;throw new Error('simulated local projection crash');}commit(...args);};
  let product=create();
  try {
    await product.recover();
    expect(errors).toHaveLength(1);expect(store.cursor('main')).toBe(5);expect(inbox.workCheckpoints('main')).toEqual({});expect(inbox.workProcessingPending).toBe(true);
    await product.stop();product=create();await product.recover();
    expect(inbox.workCheckpoints('main').main).toMatchObject({throughSeq:5,replayFrom:2,model:'retained-model',contextWindow:8192});
    source.push({seq:6,time:8,type:'tool/result',data:{turn:1,message:{toolCallId:'read',content:[{type:'text',text:'result'}],isError:false}}},
      {seq:7,time:9,type:'turn/end',data:{turn:1,reason:{kind:'completed'}}});
    await product.stop();product=create();await product.recover();
    expect(inbox.journal(0).filter(event=>event.type==='tool_start')).toHaveLength(1);
    expect(inbox.journal(0).find(event=>event.type==='tool_end')).toMatchObject({payload:{tool_name:'read',duration_ms:4,arguments:{path:'file'}}});
    expect(inbox.journal(0).find(event=>event.type==='turn_end')).toMatchObject({payload:{usage:{context_used:12,output:3,context_window:8192},elapsed_ms:7}});
    expect(inbox.workCheckpoints('main').main).toMatchObject({throughSeq:7,replayFrom:8});
    source.push({seq:8,time:10,type:'turn/start',data:{turn:2}},{seq:9,time:11,type:'user/message',data:{turn:2,source:{kind:'human'},content:[]}});
    await product.recover();
    expect(inbox.journal(0).find(event=>event.type==='turn_started'&&event.turn_id==='2')).toMatchObject({payload:{model:'retained-model'}});
  }finally{await product.stop();inbox.close();store.close();}
});

it('projects an observed cold interruption even when its native fallback run never resumed', () => {
  const start={seq:7,time:1,type:'turn/start',data:{turn:1}};
  const stale={seq:13,time:2,type:'turn/end',data:{turn:1,reason:{kind:'error'}}};
  const interrupted={seq:17,time:3,type:'turn/end',data:{turn:2,reason:{kind:'interrupted'}}};
  const events=logicalEvents([start,stale,interrupted],[{id:'child:1',sessionId:'child',turn:1,state:'running',
    attempts:[{turn:1,route:{provider:'p',model:'primary'}},{turn:2,route:{provider:'p',model:'backup'}}]}],true);
  expect(events.map(event=>event.seq)).toEqual([7,17]);
  expect(projectWorkEvent('child',events[1]!,events,true)).toMatchObject({type:'turn_end',turn:1,payload:{status:'interrupted',stop_reason:'interrupted'}});
});

it('does not mark the root current when only a child hint succeeds after a root read failure', async()=>{
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  store.bind({agentId:'a',sessionId:'main',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
  let notify!:(method:string,value:unknown)=>void;
  const errors:unknown[]=[];
  const product=new GlobalAgent({nodeId:'node',ownerId:'owner',store,inbox,image:async()=>'',onError:error=>errors.push(error),
    agents:[{agentId:'a',workspace:'/tmp',revision:'1',provider:'p',model:'m',mode:'global'}],
    relay:{request:async()=>({type:'ack',payload:{}})},
    runtime:{onNotification:listener=>{notify=listener;return ()=>{};},request:async method=>{
      if(method==='session.work.root')throw new Error('no root barrier');
      if(method==='session.work.children')return {children:[]};
      throw new Error(method);
    }}});
  try {
    notify('session.event',{sessionId:'main'});
    await expect.poll(()=>errors.length).toBe(1);
    expect(inbox.workProcessingPending).toBe(true);
    notify('session.event',{sessionId:'child',rootSessionId:'main'});
    await expect.poll(()=>errors.length).toBe(2);
    expect(inbox.workProcessingPending).toBe(true);
    expect(inbox.workCut('main')).toBeUndefined();
  } finally {await product.stop();inbox.close();store.close();}
});


it('reconciles a durable Inbox read before concurrent Relay can wake the same root, without waiting for child Work', async () => {
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  store.bind({agentId:'a',sessionId:'main',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
  const input: RelayInput = {agent_id:'a',conversation_id:'c',relay_task_id:'relay',idempotency_key:'key',
    metadata:{conversation_type:'direct'},message:{id:'message',content:'original',sender_type:'user',sender_user_id:'owner',attachments:[]}};
  inbox.acceptRelay(input,true);
  inbox.admitWake('a',1);
  const read = inbox.read('a','main','read',{target:'c'});
  const events = [
    {seq:0,time:0,type:'turn/start',data:{turn:1}},
    {seq:1,time:1,type:'tool/result',data:{turn:1,message:{toolCallId:'read',isError:false,content:[{type:'text',text:JSON.stringify(read)}]}}},
    {seq:2,time:2,type:'turn/end',data:{turn:1,reason:{kind:'interrupted'}}},
  ];
  const root = Promise.withResolvers<void>(), rootStarted = Promise.withResolvers<void>();
  const child = Promise.withResolvers<void>(), childStarted = Promise.withResolvers<void>();
  const submitted: string[] = [], receipts: string[] = [];
  const product = new GlobalAgent({nodeId:'node',ownerId:'owner',store,inbox,image:async()=>'',onError:error=>{throw error;},
    agents:[{agentId:'a',workspace:'/tmp',revision:'1',provider:'p',model:'m',mode:'global'}],
    relay:{request:async(type,payload)=>{
      if(type==='node.delivery_receipt')receipts.push(String(payload.delivery_status));
      return {type:'ack',payload:{}};
    }},
    runtime:{onNotification:()=>()=>{},request:async(method,args:any)=>{
      if(method==='session.work.root'){
        rootStarted.resolve();
        await root.promise;
        return {durable:true,throughSeq:2,events:events.filter(event=>event.seq>(args.afterSeq??-1))};
      }
      if(method==='session.work.children'){
        childStarted.resolve();
        await child.promise;
        return {children:[]};
      }
      if(method==='session.lookup')return {accepted:true,acceptedSeq:0,terminal:{kind:'interrupted'}};
      if(method==='session.submit')submitted.push(args.inputId);
      return {};
    }},
  });
  const recovery = product.recover();
  let redelivery: Promise<void> | undefined;
  try {
    await rootStarted.promise;
    redelivery = product.receive(input);
    root.resolve();
    await childStarted.promise;
    await Promise.all([recovery, redelivery]);
    expect(submitted).toEqual([]);
    expect(receipts).toContain('failed');
    expect(inbox.unreadAttention('a')).toBeUndefined();
    expect(inbox.workProcessingPending).toBe(true);
    child.resolve();
    await expect.poll(()=>inbox.workProcessingPending).toBe(false);
  } finally {
    root.resolve();
    child.resolve();
    await Promise.allSettled([recovery, redelivery]);
    await product.stop();
    inbox.close();
    store.close();
  }
});

it('projects model delivery sidecars before acknowledging them and replays a lost acknowledgement', async () => {
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  store.bind({agentId:'a',sessionId:'main',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
  let notify!: (method:string,value:unknown) => void;
  const submitted: string[] = [], receipts: {id:string;status:string}[] = [], errors:unknown[] = [];
  let delivered:string[] = [], failAck = true, acknowledgements = 0;
  const product = new GlobalAgent({nodeId:'node',ownerId:'owner',store,inbox,image:async()=>'',onError:error=>errors.push(error),
    agents:[{agentId:'a',workspace:'/tmp',revision:'1',provider:'p',model:'m',mode:'global'}],
    runtime:{onNotification:listener=>{notify=listener;return ()=>{};},request:async(method,args:any)=>{
      if(method==='session.submit'){submitted.push(args.inputId);return {accepted:true,durable:true};}
      if(method==='session.lookup')return {accepted:false};
      if(method==='session.work.root')return {durable:true,events:[],throughSeq:-1,inboxDelivered:delivered};
      if(method==='session.work.children')return {children:[]};
      if(method==='session.inbox-delivered.confirm'){
        acknowledgements++;
        expect(inbox.pendingRelays().every(row=>row.status!=='accepted')).toBe(true);
        if(failAck){failAck=false;throw Error('acknowledgement lost');}
        delivered=[];
      }
      return {status:'idle'};
    }},
    relay:{request:async(type,payload:any)=>{
      if(type==='node.delivery_receipt')receipts.push({id:payload.relay_task_id,status:payload.delivery_status});
      return {type:'ack',payload:type==='conversation.query'?{ok:true,result:{conversations:payload.targets.map((target:string)=>({target,name:target}))}}:{}};
    }},
  });
  const input=(id:string):RelayInput=>({agent_id:'a',conversation_id:'c',relay_task_id:id,idempotency_key:id,metadata:{conversation_type:'direct',agent_receipt:true},message:{id,content:id,sender_type:'user',sender_user_id:'owner',attachments:[]}});
  try {
    await product.receive(input('first'));
    await expect.poll(()=>receipts).toEqual([{id:'first',status:'accepted'}]);
    await product.receive(input('later'));
    await expect.poll(()=>receipts.length).toBe(2);
    expect(receipts.every(row=>row.status==='accepted')).toBe(true);
    delivered=[submitted[0]!];
    notify('session.event',{sessionId:'main'});
    await expect.poll(()=>errors.length).toBe(1);
    notify('session.event',{sessionId:'main'});
    await expect.poll(()=>acknowledgements).toBeGreaterThanOrEqual(2);
    await expect.poll(()=>receipts.filter(row=>row.status==='sent')).toEqual([{id:'first',status:'sent'}]);
    expect(receipts.filter(row=>row.id==='later')).toEqual([{id:'later',status:'accepted'}]);
  } finally {await product.stop();inbox.close();store.close();}
});


it.each(['interrupted','error','aborted'])('retains a migrated non-attention wake through %s until model receipt',async terminal=>{
  const home=mkdtempSync(join(tmpdir(),'nano-legacy-wake-')),path=join(home,'inbox.db');
  const store=new NodeStore(':memory:','owner');let inbox=new InboxStore(path);
  const input:RelayInput={agent_id:'a',conversation_id:'group',relay_task_id:'legacy',idempotency_key:'legacy',metadata:{conversation_type:'group',agent_receipt:true},message:{id:'legacy',content:'original',sender_type:'user',sender_user_id:'owner',attachments:[]}};
  inbox.acceptRelay(input,false);inbox.close();
  const db=new DatabaseSync(path);db.exec("UPDATE relay_receipts SET status='sent',confirmed=1");db.close();
  execFileSync('python3',['scripts/migrate_model_delivery_receipts.py','apply','--kind','inbox','--database',path,'--writers-stopped']);
  inbox=new InboxStore(path);store.bind({agentId:'a',sessionId:'main',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
  const admitted=new Map<string,any>(),submitted:string[]=[];let delivered:string[]=[];let notify!:(method:string,args:any)=>void;
  const product=new GlobalAgent({nodeId:'node',ownerId:'owner',store,inbox,agents:[{agentId:'a',workspace:'/tmp',revision:'1',provider:'p',model:'m',mode:'global'}],image:async()=>'',onError:error=>{throw error;},
    runtime:{onNotification:listener=>{notify=listener;return()=>{};},request:async(method,args:any)=>{
      if(method==='session.lookup')return admitted.get(args.inputId)??{accepted:false};
      if(method==='session.submit'){submitted.push(args.inputId);admitted.set(args.inputId,{accepted:true,acceptedSeq:10});return{accepted:true,durable:true};}
      if(method==='session.work.children')return{children:[]};
      if(method==='session.work.root')return{durable:true,events:[],throughSeq:-1,inboxDelivered:delivered};
      if(method==='session.inbox-delivered.confirm'){delivered=[];return{};}
      return{status:'idle'};
    }},relay:{request:async(type,args:any)=>({type:'ack',payload:type==='conversation.query'?{ok:true,result:{conversations:args.targets.map((target:string)=>({target,name:target}))}}:{}})}});
  try{
    await product.recover();expect(submitted).toEqual(['inbox-wake:a:1:delivery-recovery']);expect(inbox.legacyReceiptWake('a')).toBe(1);
    admitted.set(submitted[0]!,{accepted:true,acceptedSeq:10,terminal:{kind:terminal}});
    product.runtimeUnavailable(['a']);await product.recover();
    if(terminal==='aborted'){expect(submitted).toHaveLength(1);return;}
    expect(submitted).toEqual(['inbox-wake:a:1:delivery-recovery','inbox-wake:a:1:delivery-recovery:recovery:10']);
    expect(inbox.legacyReceiptWake('a')).toBe(1);
    delivered=[submitted[1]!];notify('session.event',{sessionId:'main'});
    await expect.poll(()=>inbox.legacyReceiptWake('a')).toBeUndefined();
  }finally{await product.stop();inbox.close();store.close();rmSync(home,{recursive:true,force:true});}
});
