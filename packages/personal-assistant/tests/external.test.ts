import { expect, it } from 'vitest';
import { ExternalChannels } from '../src/external.js';
import { NodeStore } from '../src/store.js';
import type { RelayInput } from '@nano/product-contracts';
import { InboxStore } from '../src/inbox.js';

it('marks only the configured owner direct chat as an owner recipient, including shadow aliases', async () => {
  const store=new NodeStore(':memory:','owner'),accepted:RelayInput[]=[];
  const external=new ExternalChannels(':memory:',{nodeId:'node',ownerId:'owner',store,
    relay:{ready:true,request:async()=>({type:'ack',payload:{}})},
    im:async(_path,options)=>({id:`shadow-${JSON.parse(String(options?.body)).external_chat_id}`}),
    receive:async input=>{accepted.push(input);},permission:async()=>{},onError:()=>{}});
  let sends=0;
  const connection={config:{appId:'app',ownerOpenId:'owner-openid'},send:async()=>{sends++;return 'sent';},thinking:async()=>undefined,image:async()=>({data:Buffer.alloc(0),mediaType:'image/png'}),updateCard:async()=>{}};
  external.add('a',connection);
  try{
    for(const [id,senderId,isGroup] of [['owner','owner-openid',false],['other','other-openid',false],['group','owner-openid',true]] as const){
      await external.receive('a',{messageId:id,chatId:id,senderId,isGroup,mentioned:false,time:'1000',parts:[{type:'text',text:'hi'}]});
      const target=accepted.at(-1)!.conversation_id;
      const info=await external.request('conversation.query',{agent_id:'a',action:'info',target});
      expect(info.payload.result).toMatchObject({owner_recipient:id==='owner'});
    }
    await external.recover();
    const alias=await external.request('conversation.query',{agent_id:'a',action:'info',target:'shadow-feishu:app:dm:owner-openid'});
    expect(alias.payload.result).toMatchObject({owner_recipient:true});
    external.add('a',{...connection,config:{appId:'app',ownerOpenId:'different-owner'}});
    const stale=await external.request('conversation.query',{agent_id:'a',action:'info',target:accepted[0]!.conversation_id});
    expect(stale.payload.result).toMatchObject({owner_recipient:false});
    expect(sends).toBe(0);
  }finally{await external.stop();store.close();}
});

it('keeps external execution and confirmed sends available offline and does not resend on replay', async () => {
  const store = new NodeStore(':memory:', 'owner'); let sends = 0;
  const accepted: RelayInput[] = []; let online = false; const mirrored: Record<string, unknown>[] = []; const requests: unknown[] = [];
  const external = new ExternalChannels(':memory:', { nodeId: 'node', ownerId: 'owner', store,
    relay: { get ready() { return online; }, async request(_type, payload) { mirrored.push(payload); return { type: 'ack', payload: { message_id: 'im-bubble' } }; } },
    im: async (path, options) => { if (!online) throw new Error('offline'); requests.push(JSON.parse(String(options?.body))); return { id: path.endsWith('find-or-create') ? 'shadow-chat' : 'shadow-input' }; }, receive: async input => { accepted.push(input); }, permission: async () => {}, onError: () => {},
  });
  external.add('a', { config: { appId: 'app', botOpenId: 'bot', ownerOpenId: 'human' }, async send() { sends++; return 'platform-result'; }, async thinking() { return undefined; }, async image() { return { data: Buffer.alloc(0), mediaType: 'image/png' }; }, async updateCard() {} });
  const message = { messageId: 'source', chatId: 'chat', senderId: 'human', isGroup: false, mentioned: false, time: '1000', parts: [{ type: 'text' as const, text: 'hello' }] };
  try {
    await external.receive('a', message); await external.receive('a', message);
    expect(accepted).toHaveLength(1);
    const input = accepted[0]!;
    expect(input.message.sender_user_id).toBe('human');
    const task = { agent_id: 'a', request_id: 'task-call', action: 'create', source_message_id: input.message.id, args: { conversation_id: 'shadow-chat' } };
    expect(await external.request('task_graph.command', task)).toMatchObject({ payload: { ok: false, error: { code: 'source_unavailable' } } });
    expect(mirrored).toEqual([]);
    const start = await external.request('node.streaming_delta', { node_id: 'node', kind: 'turn_start', agent_id: 'a', conversation_id: input.conversation_id, idempotency_key: 'turn', external_reply: input.metadata.external_reply });
    const tool = {id: 'native-tool', input: ['dynamic', {nested: null}], output: false, detail: {vendor: ['full', 'result']}};
    const toolFrame = {kind: 'tool_call_completed', message_id: start.payload.message_id, tool_call: tool};
    await external.request('node.streaming_delta', toolFrame); await external.request('node.streaming_delta', toolFrame);
    await expect(external.request('node.streaming_delta', {...toolFrame, tool_call: {...tool, id: 42}})).rejects.toThrow('id required');
    const complete = { kind: 'message_completed', message_id: start.payload.message_id, final_content: 'answer', delivery_status: 'completed' };
    await external.request('node.streaming_delta', complete); await external.request('node.streaming_delta', complete);
    expect(sends).toBe(1);
    const imStart = await external.request('node.streaming_delta', { kind: 'turn_start', agent_id: 'a', conversation_id: input.conversation_id, idempotency_key: 'im-triggered' });
    await external.request('node.streaming_delta', { ...complete, message_id: imStart.payload.message_id });
    expect(sends).toBe(1);
    const notice = { conversation_id: input.conversation_id, idempotency_key: 'knowledge-review', text: 'skills updated', system_notice: { source_agent_id: 'a', kind: 'self_evolution_review', updated_targets: ['skills'] } };
    await external.request('node.system_message', notice); await external.request('node.system_message', notice);
    expect(sends).toBe(2);
    store.bind({ agentId: 'a', sessionId: 'session', conversationId: input.conversation_id, ownerId: 'owner', cwd: '/tmp', revision: '1' });
    online = true; await external.recover(); await external.recover();
    expect(sends).toBe(2);
    expect(mirrored.filter(frame => frame.system_notice)).toHaveLength(1);
    expect(store.bindingFor('a', 'shadow-chat')?.sessionId).toBe('session');
    await external.request('task_graph.command', task);
    expect(mirrored).toContainEqual({ ...task, source_message_id: 'shadow-input',lifecycle_revision:1 });
    expect(await external.request('task_graph.command', { ...task, agent_id: 'other' })).toMatchObject({ payload: { ok: false, error: { code: 'source_unavailable' } } });
    expect(mirrored.filter(frame => frame.kind === 'turn_start')).toHaveLength(2);
    expect(mirrored.filter(frame => frame.kind === 'message_completed')).toHaveLength(2);
    expect(mirrored.filter(frame => frame.kind === 'tool_call_completed')).toEqual([expect.objectContaining({tool_call: tool, message_id: 'im-bubble'})]);
    await external.request('node.system_message', { ...notice, conversation_id: 'shadow-chat', idempotency_key: 'internal-review' });
    expect(sends).toBe(2);
    expect(requests).toContainEqual(expect.objectContaining({ sender_source_id: 'human', suppress_relay: true }));
  } finally { await external.stop(); store.close(); }
});

it('gives Feishu Inbox the original occurrence and the owner timezone captured at ingress', async () => {
  const store = new NodeStore(':memory:', 'owner');
  store.setOwnerTimezone('Asia/Shanghai');
  const inbox = new InboxStore(':memory:');
  let accepted: RelayInput | undefined;
  const external = new ExternalChannels(':memory:', { nodeId: 'node', ownerId: 'owner', store,
    relay: { ready: false, async request() { throw new Error('offline'); } }, im: async () => { throw new Error('offline'); },
    receive: async input => { accepted = input; inbox.receive(input, true); }, permission: async () => {}, onError: () => {},
  });
  external.add('a', { config: { appId: 'app', ownerOpenId: 'human' }, async send() { return 'sent'; },
    async thinking() { return undefined; }, async image() { return { data: Buffer.alloc(0), mediaType: 'image/png' }; }, async updateCard() {} });
  const message = { messageId: 'morning', chatId: 'chat', senderId: 'human', senderName: '你', isGroup: false, mentioned: false,
    time: String(Date.parse('2026-10-14T01:00:00Z')), parts: [{ type: 'text' as const, text: '早，今天有什么安排？' }] };
  try {
    await external.receive('a', message);
    store.setOwnerTimezone('Asia/Tokyo');
    await external.receive('a', message);
    expect(inbox.read('a', 'main', 'read', { target: accepted!.conversation_id })).toMatchObject({
      messages: [{ time: '2026-10-14T09:00:00+08:00', content: [{ text: message.parts[0]!.text }] }],
    });
    expect((await external.request('conversation.query', { agent_id: 'a', action: 'read', target: accepted!.conversation_id })).payload.result).toMatchObject({
      messages: [{ created_at: '2026-10-14T09:00:00+08:00' }],
    });
  } finally { await external.stop(); inbox.close(); store.close(); }
});

it('keeps group approval values private and accepts only the bound owner on the actual card', async () => {
  const store = new NodeStore(':memory:', 'owner'); const inputs: RelayInput[] = []; let decisions = 0,updates=0; let card: unknown;
  const external = new ExternalChannels(':memory:', { nodeId: 'node', ownerId: 'owner', store,
    relay: { ready: false, async request() { throw new Error('offline'); } }, im: async () => { throw new Error('offline'); },
    receive: async input => { inputs.push(input); }, permission: async () => { decisions++; }, onError: () => {},
  });
  external.add('a', { config: { appId: 'app', botOpenId: 'bot', ownerOpenId: 'owner-openid' }, async send(_chat, _text, _key, payload) { card = payload; return 'card'; }, async thinking() { return undefined; }, async image() { return { data: Buffer.alloc(0), mediaType: 'image/png' }; }, async updateCard() {updates++;} });
  try {
    await external.receive('a', { messageId: 'group-input', chatId: 'group', senderId: 'member', isGroup: true, mentioned: true, time: '1000', parts: [{ type: 'text', text: 'request' }] });
    const input = inputs[0]!;
    const start = await external.request('node.streaming_delta', { kind: 'turn_start', agent_id: 'a', conversation_id: input.conversation_id, idempotency_key: 'turn', external_reply: input.metadata.external_reply });
    await external.request('node.streaming_delta', { kind: 'permission_request', run_id: 'session', message_id: start.payload.message_id, permission_request: { request_id: 'request', tool_name: 'bash', reason: 'private-owner-data', tool_input: { command: 'private-owner-data' } } });
    expect(JSON.stringify(card)).not.toContain('private-owner-data');
    const action = { context: { open_message_id: 'card' }, action: { value: { request_id: 'request', decision: 'allow_once' } } };
    await external.card('a', { ...action, operator: { open_id: 'member' } }); expect(decisions).toBe(0);
    await external.card('a', { ...action, operator: { open_id: 'owner-openid' } }); expect(decisions).toBe(1);
    await external.card('a', { ...action, operator: { open_id: 'owner-openid' } }); expect(decisions).toBe(1);
    await expect(external.request('node.streaming_delta',{kind:'permission_resolved',message_id:start.payload.message_id,permission_request:{request_id:'request'},decision:'allow_once'})).resolves.toMatchObject({type:'ack'});
    expect(updates).toBe(1);
  } finally { await external.stop(); store.close(); }
});

it('never reports completed before the platform response and preserves unknown outcomes across restart', async () => {
  const { mkdtemp, rm } = await import('node:fs/promises'); const { tmpdir } = await import('node:os'); const { join } = await import('node:path');
  const directory = await mkdtemp(join(tmpdir(), 'nano-external-')); const path = join(directory, 'external.sqlite3');
  const store = new NodeStore(':memory:', 'owner'); const accepted: RelayInput[] = []; const frames: Record<string, unknown>[] = [];
  let sends = 0; let rejectSend: (error: Error) => void = () => {};
  const options = { nodeId: 'node', ownerId: 'owner', store,
    relay: { ready: true, async request(_type: string, payload: Record<string, unknown>) { frames.push(payload); return { type: 'ack', payload: { message_id: 'mirror' } }; } },
    im: async (path: string) => ({ id: path.endsWith('find-or-create') ? 'shadow' : 'input' }), receive: async (input: RelayInput) => { accepted.push(input); }, permission: async () => {}, onError: () => {},
  };
  const connection = { config: { appId: 'app', botOpenId: 'bot' }, send() { sends++; return new Promise<string>((_resolve, reject) => { rejectSend = reject; }); }, async thinking() { return undefined; }, async image() { return { data: Buffer.alloc(0), mediaType: 'image/png' }; }, async updateCard() {} };
  let external = new ExternalChannels(path, options); external.add('a', connection);
  try {
    await external.receive('a', { messageId: 'source', chatId: 'chat', senderId: 'human', isGroup: false, mentioned: false, time: '1000', parts: [{ type: 'text', text: 'hello' }] });
    const input = accepted[0]!;
    const start = await external.request('node.streaming_delta', { kind: 'turn_start', agent_id: 'a', conversation_id: input.conversation_id, idempotency_key: 'turn', external_reply: input.metadata.external_reply });
    const tool = {id: 'native-tool', input: ['dynamic', {nested: null}], output: false, detail: {vendor: ['full', 'result']}};
    const toolFrame = {kind: 'tool_call_completed', message_id: start.payload.message_id, tool_call: tool};
    await external.request('node.streaming_delta', toolFrame); await external.request('node.streaming_delta', toolFrame);
    await expect(external.request('node.streaming_delta', {...toolFrame, tool_call: {...tool, id: 42}})).rejects.toThrow('id required');
    const complete = { kind: 'message_completed', message_id: start.payload.message_id, final_content: 'answer', delivery_status: 'completed' };
    const pending = external.request('node.streaming_delta', complete); const rejected = expect(pending).rejects.toMatchObject({ delivery: 'unknown' });
    await external.recover(); expect(frames.some(frame => frame.kind === 'message_completed')).toBe(false);
    rejectSend(new Error('platform connection lost after send')); await rejected;
    await external.recover();
    expect(frames.filter(frame => frame.kind === 'message_completed')).toEqual([expect.objectContaining({ delivery_status: 'failed', external_delivery_status: 'unknown' })]);
    await external.stop(); external = new ExternalChannels(path, options); external.add('a', connection);
    await expect(external.request('node.streaming_delta', complete)).rejects.toMatchObject({ delivery: 'unknown' });
    expect(sends).toBe(1);
  } finally { await external.stop(); store.close(); await rm(directory, { recursive: true, force: true }); }
});

it('mirrors personal inputs once for observation without blocking them on failed output projections',async()=>{
 const store=new NodeStore(':memory:','owner'),calls:{type:string;payload:any}[]=[],mirrors:string[]=[],errors:unknown[]=[];
 let received=0,sent=0,removed=0;
 let external:ExternalChannels;
 external=new ExternalChannels(':memory:',{nodeId:'node',ownerId:'owner',store,personalAgent:()=>true,
  relay:{ready:true,request:async(type,payload)=>{calls.push({type,payload});if(type==='node.streaming_delta')throw new Error('old output projection failed');return {type:type+'.result',payload:{ok:true,result:{allowed:true}}};}},
  im:async(path,options)=>{if(path.endsWith('find-or-create'))return {id:'shadow-chat'};const content=JSON.parse(String(options?.body)).content;mirrors.push(content);return {id:`shadow-${content}`};},
  personalDelivery:delivery=>delivery.dispatch(delivery.text),
  receive:async()=>{received++;},permission:async()=>{},onError:error=>{errors.push(error);}});
 external.add('pa',{config:{appId:'app'},send:async()=>{sent++;return 'om_actual';},thinking:async(_id,reaction)=>{if(reaction)removed++;return 'thinking';},image:async()=>({data:Buffer.alloc(0),mediaType:'image/png'}),updateCard:async()=>{}});
 try {
  const message={messageId:'m',chatId:'dm',senderId:'peer',isGroup:false,mentioned:false,time:'1000',parts:[{type:'text' as const,text:'first'}]};
  await external.receive('pa',message);
  expect(await external.request('agent.message',{to:'conversation:shadow-chat',from_session_id:'pa|tool_call:reply',text:'Reply'})).toMatchObject({payload:{message_id:'om_actual'}});
  await external.receive('pa',{...message,messageId:'next',parts:[{type:'text',text:'next'}]});
  await external.receive('pa',message);await external.recover();
  expect(mirrors).toEqual(['first','next']);expect(received).toBe(0);expect(sent).toBe(1);
  expect(errors.some(error=>String(error).includes('old output projection failed'))).toBe(true);
  await external.request('pa.source.admit',{agent_id:'pa',source_message_id:'external:pa:app:m',conversation_id:'external:pa:feishu:app:dm:peer'});
  expect(calls).toContainEqual({type:'pa.source.admit',payload:{agent_id:'pa',source_message_id:'shadow-first',conversation_id:'shadow-chat',lifecycle_revision:1}});
  await external.request('node.delivery_receipt',{agent_id:'pa',external_source_message_id:'shadow-first',delivery_status:'completed'});
  expect(removed).toBe(1);
 }finally{await external.stop();store.close();}
});
