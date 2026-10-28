import { expect, it } from 'vitest';
import { start, bind, connect } from './helpers.js';

it('applies public read, member writes and frozen history across HTTP and Agent conversation tools',async()=>{
  const f=await start(), g=await bind(f);
  const call=(method:string,path:string,body:any=undefined,who='alice')=>f.http(method,path,body,f.tokens[who]);
  const created=await call('POST','/im/v1/conversations',{title:'Public work',type:'group',participants:[]});
  expect(created.status,created.body).toBe(201);
  const id=created.body.id;
  expect(created.body).toMatchObject({visibility:'public',is_member:true,can_write:true});
  expect((await call('GET',`/im/v1/conversations/${id}`,undefined,'bob')).body).toMatchObject({is_member:false,can_write:false});
  expect((await call('GET','/im/v1/conversations',undefined,'bob')).body.items).toHaveLength(0);
  expect((await call('GET','/im/v1/conversations?scope=public',undefined,'bob')).body.items.map((x:any)=>x.id)).toContain(id);
  expect((await call('POST',`/im/v1/conversations/${id}/messages`,{sender_user_id:'bob',content:'no'},'bob')).status).toBe(404);
  const task=await call('POST','/im/v1/task-graphs',{title:'Root',mode:'explore',conversation_id:id,request_key:'root'});
  expect(task.status,task.body).toBe(200);
  const graphId=task.body.graph_id;
  const command=(action:string,extra:any)=>g.frames.send('conversation.query',{node_id:g.node,agent_id:'assistant',session_id:'single',request_id:crypto.randomUUID(),action,...extra});
  const info=await command('info',{target:id});
  expect(info.payload,info).toMatchObject({result:{is_member:false,can_write:false}});
  expect((await command('join',{target:id})).payload.result.conversation.can_write).toBe(true);
  expect((await call('POST',`/im/v1/conversations/${id}/join`,{},'bob')).body.can_write).toBe(true);
  expect((await call('PATCH',`/im/v1/conversations/${id}`,{visibility:'private'},'bob')).status).toBe(403);
  expect((await call('PATCH',`/im/v1/conversations/${id}`,{visibility:'private'})).status).toBe(200);
  expect((await call('GET',`/im/v1/task-graphs/${graphId}`,undefined,'outsider')).status).toBe(404);
  expect((await call('POST',`/im/v1/conversations/${id}/join`,{},'outsider')).status).toBe(404);
  const nodes=await call('POST',`/im/v1/task-graphs/${graphId}/apply`,{base_revision:1,request_key:'children',change_note:'',operations:[
    {op:'add_task',client_ref:'done',container_id:'n1',title:'Done',status:'done',result:'preserve this'},
    {op:'add_task',client_ref:'open',container_id:'n1',title:'Open',status:'in_review'},
    {op:'select_candidate',scope_id:'n1',node_id:'@open',reason:'Preserve selection history'},
    {op:'update_task',node_id:'n1',patch:{status:'done',result:'Finished scope'}},
  ]});
  expect(nodes.status,nodes.body).toBe(200);
  const beforeMessages=(await call('GET',`/im/v1/conversations/${id}/messages`)).body;
  expect((await call('DELETE',`/im/v1/conversations/${id}`,undefined,'bob')).status).toBe(403);
  expect((await call('GET',`/im/v1/task-graphs/${graphId}?view=all`)).body.revision).toBe(2);
  expect((await call('DELETE',`/im/v1/conversations/${id}`)).status).toBe(204);
  const history=await call('GET',`/im/v1/conversations/${id}`,undefined,'bob');
  expect(history.body).toMatchObject({is_member:true,can_write:false,visibility:'private'});
  expect(history.body.dissolved_at).toBeTruthy();
  const graph=await call('GET',`/im/v1/task-graphs/${graphId}?view=all`,undefined,'bob');
  expect(graph.body.nodes.map((n:any)=>n.status)).toEqual(['done','done','closed']);
  expect(graph.body.nodes[1].result).toBe('preserve this');
  expect(graph.body.nodes[0]).toMatchObject({selected_candidate_id:null,selection_reason:'Preserve selection history',result:'Finished scope',updated_by:'alice (alice)',updated_by_actor:{type:'user',id:'alice'},updated_at:history.body.dissolved_at});
  expect(graph.body.nodes[0].change_note).toBeTruthy();
  const agentRead=await g.frames.send('task_graph.command',{node_id:g.node,agent_id:'assistant',request_id:'history-task',action:'get',args:{graph_id:graphId,view:'all'}});
  expect(agentRead.payload).toMatchObject({ok:true,result:{revision:3,updated_by:'alice (alice)',conversation:{can_write:false}}});
  expect(agentRead.payload.result.nodes[2]).toMatchObject({status:'closed',updated_by_actor:{type:'user',id:'alice'},updated_at:history.body.dissolved_at});
  expect((await call('GET',`/im/v1/conversations/${id}/messages`)).body).toEqual(beforeMessages);
  expect((await call('GET','/im/v1/conversations',undefined,'bob')).body.items).toHaveLength(0);
  expect((await call('POST',`/im/v1/conversations/${id}/participants`,{participants:[{type:'user',id:'outsider'}]})).status).toBe(409);
  expect((await call('POST',`/im/v1/task-graphs/${graphId}/apply`,{base_revision:3,request_key:'late',change_note:'',operations:[{op:'update_task',node_id:'n1',patch:{description:'Late edit'}}]})).body.detail.code).toBe('conversation_dissolved');
},20000);

it('stores task notifications offline and cancels delivery when the Agent leaves before reconnect',async()=>{
  const f=await start(),g=await bind(f);
  const chat=await f.http('POST','/im/v1/conversations',{title:'Offline',type:'group',participants:[{type:'agent',id:'assistant'}]},f.tokens.alice);
  const id=chat.body.id;
  g.socket.close();
  await new Promise<void>(resolve=>g.socket.once('close',()=>resolve()));
  const args={title:'Assignment',mode:'dag',conversation_id:id,assignee:{type:'agent',id:'assistant'},request_key:'assigned'};
  const saved=await f.http('POST','/im/v1/task-graphs',args,f.tokens.alice);
  expect(saved.status,saved.body).toBe(200);
  expect((await f.http('POST','/im/v1/task-graphs',args,f.tokens.alice)).body).toEqual(saved.body);
  const messages=await f.http('GET',`/im/v1/conversations/${id}/messages`,undefined,f.tokens.alice);
  expect(messages.body.items).toHaveLength(1);
  expect(messages.body.items[0].message.sender_type).toBe('system');
  const again=await connect(f,g.node,g.runtime);
  const notification=await again.frames.next(p=>p.type==='relay.message');
  expect(notification.payload.message.id).toBe(messages.body.items[0].message.id);
  expect(notification.payload.metadata.mentioned_agent_ids).toEqual(['assistant']);
  again.socket.close();
  await new Promise<void>(resolve=>again.socket.once('close',()=>resolve()));
  const member=chat.body.participants.find((p:any)=>p.id==='assistant');
  expect((await f.http('DELETE',`/im/v1/conversations/${id}/participants/${member.user_id}`,undefined,f.tokens.alice)).status).toBe(204);
  const last=await connect(f,g.node,g.runtime);
  // A normal request gives the serialized connection handler a completed turn after its replay.
  await last.frames.send('conversation.query',{node_id:g.node,agent_id:'assistant',session_id:'s',action:'list',request_id:'after-replay'});
  expect(last.frames.queue.filter(p=>p.type==='relay.message')).toHaveLength(0);
},20000);
