import {DatabaseSync} from 'node:sqlite';
import {expect,it} from 'vitest';
import {start,bind,connect} from './helpers.js';

it('saves offline messages and recovers through a bounded node window with monotonic receipts',async()=>{
 const f=await start(),g=await bind(f);
 const created=await f.http('POST','/im/v1/conversations',{title:'Recovery',type:'direct',participants:[{type:'agent',id:'assistant'}]},f.tokens.alice);expect(created.status,created.body).toBe(201);const id=created.body.id;
 const send=(i:number)=>f.http('POST',`/im/v1/conversations/${id}/messages`,{sender_user_id:'alice',content:`message ${i}`},f.tokens.alice,{'Idempotency-Key':`message-${i}`});
 for(let i=0;i<40;i++)expect((await send(i)).status).toBe(201);
 await expect.poll(()=>g.frames.queue.filter(p=>p.type==='relay.message').length).toBe(32);
 const input=await g.frames.next(p=>p.type==='relay.message');
 expect((await g.frames.send('node.delivery_receipt',{node_id:g.node,relay_task_id:input.payload.relay_task_id,delivery_status:'completed',request_id:'complete'})).payload.request_id).toBe('complete');
 await expect.poll(()=>g.frames.queue.filter(p=>p.type==='relay.message').length).toBe(32);
 await g.frames.send('node.delivery_receipt',{node_id:g.node,relay_task_id:input.payload.relay_task_id,delivery_status:'sent',request_id:'late'});
 const history=await f.http('GET',`/im/v1/conversations/${id}/messages?limit=100`,undefined,f.tokens.alice);
 expect(history.body.items.find((m:any)=>m.message?.id===input.payload.message.id)?.message.delivery_status).toBe('completed');
 g.socket.terminate();await new Promise(r=>g.socket.once('close',r));
 expect((await send(40)).status).toBe(201);
 const again=await connect(f,g.node,g.runtime);await expect.poll(()=>again.frames.queue.filter(p=>p.type==='relay.message').length).toBe(32);
 expect(again.frames.queue.filter(p=>p.type==='relay.message').every(p=>p.payload.message.id!==input.payload.message.id)).toBe(true);
},15000);

it('establishes current scope without a Work flush and history cannot replace it',async()=>{
 const f=await start(),g=await bind(f);
 const scope=await g.frames.send('agent.session.ensure',{node_id:g.node,agent_id:'global',session_id:'current-main',request_id:'scope'});
 expect(scope).toMatchObject({type:'ack',payload:{request_id:'scope',session_id:'current-main'}});
 const queried=await g.frames.send('conversation.query',{node_id:g.node,agent_id:'global',session_id:'current-main',action:'list',request_id:'query'});expect(queried.payload.ok).toBe(true);
 const uploaded=await f.http('POST','/im/v1/gateway/work-sync/journals/history/events',{from_seq:1,events:[{seq:1,event_id:'old',root_agent_id:'global',session_id:'old-main',type:'session_registered',payload:{scope:'global_main'}}]},g.runtime);expect(uploaded.status).toBe(200);
 const retired=await g.frames.send('conversation.query',{node_id:g.node,agent_id:'global',session_id:'old-main',action:'list',request_id:'old-query'});expect(retired.type==='error'||retired.payload.ok===false).toBe(true);
 expect((await g.frames.send('conversation.query',{node_id:g.node,agent_id:'global',session_id:'current-main',action:'list',request_id:'still-current'})).payload.ok).toBe(true);
});

it('projects Global Agent receipt stages separately from the relay lifecycle', async () => {
  const f = await start(), g = await bind(f);
  const conversation = await f.http('POST', '/im/v1/conversations', {
    title: 'Global Agent receipt', type: 'direct', participants: [{ type: 'agent', id: 'global' }],
  }, f.tokens.alice);
  expect(conversation.status, conversation.body).toBe(201);
  const messages = `/im/v1/conversations/${conversation.body.id}/messages`;
  const sent = await f.http('POST', messages, { sender_user_id: 'alice', content: 'Check the itinerary' }, f.tokens.alice);
  expect(sent.status, sent.body).toBe(201);
  expect(sent.body.receipts).toMatchObject([{ status: 'sent' }]);

  const input = await g.frames.next(frame => frame.type === 'relay.message');
  const receipt = async (status: string) => {
    const reply = await g.frames.send('node.delivery_receipt', {
      node_id: g.node, relay_task_id: input.payload.relay_task_id, delivery_status: status, request_id: status,
    });
    expect(reply.type, reply.payload).toBe('ack');
  };
  const history = async () => {
    const response = await f.http('GET', messages, undefined, f.tokens.alice);
    return response.body.items.find((item: any) => item.message?.id === sent.body.id)?.message;
  };
  await receipt('sent');
  expect((await history()).receipts).toMatchObject([{ recipient_id: input.payload.participants.find((actor: any) => actor.id === 'global').user_id, status: 'received' }]);
  await receipt('read');
  const db = new DatabaseSync(f.dbPath, { readOnly: true });
  try {
    const events = db.prepare(`SELECT message_id FROM conversation_events
      WHERE conversation_id=? AND event_type='message.receipts_changed'`).all(conversation.body.id);
    expect(events).toEqual([{ message_id: null }, { message_id: null }]);
  } finally {
    db.close();
  }
  await receipt('failed');
  expect((await history()).receipts).toMatchObject([{ recipient_id: input.payload.participants.find((actor: any) => actor.id === 'global').user_id, status: 'read' }]);
});

it.each(['direct', 'group'] as const)('confirms %s delivery from each real recipient and exposes details only to the sender', async type => {
  const f = await start();
  const g = type === 'group' ? await bind(f) : undefined;
  const conversation = await f.http('POST', '/im/v1/conversations', {
    title: 'Member receipts', type, participants: [{type:'user',id:'bob'}, ...(g ? [
      {type:'agent',id:'global'}, {type:'agent',id:'assistant'},
    ] : [])],
  }, f.tokens.alice);
  expect(conversation.status, JSON.stringify(conversation.body)).toBe(201);
  const base = `/im/v1/conversations/${conversation.body.id}`;
  const sent = await f.http('POST', `${base}/messages`, {content:'Regular group update', sender_user_id:'alice'}, f.tokens.alice);
  expect(sent.status).toBe(201);
  expect(sent.body.receipts).toHaveLength(g ? 3 : 1);
  expect(sent.body.receipts.every((receipt: any) => receipt.status === 'sent')).toBe(true);

  const readMessage = async (viewer: string) => (await f.http('GET', `${base}/messages/${sent.body.id}`, undefined, f.tokens[viewer])).body.message;
  const confirm = (viewer: string) => f.http('POST', '/im/v1/message-receipts', {message_ids:[sent.body.id]}, f.tokens[viewer]);
  await confirm('outsider');
  expect((await readMessage('alice')).receipts).toContainEqual(expect.objectContaining({recipient_id:'bob',status:'sent'}));
  expect((await readMessage('bob')).receipts).toBeUndefined();
  expect((await confirm('bob')).status).toBe(200);
  expect((await readMessage('alice')).receipts).toContainEqual(expect.objectContaining({recipient_id:'bob',status:'received'}));

  if (g) {
    for (const agent of ['global','assistant']) {
      const relay = await g.frames.next(frame => frame.type === 'relay.message' && frame.payload.agent_id === agent);
      expect(relay.payload.metadata).toMatchObject({agent_receipt:true,mentioned_agent_ids:[]});
      for (const status of ['sent','read']) {
        const reply = await g.frames.send('node.delivery_receipt', {
          node_id:g.node, relay_task_id:relay.payload.relay_task_id, delivery_status:status, request_id:agent+status,
        });
        expect(reply.type).toBe('ack');
      }
    }
    expect((await readMessage('alice')).receipts.map((receipt: any) => receipt.status).sort()).toEqual(['read','read','received']);
  }
  expect((await f.http('POST', `${base}/read`, {last_read_message_id:sent.body.id}, f.tokens.bob)).status).toBe(200);
  await confirm('bob');
  expect((await readMessage('alice')).receipts.every((receipt: any) => receipt.status === 'read')).toBe(true);
});
