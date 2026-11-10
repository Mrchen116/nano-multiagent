import { expect, it } from 'vitest';
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
    await product.recover(); calls.length=0;
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
    await product.recover(); await product.stop(); product=create();
    await product.recover();
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
