import { expect, it } from 'vitest';
import type { RelayInput, RuntimeEvent } from '@nano/product-contracts';
import { NodeStore } from '../src/store.js';
import { SingleThread } from '../src/single-thread.js';

it('supplies local message time to the model without rewriting the human body', async () => {
  const store = new NodeStore(':memory:', 'owner');
  const submitted: any[] = [];
  const product = new SingleThread({ nodeId: 'node', ownerId: 'owner', store,
    agents: [{ agentId: 'a', revision: '1', mode: 'single_thread', provider: 'test', model: 'test', workspace: '/tmp' }],
    runtime: { onNotification: () => () => {}, async request(method, value) {
      if (method === 'session.submit') submitted.push(value);
      if (method === 'session.lookup') return { accepted: submitted.some(input => input.inputId === (value as any).inputId) };
      return { events: [], durable: true };
    } },
    relay: { async request() { return { type: 'ack', payload: {} }; } }, image: async () => '', onError: error => { throw error; },
  });
  const input: RelayInput = { agent_id: 'a', conversation_id: 'c', relay_task_id: 'morning', idempotency_key: 'morning',
    metadata: { conversation_type: 'direct', channel: 'web_relay' }, message: { id: 'morning', content: '早，今天有什么安排？',
      created_at: '2026-10-14T01:00:00Z', timezone: 'Asia/Shanghai', sender_type: 'user', sender_user_id: 'owner', attachments: [] } };
  try {
    await product.receive(input);
    expect(submitted[0].content).toEqual([
      { type: 'text', text: 'Message time: 2026-10-14T09:00:00+08:00 (Asia/Shanghai); source: Web IM.' },
      { type: 'text', text: input.message.content },
    ]);
    expect(store.inputs(store.bindingFor('a', 'c')!.sessionId)[0]!.input.message.content).toBe(input.message.content);
  } finally { await product.stop(); store.close(); }
});

it.each(['user', 'system'])('parks %s group background, admits it on mention once, and suppresses silent replies', async senderType => {
  const store = new NodeStore(':memory:', 'owner');
  const submitted: Record<string, unknown>[] = []; const frames: Record<string, unknown>[] = [];
  let ensured = 0; let events: RuntimeEvent[] = [];
  let notify: (method: string, value: unknown) => void = () => {};
  const product = new SingleThread({ nodeId: 'node', ownerId: 'owner', store,
    agents: [{ agentId: 'a', revision: '1', mode: 'single_thread', provider: 'test', model: 'test', workspace: '/tmp' }],
    runtime: { onNotification(listener) { notify = listener; return () => {}; }, async request(method, value) {
      const args = value as Record<string, unknown>;
      if (method === 'session.ensure') ensured++;
      if (method === 'session.submit') submitted.push(args);
      if (method === 'session.lookup') return { accepted: submitted.some(input => input.inputId === args.inputId), ...(submitted.some(input => input.mode === 'followup') ? { turn: 1 } : {}) };
      return { durable: true, events };
    } }, relay: { async request(_type, payload) { frames.push(payload); return { type: 'ack', payload: { message_id: 'bubble' } }; } },
    image: async () => '', onError: error => { throw error; },
  });
  const input = (id: string, mentioned = false): RelayInput => ({ agent_id: 'a', conversation_id: 'group', relay_task_id: id, idempotency_key: id,
    metadata: { conversation_type: 'group', mentioned_agent_ids: mentioned ? ['a'] : [] },
    message: { id, content: id, sender_user_id: 'human', sender_type: senderType, attachments: [] } });
  try {
    await product.receive(input('background'));
    expect(ensured).toBe(0); expect(submitted).toHaveLength(0);
    await product.recover(); expect(ensured).toBe(0);
    await product.receive(input('mention', true));
    expect(submitted.map(input => [input.inputId, input.mode])).toEqual([['a:background', 'inject'], ['a:mention', 'followup']]);
    await product.receive(input('mention', true)); expect(submitted).toHaveLength(2);
    const sessionId = store.bindingFor('a', 'group')!.sessionId;
    const live = store.prepareDelivery(sessionId, 1);
    store.updateDelivery(live.operationId, 'sending', 'bubble', '');
    notify('session.liveness', {sessionId});
    expect(frames.filter(frame => frame.kind === 'run_heartbeat')).toEqual([expect.objectContaining({message_id:'bubble',source:'dsh-agent'})]);
    store.updateDelivery(live.operationId, 'confirmed', 'bubble', '');
    notify('session.liveness', {sessionId});
    expect(frames.filter(frame => frame.kind === 'run_heartbeat')).toHaveLength(1);
    store.updateDelivery(live.operationId, 'sending', 'bubble', '');
    notify('session.stream', { sessionId, frame: { type: 'start', attemptId: 'attempt', turn: 1 } });
    notify('session.stream', { sessionId, frame: { type: 'chunk', attemptId: 'attempt', chunk: { type: 'text-delta', text: 'NO_' } } });
    events = [{ seq: 1, time: 1, type: 'assistant/message', data: { turn: 1, message: { id: 'answer', content: [{ type: 'text', text: 'NO_REPLY' }] } } },
      { seq: 2, time: 2, type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } }];
    await product.recover();
    expect(frames.some(frame => frame.kind === 'message_delta')).toBe(false);
    expect(frames.some(frame => frame.kind === 'message_completed' && frame.final_content === 'NO_REPLY')).toBe(false);
    expect(frames.filter(frame => frame.kind === 'message_discarded')).toHaveLength(1);
  } finally { await product.stop(); store.close(); }
});

it.each(['user', 'system'])('withholds a group draft when an accepted %s correction is waiting and publishes the revised turn', async senderType => {
  const store = new NodeStore(':memory:', 'owner'); const frames: Record<string, unknown>[] = []; const submitted: Record<string, unknown>[] = [];
  let events: RuntimeEvent[] = []; let correctionConsumed = false;
  const product = new SingleThread({ nodeId: 'node', ownerId: 'owner', store,
    agents: [{ agentId: 'a', revision: '1', mode: 'single_thread', provider: 'test', model: 'test', workspace: '/tmp', groupReplyPolicy: 'always' }],
    runtime: { onNotification() { return () => {}; }, async request(method, value) {
      const args = value as Record<string, unknown>;
      if (method === 'session.submit') submitted.push(args);
      if (method === 'session.lookup') return { accepted: submitted.some(input => input.inputId === args.inputId), ...(args.inputId === 'a:first' ? { turn: 1 } : correctionConsumed ? { turn: 2 } : {}) };
      return { durable: true, events };
    } }, relay: { async request(_type, payload) { frames.push(payload); return { type: 'ack', payload: { message_id: String(payload.idempotency_key) } }; } }, image: async () => '', onError: () => {},
  });
  const input = (id: string): RelayInput => ({ agent_id: 'a', conversation_id: 'group', relay_task_id: id, idempotency_key: id, metadata: { conversation_type: 'group' }, message: { id, content: id, sender_type: senderType, sender_user_id: 'human', attachments: [] } });
  try {
    await product.receive(input('first'));
    events = [{ seq: 1, time: 1, type: 'assistant/message', data: { turn: 1, message: { id: 'draft', content: [{ type: 'text', text: 'Thursday' }] } } }, { seq: 2, time: 2, type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } }];
    await product.receive(input('correction'));
    expect(frames.some(frame => frame.kind === 'message_completed' && frame.final_content === 'Thursday')).toBe(false);
    expect(frames.some(frame => frame.kind === 'reply_process' && (frame.item as Record<string, unknown>).text === 'Thursday')).toBe(true);
    correctionConsumed = true;
    events.push({ seq: 3, time: 3, type: 'assistant/message', data: { turn: 2, message: { id: 'revised', content: [{ type: 'text', text: 'Friday' }] } } }, { seq: 4, time: 4, type: 'turn/end', data: { turn: 2, reason: { kind: 'completed' } } });
    await product.recover();
    expect(frames.some(frame => frame.kind === 'message_completed' && frame.final_content === 'Friday')).toBe(true);
  } finally { await product.stop(); store.close(); }
});

it('starts a fresh context for /new without submitting the command as a model prompt or resetting twice', async () => {
  const store = new NodeStore(':memory:', 'owner'); const submitted: string[] = []; const frames: Record<string, unknown>[] = [];
  const product = new SingleThread({ nodeId: 'node', ownerId: 'owner', store,
    agents: [{ agentId: 'a', revision: '2', mode: 'single_thread', provider: 'p', model: 'm', workspace: '/tmp' }],
    runtime: { onNotification: () => () => {}, async request(method, value) {
      if (method === 'session.submit') submitted.push((value as { inputId: string }).inputId);
      if (method === 'session.lookup') return { accepted: false };
      return { durable: true, events: [], wasRunning: false };
    } }, relay: { async request(_type, payload) { frames.push(payload); return { type: 'ack', payload: { message_id: 'reply' } }; } }, image: async () => '', onError: () => {},
  });
  const input = (id: string, content: string): RelayInput => ({ agent_id: 'a', conversation_id: 'c', relay_task_id: id, idempotency_key: id, metadata: { conversation_type: 'direct' }, message: { id, content, sender_type: 'user', sender_user_id: 'owner', attachments: [] } });
  try {
    await product.receive(input('before', 'remember old context')); const before = store.bindingFor('a', 'c')!;
    await product.receive(input('new', '/new')); const after = store.bindingFor('a', 'c')!;
    expect(after.sessionId).not.toBe(before.sessionId);
    expect(store.bindings().find(row => row.sessionId === before.sessionId)?.conversationId).toBe('c');
    await product.receive(input('new', '/new'));
    expect(store.bindingFor('a', 'c')?.sessionId).toBe(after.sessionId);
    expect(store.canonical('a')?.sessionId).toBe(after.sessionId);
    expect(submitted).toEqual(['a:before']);
    expect(frames.some(frame => frame.final_content === '已开始新会话。')).toBe(true);
  } finally { await product.stop(); store.close(); }
});

it('holds later input behind a compact command and never treats the focus as model input', async () => {
  const store = new NodeStore(':memory:', 'owner'); const calls: { method: string; args: Record<string, unknown> }[] = [];
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
  const product = new SingleThread({ nodeId:'node',ownerId:'owner',store,agents:[{agentId:'a',revision:'1',mode:'single_thread',provider:'p',model:'m',workspace:'/tmp'}],
    runtime:{onNotification:()=>()=>{},request:async(method,value)=>{const args=value as Record<string,unknown>;calls.push({method,args});if(method==='session.command'){await gate;return{text:'已压缩原会话。'};}if(method==='session.lookup')return{accepted:false};return{durable:true,events:[]};}},
    relay:{request:async()=>({type:'ack',payload:{message_id:'control'}})},image:async()=>'',onError:()=>{},
  });
  const input=(id:string,content:string):RelayInput=>({agent_id:'a',conversation_id:'chat',relay_task_id:id,idempotency_key:id,metadata:{conversation_type:'direct'},message:{id,content,sender_type:'user',sender_user_id:'owner',attachments:[]}});
  try{
    const compact=product.receive(input('compact','/compact 保留认证方案'));
    const later=product.receive(input('later','Continue after compaction'));
    await expect.poll(()=>calls.filter(call=>call.method==='session.command').length).toBe(1);
    expect(calls.some(call=>call.method==='session.submit')).toBe(false);
    release();await compact;await later;
    expect(calls.filter(call=>call.method==='session.submit').map(call=>call.args.inputId)).toEqual(['a:later']);
    expect(calls.find(call=>call.method==='session.command')?.args.argument).toBe('保留认证方案');
    await product.receive(input('compact','/compact 保留认证方案'));
    expect(calls.filter(call=>call.method==='session.command')).toHaveLength(1);
  }finally{release();await product.stop();store.close();}
});

it('keeps the approval identity inside a resolution independently of transport request correlation',async()=>{
 const store=new NodeStore(':memory:','owner'),frames:Record<string,unknown>[]=[];let notify:(method:string,payload:unknown)=>void=()=>{};
 const binding=store.bind({agentId:'a',sessionId:'approval-main',conversationId:'chat',ownerId:'owner',revision:'1',cwd:'/tmp'});
 store.receive(binding.sessionId,{agent_id:'a',conversation_id:'chat',relay_task_id:'input',idempotency_key:'input',metadata:{conversation_type:'direct'},message:{id:'m',content:'run',sender_type:'user',sender_user_id:'owner',attachments:[]}});
 const product=new SingleThread({nodeId:'n',ownerId:'owner',agents:[{agentId:'a',revision:'1',workspace:'/tmp',mode:'single_thread',provider:'test',model:'test'}],store,
 runtime:{onNotification(listener){notify=listener;return()=>{};},async request(method){return method==='session.lookup'?{accepted:true,turn:1}:{durable:true,events:[]};}},
 relay:{async request(_type,payload){frames.push(payload);return {type:'ack',payload:{message_id:'bubble'}};}},image:async()=>'',onError:()=>{}});
 try{
  notify('approval.request',{sessionId:binding.sessionId,requestId:'original-permission',toolName:'bash',callId:'tool'});
  await expect.poll(()=>frames.some(p=>p.kind==='permission_request')).toBe(true);
  notify('approval.resolved',{sessionId:binding.sessionId,requestId:'original-permission',outcome:'timed-out'});
  await expect.poll(()=>frames.find(p=>p.kind==='permission_resolved')).toMatchObject({permission_request:{request_id:'original-permission'},decision:'timed-out'});
 }finally{await product.stop();store.close();}
});

it.each([{interactive:true,found:true,same:true},{interactive:false,found:true,same:true},{interactive:false,found:true,same:false},{interactive:false,found:false,same:true}])('suppresses closing sentinel only for a confirmed bound-chat send: %j',async({interactive,found,same})=>{
 const {GlobalAgent}=await import('../src/global-agent.js'),{InboxStore}=await import('../src/inbox.js'),{RelayDeliveryError}=await import('@nano/channels');
 const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:'),frames:Record<string,unknown>[]=[];
 store.bind({agentId:'a',sessionId:'main',conversationId:'chat',ownerId:'owner',revision:'1',cwd:'/tmp'});
 store.receive('main',{agent_id:'a',conversation_id:'chat',relay_task_id:'input',idempotency_key:'input',metadata:{conversation_type:'direct'},message:{id:'m',content:'show a card',sender_type:'user',sender_user_id:'owner',attachments:[]}});
 const events:RuntimeEvent[]=[{seq:1,type:'turn/start',time:1,data:{turn:1}},{seq:2,type:'tool/call',time:2,data:{turn:1,callId:'send',name:'send_message'}},{seq:3,type:'assistant/message',time:3,data:{turn:1,message:{content:[{type:'text',text:'NO_REPLY'}]}}},{seq:4,type:'turn/end',time:4,data:{turn:1,reason:{kind:'completed'}}}];
 const runtime={onNotification:()=>()=>{},async request(method:string){return method==='session.lookup'?{accepted:true,turn:1,terminal:{kind:'completed'}}:{durable:true,events};}};
 const relay={async request(type:string,payload:Record<string,unknown>){frames.push(payload);if(type==='agent.message')throw new RelayDeliveryError('ACK lost','unknown');return {type:'ack',payload:type==='agent.message.status'?{found,message_id:'card',conversation_id:same?'chat':'other-chat'}:type==='conversation.query'?{ok:true,result:{type:'direct',channel:'web'}}:{message_id:'bubble'}};}};
 const agents=[{agentId:'a',revision:'1',workspace:'/tmp',mode:'single_thread' as const,provider:'test',model:'test'}],options={nodeId:'n',ownerId:'owner',agents,store,runtime,relay,image:async()=>'',onError:()=>{}};
 const global=new GlobalAgent({...options,inbox}),single=new SingleThread(options);
 try{
  const sending=global.call({method:'send_message',args:{target:'chat',text:'Card',...(interactive?{interactive:{format:'openui',catalog_version:'nano-1',source:'root = TextContent("card")'}}:{})},operationId:'main:send',callId:'send',sessionId:'main',rootSessionId:'main',agentId:'a',ownerId:'owner'});
  if(found)expect(await sending).toMatchObject({status:'sent',message_id:'card'});else await expect(sending).rejects.toThrow('ACK lost');
  await single.recover();
  expect(frames.some(p=>p.final_content==='NO_REPLY')).toBe(!(found&&same));
 }finally{await global.stop();await single.stop();inbox.close();store.close();}
});

it.each(['native','notice'])('keeps %s Task progress quiet while preserving a requested approval and its result',async(origin)=>{
 const store=new NodeStore(':memory:','owner'),frames:Record<string,unknown>[]=[];let notify:(method:string,payload:unknown)=>void=()=>{};
 const binding=store.bind({agentId:'a',sessionId:'task-main',conversationId:'chat',ownerId:'owner',revision:'1',cwd:'/tmp'});
 let events:RuntimeEvent[]=[{seq:1,type:'turn/start',time:1,data:{turn:1}},{seq:2,type:'user/message',time:2,data:{turn:1,id:'task-auto',source:{kind:'nano-system',channel:origin==='native'?'task-execution':'web_relay'},content:[{type:'text',text:'Continue task'}]}}];
 if(origin==='notice')store.receive(binding.sessionId,{agent_id:'a',conversation_id:'chat',relay_task_id:'task-notice',idempotency_key:'task-notice',metadata:{conversation_type:'direct'},message:{id:'task-notice',content:'Task assignment',sender_type:'system',sender_user_id:'owner',system_notice:{kind:'task_graph'},attachments:[]}});
 const errors:unknown[]=[];
 const product=new SingleThread({nodeId:'n',ownerId:'owner',agents:[{agentId:'a',revision:'1',workspace:'/tmp',mode:'single_thread',provider:'test',model:'test'}],store,
 runtime:{onNotification(listener){notify=listener;return()=>{};},async request(method){return method==='session.lookup'?{accepted:true,turn:1}:{durable:true,events};}},
 relay:{async request(type,payload){frames.push({...payload,transport:type});return {type:'ack',payload:{message_id:'task-bubble'}};}},image:async()=>'',onError:error=>{errors.push(error);}});
 try{
  await product.recover();expect(frames.filter(p=>p.transport!=='node.delivery_receipt')).toEqual([]);
  notify('session.stream',{sessionId:binding.sessionId,frame:{type:'start',attemptId:'auto',turn:1}});
  notify('session.stream',{sessionId:binding.sessionId,frame:{type:'chunk',attemptId:'auto',turn:1,chunk:{type:'text-delta',text:'Routine progress'}}});
  notify('session.stream',{sessionId:binding.sessionId,frame:{type:'end',attemptId:'auto',turn:1}});
  events=[...events,{seq:3,type:'tool/call',time:3,data:{turn:1,callId:'approve',name:'bash',arguments:'{"command":"reviewed command"}'}}];
  notify('approval.request',{sessionId:binding.sessionId,requestId:'task-approval',toolName:'bash',callId:'approve'});
  await expect.poll(()=>frames.some(p=>p.kind==='permission_request')).toBe(true);
  notify('approval.resolved',{sessionId:binding.sessionId,requestId:'task-approval',outcome:'allowed-once'});
  await expect.poll(()=>frames.some(p=>p.kind==='permission_resolved')).toBe(true);
  events=[...events,{seq:4,type:'assistant/message',time:4,data:{turn:1,message:{id:'answer',content:[{type:'text',text:'NO_REPLY'}]}}},{seq:5,type:'turn/end',time:5,data:{turn:1,reason:{kind:'completed'}}}];
  await product.recover();
  expect(frames.some(p=>p.kind==='message_delta'||p.kind==='message_discarded'||origin==='native'&&p.transport==='node.delivery_receipt')).toBe(false);
  expect(frames.find(p=>p.kind==='message_completed')).toMatchObject({message_id:'task-bubble',final_content:'',delivery_status:'completed'});
  expect(errors).toEqual([]);
 }finally{await product.stop();store.close();}
});

it.each([
  ['system','task_graph','NO_REPLY',false],
  ['system','task_graph','Task update worth sharing',true],
  ['user','task_graph','NO_REPLY',true],
  ['system','other_notice','NO_REPLY',true],
  ['system','task_graph','NO_REPLY',true,true],
])('handles direct %s/%s notice closing %s without confusing its source',async(sender,kind,closing,visible,mixed=false)=>{
 const store=new NodeStore(':memory:','owner'),frames:Record<string,unknown>[]=[];
 store.bind({agentId:'a',sessionId:'notice-main',conversationId:'chat',ownerId:'owner',revision:'1',cwd:'/tmp'});
 store.receive('notice-main',{agent_id:'a',conversation_id:'chat',relay_task_id:'notice',idempotency_key:'notice',metadata:{conversation_type:'direct'},message:{id:'notice',content:'Task assignment',sender_user_id:'owner',sender_type:String(sender),system_notice:{kind:String(kind)},attachments:[]}});
 if(mixed)store.receive('notice-main',{agent_id:'a',conversation_id:'chat',relay_task_id:'human',idempotency_key:'human',metadata:{conversation_type:'direct'},message:{id:'human',content:'A real human question',sender_user_id:'owner',sender_type:'user',attachments:[]}});
 let events:RuntimeEvent[]=[];
 const product=new SingleThread({nodeId:'n',ownerId:'owner',agents:[{agentId:'a',revision:'1',workspace:'/tmp',mode:'single_thread',provider:'test',model:'test'}],store,
  runtime:{onNotification:()=>()=>{},async request(method){return method==='session.lookup'?{accepted:true,turn:1}:{durable:true,events};}},
  relay:{async request(_type,payload){frames.push(payload);return {type:'ack',payload:{message_id:'notice-bubble'}};}},image:async()=>'',onError:error=>{throw error;}});
 try{
  await product.recover();
  if(sender==='system'&&kind==='task_graph'&&!mixed)expect(frames.some(p=>p.kind==='turn_start')).toBe(false);
  events=[{seq:1,type:'assistant/message',time:1,data:{turn:1,message:{content:[{type:'text',text:closing}]}}},{seq:2,type:'turn/end',time:2,data:{turn:1,reason:{kind:'completed'}}}];
  await product.recover();
  expect(frames.some(p=>p.kind==='message_completed'&&p.final_content===closing)).toBe(visible);
 }finally{await product.stop();store.close();}
});
