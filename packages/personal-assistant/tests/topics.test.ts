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
    thread_root_sender:'王',thread_root_excerpt:'核对排期',thread_earlier:[{id:'prior',sender:'李',excerpt:'先看周末'}]},
};

it('preserves topic history and addresses only the conversation and turn actually read', () => {
  const inbox = new InboxStore(':memory:');
  try {
    inbox.receive(topic,true);
    const page = inbox.read('alice','main','read',{target:'c_chat'});
    const rendered = JSON.stringify(page);
    for (const item of ['request','核对排期','先看周末']) expect(rendered).toContain(item);
    expect(rendered.split('只核对周三')).toHaveLength(2);
    inbox.commitRead('main','read',[{type:'text',text:rendered}],false,5);
    expect(inbox.threadForTurn('main',5,'c_chat')).toBe('request');
    expect(inbox.threadForTurn('main',6,'c_chat')).toBeUndefined();
    expect(inbox.threadForTurn('main',5,'elsewhere')).toBeUndefined();
  } finally {inbox.close();}
});

it('wakes a followed PA observation without changing observer identity or owner-only scope', () => {
  const input={...topic, metadata:{...topic.metadata,personal_delivery:'observer',pa_observation:true,context_only:true}};
  const agent={agentId:'alice',mode:'global' as const,provider:'test',model:'test',revision:'1'};
  expect(chatDelivery(input,agent,'owner')).toBe('high');
  expect(chatDelivery(input,{...agent,collaborationScope:'owner_only'},'owner')).toBe('skip');
  expect(chatDelivery({...input,metadata:{...input.metadata,thread_root_message_id:undefined}},agent,'owner')).toBe('background');
});

it.each([true,false])('routes automatic text by the confirmed request topic after streaming began (sent=%s)',async sent=>{
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
    const args={target:'current',text:'开始核对',in_thread_of:'request'};
    events.push({seq:2,time:2,type:'tool/call',data:{turn:1,callId:'send',name:'send_message',arguments:JSON.stringify(args)}});
    const sending=tools.call({method:'send_message',args,operationId:'session:send',callId:'send',sessionId:'session',rootSessionId:'session',agentId:'alice',ownerId:'owner'});
    if(sent)expect(await sending).toMatchObject({status:'sent'});else await expect(sending).rejects.toThrow('not accepted');
    events.push({seq:3,time:3,type:'assistant/message',data:{turn:1,message:{id:'result',content:[{type:'text',text:'3 辆'}]}}},
      {seq:4,time:4,type:'turn/end',data:{turn:1,reason:{kind:'completed'}}});
    await single.recover();
    expect(frames.some(frame=>frame.kind==='message_discarded'&&frame.message_id==='main-output')).toBe(sent);
    expect(frames.some(frame=>frame.kind==='turn_start'&&frame.thread_root_message_id==='request')).toBe(sent);
    expect(frames.find(frame=>frame.kind==='message_completed')).toMatchObject({message_id:sent?'topic-output':'main-output',final_content:'3 辆'});
  }finally{await single.stop();await tools.stop();inbox.close();store.close();}
});

it('defaults a Global send to the ingested topic only during its own turn', async () => {
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  store.bind({agentId:'alice',sessionId:'main',conversationId:'global:alice',ownerId:'owner',revision:'1',cwd:'/tmp'});
  const publications:Record<string,unknown>[]=[];
  const product=new GlobalAgent({nodeId:'n',ownerId:'owner',store,inbox,
    agents:[{agentId:'alice',workspace:'/tmp',revision:'1',provider:'test',model:'test',mode:'global'}],
    runtime:{onNotification:()=>()=>{},async request(method){return method==='session.work.children'?{children:[]}:{events:[],durable:true,status:'idle'};}},
    relay:{async request(type,payload){
      if(type==='agent.message'){publications.push(payload);return {type:'ack',payload:{message_id:String(publications.length),conversation_id:'c_chat'}};}
      return {type:'ack',payload:{ok:true,result:{type:'group',channel:'web',target:'c_chat'}}};
    }},image:async()=>'',onError:error=>{throw error;}});
  try {
    inbox.receive(topic,true);
    const page=inbox.read('alice','main','read',{target:'c_chat'});
    inbox.commitRead('main','read',[{type:'text',text:JSON.stringify(page)}],false,3);
    for (const turn of [3,4]) {
      const callId='send-'+turn;
      store.recordEvents('main',[{seq:turn,time:turn,type:'tool/call',data:{turn,callId,name:'send_message',arguments:'{}'}}]);
      const call={method:'send_message',args:{target:'c_chat',text:'收到'},sessionId:'main',rootSessionId:'main',ownerId:'owner',agentId:'alice',operationId:'main:'+callId,callId};
      expect(await product.call(call)).toMatchObject({status:'sent'});
      expect(await product.call(call)).toMatchObject({status:'sent'});
    }
    expect(publications.map(item=>item.in_thread_of)).toEqual(['request',undefined]);
  } finally {await product.stop();inbox.close();store.close();}
});
