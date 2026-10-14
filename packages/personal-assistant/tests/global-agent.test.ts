import { expect, it } from 'vitest';
import { NodeStore } from '../src/store.js';
import { InboxStore } from '../src/inbox.js';
import { GlobalAgent, type ProductCall } from '../src/global-agent.js';
import type { RelayInput } from '@nano/product-contracts';

it.each([
  ['owner-id', 'user:owner', undefined, 'owner'],
  ['owner-web', 'conversation:c_owner', {type:'direct',channel:'web',members:[{type:'user',user_id:'owner'},{type:'agent',user_id:'agent-account'}]}, 'owner'],
  ['other-web', 'c_other', {type:'direct',channel:'web',members:[{type:'user',user_id:'other'},{type:'agent',user_id:'agent-account'}]}, 'user'],
  ['owner-group', 'c_group', {type:'group',channel:'web',members:[{type:'user',user_id:'owner'},{type:'agent',user_id:'agent-account'}]}, 'group'],
  ['owner-feishu', 'external:owner', {type:'direct',channel:'feishu',owner_recipient:true}, 'owner'],
  ['other-feishu-shadow', 'c_shadow', {type:'direct',channel:'feishu',owner_recipient:false,members:[{type:'user',user_id:'owner'},{type:'agent',user_id:'agent-account'}]}, 'user'],
  ['unmapped-feishu', 'external:unknown', {type:'direct',channel:'feishu'}, 'user'],
  ['unknown', 'c_unknown', undefined, 'unknown'],
] as const)('resolves %s message review identity from trusted product facts without sending', async (_label, target, info, expected) => {
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  store.bind({agentId:'a',sessionId:'main',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
  let sends=0;
  const product=new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[],store,inbox,
    runtime:{onNotification:()=>()=>{},request:async()=>({})},relay:{async request(type){
      if(type==='agent.message')sends++;
      if(!info)throw new Error('No accessible target');
      return {type:'conversation.query.result',payload:{ok:true,result:info}};
    }},image:async()=>'',onError:()=>{}});
  const call:ProductCall={method:'send_message.context',args:{target,owner_recipient:true},operationId:'review',callId:'send',sessionId:'main',rootSessionId:'main',agentId:'a',ownerId:'owner'};
  try{
    expect(await product.call(call)).toMatchObject({target,sender:{type:'agent',agent_id:'a'},recipient:{kind:expected}});
    expect(sends).toBe(0);
    await expect(product.call({...call,ownerId:'other'})).rejects.toThrow('identity');
  }finally{await product.stop();inbox.close();store.close();}
});

it.each([
  { label: 'Web group', type: 'group', channel: 'web', requested: 'c_group', incoming: 'c_group', resolved: 'c_group' },
  { label: 'Web direct', type: 'direct', channel: 'web', requested: 'c_direct', incoming: 'c_direct', resolved: 'c_direct' },
  { label: 'Feishu direct', type: 'direct', channel: 'feishu', requested: 'external:direct', incoming: 'external:direct', resolved: 'external:direct' },
  { label: 'Feishu shadow reply', type: 'direct', channel: 'feishu', requested: 'c_shadow', incoming: 'external:direct', resolved: 'external:direct' },
  { label: 'Feishu external reply to shadow input', type: 'direct', channel: 'feishu', requested: 'external:direct', incoming: 'c_shadow', resolved: 'external:direct' },
])('holds a $label draft before dispatch until newer input is read, preserving tool identity', async ({ type: conversationType, channel, requested, incoming, resolved }) => {
  const store = new NodeStore(':memory:', 'owner'); const inbox = new InboxStore(':memory:');
  const binding = store.bind({ agentId: 'alice', sessionId: 'main', conversationId: 'global:alice', ownerId: 'owner', cwd: '/tmp/alice', revision: '1' });
  store.aliasConversation('alice', 'c_shadow', 'external:direct');
  let sent = 0;
  const input: RelayInput = { agent_id: 'alice', conversation_id: incoming, relay_task_id: 'relay', idempotency_key: 'correction', metadata: { conversation_type: conversationType }, message: { id: 'correction', content: 'Change the date', sender_type: 'user', sender_user_id: 'human', attachments: [] } };
  const product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [{ agentId: 'alice', workspace: '/tmp/alice', revision: '1', provider: 'test', model: 'test', mode: 'global' }], store, inbox,
    runtime: { onNotification: () => () => {}, request: async method => method === 'session.descendants' ? [] : ({ events: [], durable: true, status: 'idle' }) },
    relay: { request: async (type, payload) => {
      if (type === 'agent.work.append') return { type: 'agent.work.ack', payload: { through_seq: (payload.events as { seq: number }[]).at(-1)!.seq } };
      if (type === 'conversation.query') { inbox.receive(input, true); return { type: 'conversation.query.result', payload: { ok: true, result: { type: conversationType, channel, target: resolved, name: 'Conversation' } } }; }
      if (type === 'agent.message') sent++;
      return { type: 'ack', payload: { message_id: 'sent-message', conversation_id: 'c_group' } };
    } }, image: async () => '', onError: error => { throw error; },
  });
  const call: ProductCall = { method: 'send_message', args: { target: requested, text: 'old draft' }, operationId: 'main:call', callId: 'call', sessionId: binding.sessionId, rootSessionId: binding.sessionId, agentId: 'alice', ownerId: 'owner' };
  try {
    expect(await product.call(call)).toMatchObject({ status: 'held_for_revalidation', inbox_targets: [incoming] });
    expect(sent).toBe(0);
    const page = inbox.read('alice', 'main', 'read', { target: incoming });
    inbox.commitRead('main', 'read', [{ type: 'text', text: JSON.stringify(page) }], false);
    expect(await product.call(call)).toMatchObject({ status: 'held_for_revalidation' });
    expect(sent).toBe(0);
    inbox.receive({ ...input, conversation_id: 'c_other', message: { ...input.message, id: 'other-chat' } }, true);
    inbox.receive({ ...input, message: { ...input.message, id: 'background' } }, false);
    expect(await product.call({ ...call, operationId: 'main:reconsidered', callId: 'reconsidered', args: { target: requested, text: 'new draft' } })).toMatchObject({ status: 'sent' });
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
    { seq: 3, time: 3, type: 'request/header', data: { header: { config: { model: 'actual-model' } } } },
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


it.each(['global', 'single_thread'] as const)('forwards approved %s task deletion without collecting another human confirmation', async mode => {
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  const binding = store.bind({agentId:'a',sessionId:'main',conversationId:mode==='global'?'global:a':'chat',ownerId:'owner',cwd:'/tmp',revision:'1'});
  const sent: Record<string, unknown>[] = [];
  const product = new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[{agentId:'a',workspace:'/tmp',revision:'1',provider:'p',model:'m',mode}],store,inbox,
    runtime:{onNotification:()=>()=>{},request:async method=>method==='session.descendants'?[]:{events:[],durable:true,status:'idle'}},
    relay:{request:async(type,payload)=>{if(type==='task_graph.command')sent.push(payload);return{type:'ack',payload:{ok:true,result:{deleted_ids:['n2']}}};}},image:async()=>'',onError:error=>{throw error;}});
  const args={action:'delete',graph_id:'graph',node_id:'n2',base_revision:3,request_key:'delete-child'};
  try {
    expect(await product.call({method:'task_graph',args,operationId:'main:delete',callId:'delete',sessionId:binding.sessionId,rootSessionId:binding.sessionId,agentId:'a',ownerId:'owner'})).toMatchObject({ok:true,result:{deleted_ids:['n2']}});
    expect(sent).toHaveLength(1);
    expect(sent[0]).not.toHaveProperty('source_message_ids');
    expect(sent[0]).toMatchObject({action:'delete',args:{graph_id:'graph',node_id:'n2',base_revision:3,request_key:'delete-child'}});
  } finally {await product.stop();inbox.close();store.close();}
});

it.each([
  { mode: 'global', conversationId: 'global:a', target: undefined, expected: undefined },
  { mode: 'global', conversationId: 'global:a', target: 'current', expected: undefined },
  { mode: 'global', conversationId: 'global:a', target: 'conversation:c_existing', expected: 'c_existing' },
  { mode: 'single_thread', conversationId: 'c_bound', target: undefined, expected: 'c_bound' },
  { mode: 'single_thread', conversationId: 'c_bound', target: 'current', expected: 'c_bound' },
  { mode: 'single_thread', conversationId: 'external:feishu:chat', target: undefined, expected: undefined },
  { mode: 'single_thread', conversationId: 'external:feishu:mapped', target: undefined, expected: 'c_shadow' },
] as const)('resolves task creation ownership from $mode / $conversationId / $target', async ({ mode, conversationId, target, expected }) => {
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  const binding = store.bind({ agentId: 'a', sessionId: 'main', conversationId, ownerId: 'owner', cwd: '/tmp', revision: '1' });
  store.aliasConversation('a', 'c_shadow', 'external:feishu:mapped');
  const sent: Record<string, unknown>[] = [];
  const product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [{ agentId: 'a', workspace: '/tmp', revision: '1', provider: 'p', model: 'm', mode }], store, inbox,
    runtime: { onNotification: () => () => {}, request: async method => method === 'session.descendants' ? [] : { events: [], durable: true, status: 'idle' } },
    relay: { request: async (type, payload) => { if (type === 'task_graph.command') sent.push(payload); return { type: 'ack', payload: { ok: true, result: { graph_id: 'tg_created' } } }; } }, image: async () => '', onError: error => { throw error; } });
  try {
    const result = await product.call({ method: 'task_graph', args: { action: 'create', title: 'Goal', mode: 'dag', request_key: 'create', ...(target ? { target } : {}) }, operationId: 'main:create', callId: 'create', sessionId: binding.sessionId, rootSessionId: binding.sessionId, agentId: 'a', ownerId: 'owner' });
    if (expected) {
      expect(result).toMatchObject({ ok: true });
      expect(sent).toEqual([expect.objectContaining({ agent_id: 'a', args: expect.objectContaining({ conversation_id: expected }) })]);
    } else {
      expect(result).toMatchObject({ ok: false, error: { code: 'conversation_required' } });
      expect(sent).toEqual([]);
    }
  } finally { await product.stop(); inbox.close(); store.close(); }
});

it('forwards conversation discovery and membership actions with the registered identity and rejects child calls', async () => {
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  store.bind({ agentId: 'a', sessionId: 'main', conversationId: 'global:a', ownerId: 'owner', cwd: '/tmp', revision: '1' });
  const sent: Record<string, unknown>[] = [];
  const product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [], store, inbox,
    runtime: { onNotification: () => () => {}, request: async () => ({}) },
    relay: { request: async (_type, payload) => { sent.push(payload); return { type: 'conversation.query.result', payload: { ok: true, result: { id: 'c_group' } } }; } }, image: async () => '', onError: error => { throw error; } });
  const call: ProductCall = { method: 'conversations', args: {}, operationId: 'main:query', callId: 'query', sessionId: 'main', rootSessionId: 'main', agentId: 'a', ownerId: 'owner' };
  try {
    for (const args of [{ action: 'create', type: 'group', title: 'Team', visibility: 'public', participant_ids: ['user'] }, { action: 'join', target: 'c_group' }, { action: 'list', scope: 'public' }]) {
      await product.call({ ...call, args: { ...args, agent_id: 'forged', node_id: 'forged' } });
      expect(sent.at(-1)).toMatchObject({ ...args, agent_id: 'a', node_id: 'node', session_id: 'main' });
      await expect(product.call({ ...call, args, sessionId: 'child' })).rejects.toThrow('main Agent');
    }
    expect(sent).toHaveLength(3);
  } finally { await product.stop(); inbox.close(); store.close(); }
});

it.each([
  { policy: 'mention_only', mentioned: false, attention: false },
  { policy: 'mention_only', mentioned: true, attention: true },
  { policy: 'always', mentioned: false, attention: true },
] as const)('retains system task messages under $policy and wakes only with attention ($mentioned)', async ({ policy, mentioned, attention }) => {
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  const submitted: Record<string, unknown>[] = []; let status = 'running', cancellations = 0;
  const product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [{ agentId: 'a', workspace: '/tmp', revision: '1', provider: 'p', model: 'm', mode: 'global', groupReplyPolicy: policy }], store, inbox,
    runtime: { onNotification: () => () => {}, request: async (method, value) => {
      if (method === 'session.submit') submitted.push(value as Record<string, unknown>);
      if (method === 'session.cancel') { cancellations++; return { wasRunning: true }; }
      return method === 'session.descendants' ? [] : { events: [], durable: true, status };
    } }, relay: { request: async (type, payload) => ({ type: 'ack', payload: type === 'agent.work.append' ? { through_seq: (payload.events as { seq: number }[]).at(-1)!.seq } : {} }) }, image: async () => '', onError: error => { throw error; } });
  const input: RelayInput = { agent_id: 'a', conversation_id: 'c_group', relay_task_id: 'task-event', idempotency_key: 'task-event', metadata: { conversation_type: 'group', mentioned_agent_ids: mentioned ? ['a'] : [] }, message: { id: 'task-event', content: 'Assignment changed <mention type="user" target_id="a"/>', sender_type: 'system', sender_user_id: 'actor', attachments: [] } };
  try {
    await product.receive(input); await product.receive(input);
    expect(submitted).toEqual([]);
    expect(inbox.check('a').sources).toEqual([expect.objectContaining({ unread: 1, requires_attention: attention })]);
    expect(inbox.read('a', 'main', 'read', { target: 'c_group' })).toMatchObject({ messages: [{ id: 'task-event', sender: { type: 'system' } }] });
    status = 'idle'; await product.recover(); await product.receive(input);
    expect(submitted).toHaveLength(attention ? 1 : 0);
    if (attention) expect(submitted[0]).toMatchObject({ mode: 'followup', source: { kind: 'system' }, inputId: expect.stringMatching(/^inbox-wake:a:/) });
    await product.receive({ ...input, message: { ...input.message, id: 'stop', content: '/stop', sender_type: 'user' } });
    expect(cancellations).toBe(1);
    await product.receive({ ...input, idempotency_key: 'after-stop', relay_task_id: 'after-stop', message: { ...input.message, id: 'after-stop' } });
    expect(submitted).toHaveLength(attention ? 2 : 0);
  } finally { await product.stop(); inbox.close(); store.close(); }
});
