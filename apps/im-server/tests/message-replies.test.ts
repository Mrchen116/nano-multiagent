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
