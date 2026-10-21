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
