import Fastify from 'fastify';
import { expect, it } from 'vitest';
import { fixture } from './control-fixture.js';
import { Messaging, registerMessagingRoutes } from '../src/messaging.js';

it('persists authoritative quotes, relays the addressed Agent, and keeps retries bound to the original target', async () => {
  const {ctx,db}=fixture();
  ctx.gateway.broadcast=()=>{};
  ctx.messaging=new Messaging(ctx);
  const app=Fastify();registerMessagingRoutes(app,ctx);
  const original=ctx.messaging.insertMessage('chat','a1','agent','第二点：先验证再交付');
  const other=ctx.messaging.insertMessage('chat','u1','user','另一条消息');
  const send=(target:string,key='reply')=>app.inject({method:'POST',url:'/im/v1/conversations/chat/messages',headers:{'idempotency-key':key},payload:{sender:{type:'user',id:'u1'},content:'展开这个',reply_to_message_id:target}});
  try {
    const sent=await send(original.id);expect(sent.statusCode,sent.body).toBe(201);
    const quote={message_id:original.id,sender:original.sender,content:original.content,attachments:[]};
    expect(sent.json().reply_to).toEqual(quote);
    const queued=db.prepare('SELECT payload_json FROM relay_tasks WHERE message_id=?').get(sent.json().id)!;
    expect(JSON.parse(String(queued.payload_json))).toMatchObject({message:{reply_to:quote},metadata:{mentioned_agent_ids:['a']}});
    expect((await send(original.id)).json().id).toBe(sent.json().id);
    expect((await send(other.id)).statusCode).toBe(409);
    const read=await app.inject('/im/v1/conversations/chat/messages');
    expect(read.json().items.find((item:any)=>item.message?.id===sent.json().id).message.reply_to).toEqual(quote);
    expect((await send('missing','missing')).statusCode).toBe(404);
    db.prepare("INSERT INTO conversations(id,title,created_at) VALUES('private','Private',datetime('now'))").run();
    const hidden=ctx.messaging.insertMessage('private','u2','user','PRIVATE_SECRET');
    expect((await send(hidden.id,'cross-chat')).statusCode).toBe(404);
    const running=ctx.messaging.insertMessage('chat','a1','agent','unfinished',[],null,'running');
    expect((await send(running.id,'running')).statusCode).toBe(422);
    const system=ctx.messaging.insertMessage('chat','u1','system','notice');
    expect((await send(system.id,'system')).statusCode).toBe(422);
  } finally {await app.close();}
});

it('publishes an Agent quote from server-owned history and rejects a changed target on retry',()=>{
  const {ctx,db}=fixture();ctx.gateway.broadcast=()=>{};ctx.gateway.groupReply=()=>{};
  ctx.messaging=new Messaging(ctx);
  const original=ctx.messaging.insertMessage('chat','u1','user','请逐条回应这一条');
  const other=ctx.messaging.insertMessage('chat','u1','user','另一条');
  const principal={kind:'gateway' as const,node_id:'n',owner_id:'o1',node_epoch:1};
  const publication={to:'conversation:chat',from_session_id:'a|tool_call:quote',text:'这条我来处理。',reply_to_message_id:original.id};
  const receipt=ctx.messaging.publishAgent(principal,'a','quote',publication);
  expect(ctx.messaging.message(receipt.message_id)).toMatchObject({sender_type:'agent',reply_to:{message_id:original.id,content:original.content,sender:{id:'u1'}}});
  expect(ctx.messaging.publishAgent(principal,'a','quote',publication)).toEqual(receipt);
  expect(()=>ctx.messaging.publishAgent(principal,'a','quote',{...publication,reply_to_message_id:other.id})).toThrow('identity conflict');
  db.prepare("INSERT INTO conversations(id,title,created_at) VALUES('hidden','Hidden',datetime('now'))").run();
  const hidden=ctx.messaging.insertMessage('hidden','u2','user','PRIVATE');
  expect(()=>ctx.messaging.publishAgent(principal,'a','cross',{...publication,reply_to_message_id:hidden.id})).toThrow('reply target not found');
});
