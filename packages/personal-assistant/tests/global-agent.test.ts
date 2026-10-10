import { expect, it } from 'vitest';
import { NodeStore } from '../src/store.js';
import { InboxStore } from '../src/inbox.js';
import { GlobalAgent, type ProductCall } from '../src/global-agent.js';
import type { RelayInput } from '@nano/product-contracts';

it('holds a group draft when a correction arrives before dispatch and keeps tool identity idempotent', async () => {
  const store = new NodeStore(':memory:', 'owner'); const inbox = new InboxStore(':memory:');
  const binding = store.bind({ agentId: 'alice', sessionId: 'main', conversationId: 'global:alice', ownerId: 'owner', cwd: '/tmp/alice', revision: '1' });
  let sent = 0;
  const input: RelayInput = { agent_id: 'alice', conversation_id: 'c_group', relay_task_id: 'relay', idempotency_key: 'correction', metadata: { conversation_type: 'group' }, message: { id: 'correction', content: 'Change the date', sender_type: 'user', sender_user_id: 'human', attachments: [] } };
  const product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [{ agentId: 'alice', workspace: '/tmp/alice', revision: '1', provider: 'test', model: 'test', mode: 'global' }], store, inbox,
    runtime: { onNotification: () => () => {}, request: async method => method === 'session.descendants' ? [] : ({ events: [], durable: true, status: 'idle' }) },
    relay: { request: async (type, payload) => {
      if (type === 'agent.work.append') return { type: 'agent.work.ack', payload: { through_seq: (payload.events as { seq: number }[]).at(-1)!.seq } };
      if (type === 'conversation.query') { inbox.receive(input, true); return { type: 'conversation.query.result', payload: { ok: true, result: { type: 'group', channel: 'web', name: 'Group' } } }; }
      if (type === 'agent.message') sent++;
      return { type: 'ack', payload: { message_id: 'sent-message', conversation_id: 'c_group' } };
    } }, image: async () => '', onError: error => { throw error; },
  });
  const call: ProductCall = { method: 'send_message', args: { target: 'c_group', text: 'old draft' }, operationId: 'main:call', callId: 'call', sessionId: binding.sessionId, rootSessionId: binding.sessionId, agentId: 'alice', ownerId: 'owner' };
  try {
    expect(await product.call(call)).toMatchObject({ status: 'held_for_revalidation' });
    expect(sent).toBe(0);
    const page = inbox.read('alice', 'main', 'read', { target: 'c_group' });
    inbox.commitRead('main', 'read', [{ type: 'text', text: JSON.stringify(page) }], false);
    expect(await product.call(call)).toMatchObject({ status: 'held_for_revalidation' });
    expect(sent).toBe(0);
    expect(await product.call({ ...call, operationId: 'main:reconsidered', callId: 'reconsidered', args: { target: 'c_group', text: 'new draft' } })).toMatchObject({ status: 'sent' });
    expect(sent).toBe(1);
    await expect(product.call({ ...call, agentId: 'bob' })).rejects.toThrow('identity');
    await expect(product.call({ ...call, method: 'inbox', sessionId: 'child', args: { action: 'check' } })).rejects.toThrow('main Agent');
  } finally { await product.stop(); inbox.close(); store.close(); }
});

it('projects durable native child lineage and drafts into Work without a public send', async () => {
  const store = new NodeStore(':memory:', 'owner'); const inbox = new InboxStore(':memory:'); let sends = 0;
  const childEvents = [
    { seq: 1, time: 1, type: 'turn/start', data: { turn: 1 } },
    { seq: 2, time: 2, type: 'user/message', data: { source: { kind: 'subagent' } } },
    { seq: 3, time: 3, type: 'request/context', data: { model: 'actual-model' } },
    { seq: 4, time: 4, type: 'assistant/message', data: { turn: 1, message: { id: 'draft', content: [{ type: 'text', text: 'private child draft' }] } } },
    { seq: 5, time: 5, type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
  ];
  const product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [{ agentId: 'alice', workspace: '/tmp/alice', revision: '1', provider: 'test', model: 'test', mode: 'global' }], store, inbox,
    runtime: { onNotification: () => () => {}, async request(method, value) {
      if (method === 'session.descendants') return [{ kind: 'child', id: 'child', parentId: (value as { sessionId: string }).sessionId, label: 'Research', events: childEvents, throughSeq: 5 }];
      return { events: [], durable: true, status: 'idle' };
    } }, relay: { ready: false, async request() { sends++; return { type: 'ack', payload: {} }; } }, image: async () => '', onError: () => {},
  });
  try {
    await product.recover(); await product.recover();
    const events = inbox.journal(0);
    expect(events.filter(event => event.session_id === 'child' && event.type === 'session_registered')).toEqual([expect.objectContaining({ payload: expect.objectContaining({ scope: 'subagent', child_agent_id: 'child', title: 'Research' }) })]);
    expect(events.filter(event => event.session_id === 'child' && event.type === 'message')).toHaveLength(1);
    expect(events.filter(event => event.session_id === 'child' && event.type === 'model_selected')).toEqual([expect.objectContaining({ turn_id: '1', payload: { model: 'actual-model' } })]);
    expect(events.some(event => event.type === 'message_sent')).toBe(false); expect(sends).toBe(0);
  } finally { await product.stop(); inbox.close(); store.close(); }
});

it('holds a single-thread same-group tool send until the accepted correction is consumed', async () => {
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  const binding=store.bind({agentId:'a',sessionId:'chat',conversationId:'c_group',ownerId:'owner',cwd:'/tmp',revision:'1'});
  const input=(id:string):RelayInput=>({agent_id:'a',conversation_id:'c_group',relay_task_id:id,idempotency_key:id,metadata:{conversation_type:'group'},message:{id,content:id,sender_type:'user',sender_user_id:'owner',attachments:[]}});
  store.receive('chat',input('original'));store.inputEvidence('a:original',{accepted:true,turn:1});
  let corrected=false,sends=0;
  const product=new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[{agentId:'a',workspace:'/tmp',revision:'1',provider:'p',model:'m',mode:'single_thread'}],store,inbox,
    runtime:{onNotification:()=>()=>{},async request(method,value){
      if(method==='session.descendants')return [];
      if(method==='session.lookup')return {accepted:true,...((value as any).inputId==='a:original'?{turn:1}:corrected?{turn:2}:{})};
      return {durable:true,events:[{seq:corrected?2:1,time:1,type:'tool/call',data:{turn:corrected?2:1,callId:corrected?'new':'old'}}],status:'running'};
    }},relay:{async request(type,payload){
      if(type==='conversation.query'){if(!corrected)store.receive('chat',input('correction'));return {type:'conversation.query.result',payload:{ok:true,result:{type:'group',channel:'web'}}};}
      if(type==='agent.work.append')return {type:'agent.work.ack',payload:{through_seq:(payload.events as any[]).at(-1).seq}};
      if(type==='agent.message'){sends++;expect(payload.to).toBe('conversation:c_group');}
      return {type:'ack',payload:{message_id:'sent',conversation_id:'c_group'}};
    }},image:async()=>'',onError:()=>{}});
  const call:ProductCall={method:'send_message',args:{target:'current',text:'old'},operationId:'chat:old',callId:'old',sessionId:'chat',rootSessionId:'chat',agentId:'a',ownerId:'owner'};
  try{
    expect(await product.call(call)).toMatchObject({status:'held_for_revalidation'});expect(sends).toBe(0);
    corrected=true;
    expect(await product.call({...call,args:{target:'current',text:'new'},operationId:'chat:new',callId:'new'})).toMatchObject({status:'sent'});expect(sends).toBe(1);
    expect(await product.call(call)).toMatchObject({status:'held_for_revalidation'});expect(sends).toBe(1);
  }finally{await product.stop();inbox.close();store.close();}
});
