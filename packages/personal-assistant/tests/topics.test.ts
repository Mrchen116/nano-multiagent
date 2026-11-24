import {expect, it} from 'vitest';
import type {RelayInput, RuntimeEvent} from '@nano/product-contracts';
import {NodeStore} from '../src/store.js';
import {SingleThread} from '../src/single-thread.js';
import {GlobalAgent} from '../src/global-agent.js';
import {InboxStore} from '../src/inbox.js';
import {chatDelivery} from '../src/attention.js';

const topic: RelayInput = {
  agent_id:'alice', conversation_id:'c_chat', relay_task_id:'relay', idempotency_key:'msg',
  message:{id:'msg',content:'只核对周三',sender_type:'user',sender_user_id:'member',attachments:[]},
  metadata:{conversation_type:'group',addressed_to_agent:true,thread_root_message_id:'request',
    thread_root_sender:'王',thread_root_excerpt:'核对排期',thread_earlier:[{id:'prior',sender:'李',excerpt:'先看周末'}],
    thread_history_truncated:true},
};

it('splits inbox sources by thread target and attaches page-level thread_context only on first read or reactivation', () => {
  const inbox = new InboxStore(':memory:');
  try {
    inbox.receive({...topic, message:{...topic.message, id:'main-1', content:'主时间线消息'}, metadata:{conversation_type:'group', addressed_to_agent:true}}, true);
    inbox.receive(topic, true);
    const snapshot = inbox.check('alice');
    expect(snapshot.sources.map(s => s.target).sort()).toEqual(['c_chat', 'c_chat:request']);
    expect(snapshot.sources.find(s => s.target === 'c_chat:request')).toMatchObject({ parent_target: 'c_chat', unread: 1 });
    expect(JSON.stringify(snapshot)).not.toContain('只核对周三');
    expect(JSON.stringify(snapshot)).not.toContain('核对排期');

    const page1 = inbox.read('alice', 'main', 'read-1', { target: 'c_chat:request' }) as any;
    expect(page1.target).toBe('c_chat:request');
    expect(page1.parent_target).toBe('c_chat');
    expect(page1.thread_context).toMatchObject({
      root_message_id: 'request',
      root_sender: '王',
      root_excerpt: '核对排期',
      earlier_replies: [{ id: 'prior', sender: '李', excerpt: '先看周末' }],
      truncated: true,
    });
    expect(page1.messages[0]).not.toHaveProperty('thread');
    expect(inbox.commitRead('main', 'read-1', [{ type: 'text', text: JSON.stringify(page1) }], false, 5)).toBe(true);

    // Second reply in the same thread within the same session omits thread_context (zero repetition).
    inbox.receive({ ...topic, relay_task_id: 'relay-2', idempotency_key: 'msg-2', message: { ...topic.message, id: 'msg-2', content: '补充周四' } }, true);
    const page2 = inbox.read('alice', 'main', 'read-2', { target: 'c_chat:request' }) as any;
    expect(page2).not.toHaveProperty('thread_context');
    expect(page2.messages).toHaveLength(1);
    expect(page2.messages[0].content).toEqual([{ type: 'text', text: '补充周四' }]);
    expect(inbox.commitRead('main', 'read-2', [{ type: 'text', text: JSON.stringify(page2) }], false, 6)).toBe(true);

    // After compaction (clearSeenThreads) or reactivation, thread_context is re-supplied.
    inbox.receive({
      ...topic, relay_task_id: 'relay-3', idempotency_key: 'msg-3',
      message: { ...topic.message, id: 'msg-3', content: '重新叫你回来' },
      metadata: { ...topic.metadata, thread_follow_reactivated: true },
    }, true);
    const page3 = inbox.read('alice', 'main', 'read-3', { target: 'c_chat:request' }) as any;
    expect(page3.thread_context).toBeDefined();
    expect(page3.follow_reactivated).toBe(true);
    expect(inbox.commitRead('main', 'read-3', [{ type: 'text', text: JSON.stringify(page3) }], false, 7)).toBe(true);

    inbox.clearSeenThreads('main');
    inbox.receive({ ...topic, relay_task_id: 'relay-4', idempotency_key: 'msg-4', message: { ...topic.message, id: 'msg-4', content: '压缩后的回复' } }, true);
    const page4 = inbox.read('alice', 'main', 'read-4', { target: 'c_chat:request' }) as any;
    expect(page4.thread_context).toBeDefined();
  } finally { inbox.close(); }
});

it('wakes a followed PA observation without changing observer identity or owner-only scope', () => {
  const input={...topic, metadata:{...topic.metadata,personal_delivery:'observer',pa_observation:true,context_only:true}};
  const agent={agentId:'alice',mode:'global' as const,provider:'test',model:'test',revision:'1'};
  expect(chatDelivery(input,agent,'owner')).toBe('high');
  expect(chatDelivery(input,{...agent,collaborationScope:'owner_only'},'owner')).toBe('skip');
  expect(chatDelivery({...input,metadata:{...input.metadata,thread_root_message_id:undefined}},agent,'owner')).toBe('background');
});

it.each([true,false])('routes automatic text by the confirmed request topic using unified target after streaming began (sent=%s)',async sent=>{
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  store.bind({agentId:'alice',sessionId:'session',conversationId:'c_chat',ownerId:'owner',revision:'1',cwd:'/tmp'});
  const input={...topic,message:{...topic.message,id:'request'},metadata:{conversation_type:'direct'}};
  store.receive('session',input);
  const frames:Record<string,unknown>[]=[];
  const events:RuntimeEvent[]=[{seq:1,time:1,type:'turn/start',data:{turn:1}}];
  const options={
    nodeId:'n',ownerId:'owner',store,inbox,
    agents:[{agentId:'alice',revision:'1',mode:'single_thread' as const,provider:'test',model:'test',workspace:'/tmp'}],
    runtime:{onNotification:()=>()=>{},async request(method:string,args?:unknown) {
      if(method==='session.lookup')return {accepted:true,turn:1};
      return {durable:true,events:events.filter(event=>event.seq>((args as {afterSeq?:number})?.afterSeq??-1))};
    }},
    relay:{async request(type:string,payload:Record<string,unknown>){
      if (type==='agent.message') {
        if(!sent)throw new Error('not accepted');
        return {type:'ack',payload:{message_id:'explicit',conversation_id:'c_chat'}};
      }
      if(type==='conversation.query')return {type:'ack',payload:{ok:true,result:{type:'direct',channel:'web'}}};
      frames.push(payload);
      return {type:'ack',payload:{message_id:payload.thread_root_message_id?'topic-output':'main-output'}};
    }},
    image:async()=>'',onError:(error:unknown)=>{throw error;},
  };
  const single=new SingleThread(options), tools=new GlobalAgent(options);
  try {
    await single.recover();
    expect(frames.find(frame=>frame.kind==='turn_start')).not.toHaveProperty('thread_root_message_id');
    const args={target:'current:request',text:'开始核对'};
    events.push({seq:2,time:2,type:'tool/call',data:{turn:1,callId:'send',name:'send_message',arguments:JSON.stringify(args)}});
    const sending=tools.call({method:'send_message',args,operationId:'session:send',callId:'send',sessionId:'session',rootSessionId:'session',agentId:'alice',ownerId:'owner'});
    if(sent)expect(await sending).toMatchObject({status:'sent', target:'current:request'});else await expect(sending).rejects.toThrow('not accepted');
    events.push({seq:3,time:3,type:'assistant/message',data:{turn:1,message:{id:'result',content:[{type:'text',text:'3 辆'}]}}},
      {seq:4,time:4,type:'turn/end',data:{turn:1,reason:{kind:'completed'}}});
    await single.recover();
    expect(frames.some(frame=>frame.kind==='message_discarded'&&frame.message_id==='main-output')).toBe(sent);
    expect(frames.some(frame=>frame.kind==='turn_start'&&frame.thread_root_message_id==='request')).toBe(sent);
    expect(frames.find(frame=>frame.kind==='message_completed')).toMatchObject({message_id:sent?'topic-output':'main-output',final_content:'3 辆'});
  }finally{await single.stop();await tools.stop();inbox.close();store.close();}
});

it('sends strictly to the explicit target without silent rewriting and isolates held_for_revalidation per thread', async () => {
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  store.bind({agentId:'alice',sessionId:'main',conversationId:'global:alice',ownerId:'owner',revision:'1',cwd:'/tmp'});
  const publications:Record<string,unknown>[]=[];
  const product=new GlobalAgent({nodeId:'n',ownerId:'owner',store,inbox,
    agents:[{agentId:'alice',workspace:'/tmp',revision:'1',provider:'test',model:'test',mode:'global'}],
    runtime:{onNotification:()=>()=>{},async request(method){return method==='session.work.children'?{children:[]}:{events:[],durable:true,status:'idle'};}},
    relay:{async request(type,payload){
      if(type==='agent.message'){publications.push(payload);return {type:'ack',payload:{message_id:`m_${publications.length}`,conversation_id:'c_chat'}};}
      return {type:'ack',payload:{ok:true,result:{type:'group',channel:'web',target:'c_chat'}}};
    }},image:async()=>'',onError:error=>{throw error;}});
  try {
    // Unread message in thread "request" must block sending to c_chat:request,
    // but must NOT block sending to main timeline c_chat or another thread c_chat:other.
    inbox.receive(topic, true);
    const held = await product.call({method:'send_message',args:{target:'c_chat:request',text:'在话题A回复'},sessionId:'main',rootSessionId:'main',ownerId:'owner',agentId:'alice',operationId:'main:hold',callId:'hold'});
    expect(held).toMatchObject({status:'held_for_revalidation', target:'c_chat:request', inbox_targets:['c_chat:request']});

    const otherThread = await product.call({method:'send_message',args:{target:'c_chat:other',text:'在话题B回复'},sessionId:'main',rootSessionId:'main',ownerId:'owner',agentId:'alice',operationId:'main:other',callId:'other'});
    expect(otherThread).toMatchObject({status:'sent', target:'c_chat:other'});

    const mainTimeline = await product.call({method:'send_message',args:{target:'c_chat',text:'主时间线通知'},sessionId:'main',rootSessionId:'main',ownerId:'owner',agentId:'alice',operationId:'main:main',callId:'main'});
    expect(mainTimeline).toMatchObject({status:'sent', target:'c_chat'});

    // Read & commit thread "request", then sending to c_chat still goes to main timeline (NO silent hijack) while c_chat:request goes to thread.
    const page = inbox.read('alice','main','read',{target:'c_chat:request'});
    inbox.commitRead('main','read',[{type:'text',text:JSON.stringify(page)}],false,3);
    store.recordEvents('main',[{seq:3,time:3,type:'tool/call',data:{turn:3,callId:'main2',name:'send_message',arguments:'{}'}},
      {seq:4,time:4,type:'tool/call',data:{turn:3,callId:'thread2',name:'send_message',arguments:'{}'}}]);
    await product.call({method:'send_message',args:{target:'c_chat',text:'仍发主时间线'},sessionId:'main',rootSessionId:'main',ownerId:'owner',agentId:'alice',operationId:'main:main2',callId:'main2'});
    await product.call({method:'send_message',args:{target:'c_chat:request',text:'明确发话题A'},sessionId:'main',rootSessionId:'main',ownerId:'owner',agentId:'alice',operationId:'main:thread2',callId:'thread2'});

    expect(publications.map(item=>item.in_thread_of)).toEqual(['other', undefined, undefined, 'request']);
  } finally {await product.stop();inbox.close();store.close();}
});

it('single-thread renders full thread context only on first encounter and uses compact format for subsequent replies', async () => {
  const store=new NodeStore(':memory:','owner');
  const submitted: string[] = [];
  const accepted = new Set<string>();
  const single = new SingleThread({
    nodeId:'n', ownerId:'owner', store,
    agents:[{agentId:'alice',revision:'1',mode:'single_thread',provider:'test',model:'test',workspace:'/tmp'}],
    runtime:{onNotification:()=>()=>{}, async request(method, args: any){
      if(method==='session.lookup') return {accepted:accepted.has(args.inputId)};
      if(method==='session.submit') { accepted.add(args.inputId); submitted.push(args.content.map((c: any) => c.text ?? '').join('\n')); return {accepted:true, durable:true}; }
      return {durable:true, events:[]};
    }},
    relay:{async request(){return {type:'ack',payload:{}}; }},
    image:async()=>'', onError:error=>{throw error;},
  });
  try {
    const longRoot = '3f4b1fd482a94c001122334455667788';
    const msg1: RelayInput = {
      agent_id:'alice', conversation_id:'c_chat', relay_task_id:'r1', idempotency_key:'k1',
      message:{id:'aaaaaaaaaaaaaaaa1111111111111111', content:'第一条话题回复', sender_type:'user', sender_user_id:'u_123456', attachments:[]},
      metadata:{conversation_type:'group', addressed_to_agent:true, thread_root_message_id:longRoot,
        thread_root_sender:'王', thread_root_excerpt:'根消息内容', thread_earlier:[], thread_history_truncated:true},
    };
    await single.receive(msg1);
    expect(submitted).toHaveLength(1);
    expect(submitted[0]).toContain('c_chat:3f4b1fd4');
    expect(submitted[0]).toContain('根消息内容');
    expect(submitted[0]).toContain('read_messages');
    expect(submitted[0]).not.toContain(longRoot);

    const msg2: RelayInput = {
      ...msg1, relay_task_id:'r2', idempotency_key:'k2',
      message:{...msg1.message, id:'bbbbbbbbbbbbbbbb2222222222222222', content:'第二条话题回复'},
    };
    await single.receive(msg2);
    expect(submitted).toHaveLength(2);
    expect(submitted[1]).toContain('[Thread c_chat:3f4b1fd4]');
    expect(submitted[1]).toContain('第二条话题回复');
    expect(submitted[1]).not.toContain('根消息内容');
  } finally { await single.stop(); store.close(); }
});
