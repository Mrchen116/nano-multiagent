import { DatabaseSync } from 'node:sqlite';
import { expect, it } from 'vitest';
import type { AgentLifecycleSnapshot } from '@nano/product-contracts';
import { AgentLifecycleAuthority } from '../src/agent-lifecycle.js';

function snapshot(revision: number, desired: 'enabled' | 'disabled'): AgentLifecycleSnapshot {
  return {agent_id:'a',desired,revision,disabled_through_revision:revision > 1 ? 2 : 0,request_id:'request',actor_user_id:'owner',
    requested_at:new Date().toISOString(),applied_revision:revision,observed:desired,process_instance_id:null,confirmed_at:null,error_code:null,error_detail:null};
}

it('persists disable and rejects stale input and output even after a new enable', async () => {
  const db = new DatabaseSync(':memory:');
  try {
    const authority = new AgentLifecycleAuthority(db);
    authority.save(snapshot(1,'enabled'));
    let continueOutput!: () => void;
    const pending = authority.run('a',1,async () => {
      await new Promise<void>(resolve => { continueOutput=resolve; });
      return authority.assert('a');
    });
    authority.save(snapshot(2,'disabled'));
    expect(() => authority.assert('a')).toThrow('agent_disabled');
    expect(new AgentLifecycleAuthority(db).snapshot('a')?.desired).toBe('disabled');
    authority.save(snapshot(3,'enabled'));
    continueOutput();
    await expect(pending).rejects.toThrow('stale_lifecycle');
    expect(authority.run('a',3,()=>authority.assert('a'))).toBe(3);
    expect(authority.assert('b')).toBe(1);
    authority.save(snapshot(1,'enabled'));
    expect(authority.snapshot('a')?.revision).toBe(3);
  } finally { db.close(); }
});

it('replaces cleanup evidence on stop and the next process launch',()=>{
  const db=new DatabaseSync(':memory:');
  try {
    const authority=new AgentLifecycleAuthority(db);
    authority.saveProof('a',{boot:'one',processInstanceId:'first',stopped:false});
    authority.saveProof('a',{boot:'one',processInstanceId:'first',stopped:true});
    expect(new AgentLifecycleAuthority(db).proof('a')?.stopped).toBe(true);
    authority.saveProof('a',{boot:'one',processInstanceId:'second',stopped:false});
    expect(new AgentLifecycleAuthority(db).proof('a')).toEqual({boot:'one',processInstanceId:'second',stopped:false});
  } finally {db.close();}
});

import { NodeStore } from '../src/store.js';
import { InboxStore } from '../src/inbox.js';
import { SingleThread } from '../src/single-thread.js';
import { ExternalChannels } from '../src/external.js';
import type { RelayInput } from '@nano/product-contracts';
const input=(id:string,agent='a'):RelayInput=>({agent_id:agent,conversation_id:'chat',relay_task_id:id,idempotency_key:id,metadata:{conversation_type:'direct'},message:{id,content:'hello',sender_type:'user',sender_user_id:'owner',attachments:[]}});
const binding=(agent='a')=>({agentId:agent,sessionId:agent,ownerId:'owner',conversationId:'chat',cwd:'/tmp',revision:'1'});
function disableEnable(store:NodeStore) {store.lifecycle.save(snapshot(2,'disabled'));store.cancelAgent('a');store.lifecycle.save(snapshot(3,'enabled'));}

it('retains cancelled input and journal evidence while retiring only the disabled Agent obligations',()=>{
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  try {
    store.bind(binding());store.bind(binding('b'));
    store.receive('a',input('old'));store.receive('b',input('other','b'));
    store.bufferGroup(input('parked'));store.prepareDelivery('a',1);
    inbox.acceptRelay(input('old'),true);inbox.acceptRelay(input('control'),false,true);
    inbox.acceptRelay(input('other','b'),true);inbox.preparePublication('a:call','chat','draft','a');
    inbox.append({event_id:'history',root_agent_id:'a',session_id:'main',type:'message',payload:{text:'kept'}});inbox.acknowledge(1);
    disableEnable(store);inbox.cancelAgent('a');
    store.inputEvidence('a:old',{accepted:true,turn:1,terminal:{kind:'completed'}},true);
    expect(store.inputs('a')[0]).toMatchObject({input:{message:{content:'hello'}},terminal:'{"kind":"cancelled_by_disable"}'});
    expect(store.lookupInputIds('a')).toEqual([]);expect(store.lookupInputIds('b')).toEqual(['b:other']);
    expect(store.delivery('a',1)?.state).toBe('cancelled_by_disable');
    expect(()=>store.admitInput(input('old'))).toThrow('stale_lifecycle');
    expect(()=>store.admitInput(input('parked'))).toThrow('stale_lifecycle');
    store.takeGroup(binding());expect(store.inputs('a')).toHaveLength(1);
    expect(inbox.check('a').sources).toEqual([]);expect(inbox.check('b').sources).toHaveLength(1);
    expect(inbox.wakePending('a')).toBeUndefined();expect(inbox.pendingControls()).toEqual([]);
    expect(inbox.publication('a:call')?.state).toBe('cancelled_by_disable');
    expect(inbox.input('a','old')?.message.content).toBe('hello');expect(inbox.pendingRelays()).toHaveLength(3);
    expect(inbox.throughSeq).toBe(1);expect(inbox.journal(0)).toHaveLength(1);
  }finally{inbox.close();store.close();}
});

it('does not submit a single-thread input whose image wait crosses disable and enable',async()=>{
  const store=new NodeStore(':memory:','owner');let release!:()=>void,started!:()=>void;const ready=new Promise<void>(r=>started=r),gate=new Promise<void>(r=>release=r);let submits=0;
  const product=new SingleThread({nodeId:'n',ownerId:'owner',store,agents:[{agentId:'a',revision:'1',mode:'single_thread',provider:'p',model:'m',workspace:'/tmp'}],
    runtime:{onNotification:()=>()=>{},request:async(method)=>{if(method==='session.submit')submits++;if(method==='session.lookup')return {accepted:false};return {events:[],durable:true};}},
    relay:{request:async()=>({type:'ack',payload:{}})},image:async()=>{started();await gate;return 'image';},onError:()=>{}});
  try {
    const old=input('image');old.message.attachments=[{url:'image',content_type:'image/png',file_name:'image'}];
    const pending=product.receive(old);await ready;disableEnable(store);release();
    await expect(pending).rejects.toThrow('stale_lifecycle');expect(submits).toBe(0);
    await product.recover();expect(submits).toBe(0);
    await expect(product.receive(old)).rejects.toThrow('stale_lifecycle');
    await product.receive(input('new'));expect(submits).toBe(1);
  } finally {release();await product.stop();store.close();}
});

it('keeps an external image admission in its original epoch across stop and restart',async()=>{
  const store=new NodeStore(':memory:','owner');let release!:()=>void,started!:()=>void;const ready=new Promise<void>(r=>started=r),gate=new Promise<void>(r=>release=r);let received=0,mirrored=0;
  const external=new ExternalChannels(':memory:',{nodeId:'n',ownerId:'owner',store,relay:{ready:true,request:async()=>({type:'ack',payload:{}})},
    im:async()=>{mirrored++;return {id:'shadow'};},receive:async()=>{received++;},permission:async()=>{},onError:()=>{}});
  external.add('a',{config:{appId:'app'},send:async()=>'',thinking:async()=>undefined,image:async()=>{started();await gate;return {data:Buffer.alloc(1),mediaType:'image/png'};},updateCard:async()=>{}});
  try {
    const message={messageId:'image',chatId:'c',senderId:'owner',isGroup:false,mentioned:false,time:'1',parts:[{type:'image' as const,key:'key'}]};
    const pending=external.receive('a',message);await ready;disableEnable(store);release();
    await expect(pending).rejects.toThrow('stale_lifecycle');await external.recover();
    expect(received).toBe(0);expect(mirrored).toBe(0);expect(()=>external.receive('a',message)).toThrow('stale_lifecycle');
  } finally {release();await external.stop();store.close();}
});

it('commits final stopped Work history and checkpoints without opening execution or publication',async()=>{
  const {GlobalAgent}=await import('../src/global-agent.js');
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  store.bind(binding());store.lifecycle.save(snapshot(2,'disabled'));
  let calls=0;
  const product=new GlobalAgent({nodeId:'n',ownerId:'owner',store,inbox,agents:[{agentId:'a',revision:'1',mode:'global',provider:'p',model:'m',workspace:'/tmp'}],
    runtime:{onNotification:()=>()=>{},request:async()=>{calls++;throw new Error('Must not restore execution');}},
    relay:{request:async()=>{calls++;throw new Error('Must not publish');}},onError:()=>{}});
  const events=[{seq:1,time:1,type:'turn/start',data:{turn:1}},{seq:2,time:2,type:'user/message',data:{source:{kind:'human'},content:[{type:'text',text:'Old task'}]}},{seq:3,time:3,type:'turn/end',data:{turn:1,reason:{kind:'cancelled'}}}];
  try {
    const history=[{sessionId:'a',rootSessionId:'a',events,modelRuns:[],throughSeq:3},{sessionId:'child',rootSessionId:'a',parentSessionId:'a',events,modelRuns:[],throughSeq:3}];
    product.recordStopped('a',history);product.recordStopped('a',history);
    expect(calls).toBe(0);expect(inbox.workCheckpoints('a').child?.throughSeq).toBe(3);
    expect(inbox.journal(0).filter(event=>event.type==='turn_end')).toHaveLength(2);
    expect(inbox.journal(0).filter(event=>event.type==='turn_end').every(event=>(event.payload as {status:string}).status==='interrupted')).toBe(true);
    expect(inbox.workProcessingPending).toBe(false);expect(store.cursor('a')).toBe(3);
  } finally {await product.stop();inbox.close();store.close();}
});

it('attributes a new native Schedule after its public Inbox replacement without relabeling old history',()=>{
  const store=new NodeStore(':memory:','owner');store.bind(binding());store.lifecycle.save(snapshot(3,'enabled'));
  const message={id:'new-schedule',content:[{type:'text',text:'new due'}],source:{kind:'schedule'}};
  try {
    store.recordEvents('a',[{seq:1,time:1,type:'agent/inbox/spliced',data:{inserted:[message]}}]);
    expect(store.inputs('a')).toEqual([]);
    store.recordEvents('a',[{seq:2,time:2,type:'agent/inbox/spliced',data:{inserted:[{...message,source:{...message.source,lifecycle_revision:3}}]}}]);
    store.recordEvents('a',[{seq:3,time:3,type:'user/message',data:{...message,id:'historical-schedule'}}]);
    expect(store.inputs('a').find(input=>input.id==='new-schedule')?.input.lifecycle_revision).toBe(3);
    expect(store.inputs('a').find(input=>input.id==='historical-schedule')?.input.lifecycle_revision).toBe(1);
  }finally{store.close();}
});
