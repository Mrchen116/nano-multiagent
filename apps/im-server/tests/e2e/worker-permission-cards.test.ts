import { DatabaseSync } from 'node:sqlite';
import { expect, it } from 'vitest';
import { bind, cleanups, start } from './helpers.js';

it('binds worker approvals to the owner DM and original call across retries, replies and expiration', async () => {
  const center = await start(undefined, {IM_RELAY_WATCHDOG_INTERVAL_SECONDS:'0.1'});
  const node = await bind(center);
  const db = new DatabaseSync(center.dbPath);
  cleanups.push(() => db.close());
  const {http, tokens} = center;
  const {body:group} = await http('POST', '/im/v1/conversations', {
    type:'group', title:'source', participants:[{type:'agent',id:'global'},{type:'user',id:'bob'}],
  }, tokens.alice);
  const {body:shadow} = await http('POST', '/im/v1/conversations/external/find-or-create', {
    agent_id:'global', external_source:'feishu', external_chat_id:'feishu:app:group:source', is_group:true, title:'Feishu source',
  }, node.token);
  expect([group.id, shadow.id]).toEqual([expect.any(String), expect.any(String)]);

  const worker = {workerId:'worker-1', runtime:'codex', label:'Build worker'};
  const original = {
    kind:'worker_permission_request', agent_id:'global', session_id:'root-session', run_id:'root-run', worker,
    expires_at:Date.now()+60_000, conversation_id:shadow.id, to_user_id:'bob',
    permission_request:{request_id:'approval-id', call_id:'call-1', tool_name:'command',
      question:'Build worker requests: git status', tool_input:{command:'git status'}, options:[{id:'allow_always'}]},
  };
  let envelope = 0;
  const stream = (input: Record<string, unknown>) => node.frames.send('node.streaming_delta', {
    node_id:node.node, request_id:`transport-${++envelope}`, ...input,
  });
  const read = (cid:string, token=tokens.alice) => http('GET', `/im/v1/conversations/${cid}/messages`, undefined, token);
  const answer = (cid:string, mid:string, rid:string, decision:string, token=tokens.alice) =>
    http('POST', `/im/v1/conversations/${cid}/permissions/${rid}`, {message_id:mid, decision}, token);

  const created = await stream(original);
  expect(created.type, created).toBe('ack');
  const {message_id:mid, conversation_id:cid} = created.payload;
  expect(cid).not.toBe(group.id);
  expect(cid).not.toBe(shadow.id);
  expect((await stream(original)).payload.message_id).toBe(mid);
  expect((await stream({...original,session_id:'other'})).type).toBe('error');
  expect((await stream({...original,permission_request:{...original.permission_request,tool_input:{command:'other'}}})).type).toBe('error');
  expect((await stream({...original,agent_id:'assistant'})).type).toBe('error');
  expect((await stream({...original,lifecycle_revision:2})).type).toBe('error');
  expect((await stream({...original,permission_request:{...original.permission_request,request_id:undefined}})).type).toBe('error');
  const {body:ownerView} = await read(cid);
  expect(ownerView.items).toHaveLength(1);
  expect(ownerView.items[0].message).toMatchObject({
    id:mid, delivery_status:'completed', permission_requests:[{
      request_id:'approval-id', question:original.permission_request.question, tool_input:{command:'git status'},
      status:'pending', worker, options:[{id:'allow_once'},{id:'deny'}],
    }],
  });
  for (const source of [group.id, shadow.id]) {
    expect(JSON.stringify((await read(source)).body)).not.toContain('approval-id');
    expect((await answer(source, mid, 'approval-id', 'allow_once')).status).toBe(409);
  }
  expect((await read(cid,tokens.bob)).status).toBe(404);
  expect((await answer(cid,mid,'approval-id','allow_once',tokens.bob)).status).toBe(404);
  expect((await answer(cid,mid,'wrong-request','allow_once')).status).toBe(409);
  expect((await answer(cid,mid,'approval-id','allow_always')).status).toBe(409);
  expect((await http('POST','/im/v1/agents/global/work/permissions/approval-id',{decision:'allow_once'},tokens.alice)).status).toBe(409);
  const resolution = {kind:'permission_resolved', message_id:mid, agent_id:'global', session_id:'root-session', run_id:'root-run',
    permission_request:{request_id:'approval-id'}, decision:'allow_once'};
  expect((await stream(resolution)).type).toBe('error');
  expect((await answer(cid,mid,'approval-id','allow_once')).body).toMatchObject({status:'submitted',decision:'allow_once',decided_by:'alice'});
  const command = await node.frames.next(frame => frame.type==='node.streaming_delta' && frame.payload.kind==='permission_response');
  expect(command.payload).toMatchObject({message_id:mid,request_id:'approval-id',decision:'allow_once',lifecycle_revision:1});
  expect((await answer(cid,mid,'approval-id','deny')).body.decision).toBe('allow_once');
  expect((await stream({...resolution,session_id:'other'})).type).toBe('error');
  expect((await stream(resolution)).type).toBe('ack');
  expect((await stream(resolution)).type).toBe('ack');
  const events=db.prepare('SELECT event_type FROM conversation_events WHERE message_id=? ORDER BY event_id').all(mid);
  expect(events.map(e=>e.event_type)).toEqual(['message.created','permission.request','permission.submitted','permission.resolved','message.completed']);
  expect((await read(cid)).body.items[0].message).toMatchObject({content:'Build worker requests: git status\n\n已允许本次操作',
    delivery_status:'completed',permission_requests:[{request_id:'approval-id',status:'resolved',decision:'allow_once',tool_name:'command',question:original.permission_request.question,tool_input:{command:'git status'},options:[{id:'allow_once'},{id:'deny'}]}]});

  const summary = await http('GET',`/im/v1/conversations/${cid}/messages?view=summary`,undefined,tokens.alice);
  expect(summary.body.items[0].message).toMatchObject({content:'Build worker requests: git status\n\n已允许本次操作',
    permission_requests:[{status:'resolved',decision:'allow_once'}]});

  const newRequest = (id:string, deadline:number) => ({...original,expires_at:deadline,permission_request:{...original.permission_request,request_id:id}});
  const cancelled = (await stream(newRequest('cancelled', Date.now()+60_000))).payload.message_id;
  expect((await stream({...resolution,message_id:cancelled,permission_request:{request_id:'cancelled'},decision:'cancelled'})).type).toBe('ack');
  expect((await answer(cid,cancelled,'cancelled','allow_once')).body).toMatchObject({status:'resolved',decision:'cancelled'});
  const expired = (await stream(newRequest('lost', Date.now()+500))).payload.message_id;
  await expect.poll(() => db.prepare('SELECT content FROM messages WHERE id=?').get(expired)?.content)
    .toBe('Build worker requests: git status\n\n已超时');
  expect((await answer(cid,expired,'lost','allow_once')).status).toBe(409);
  expect((await stream(newRequest('already-expired', Date.now()-1))).type).toBe('error');
  expect(db.prepare("SELECT count(*) n FROM conversation_events WHERE event_type='permission.submitted'").get()?.n).toBe(1);
}, 30_000);

it('uses the authoritative PA binding even when owner_id and user id differ', async () => {
  const center = await start();
  const db = new DatabaseSync(center.dbPath);
  cleanups.push(() => db.close());
  // Historical installations can have distinct account and membership identities.
  db.prepare("UPDATE users SET owner_id='account-alice',personal_space_enabled=1 WHERE id='alice'").run();
  const node = await bind(center);
  const agent = 'global';
  const privateChat = await center.http('POST','/im/v1/conversations',{type:'direct',title:'PA',
    participants:[{type:'agent',id:agent}]},center.tokens.alice);
  const cid = privateChat.body.id;
  const epoch = db.prepare('SELECT node_epoch FROM node_binding_state WHERE node_id=?').get(node.node)!.node_epoch;
  db.prepare("INSERT INTO personal_agent_bindings VALUES('binding','account-alice','alice',?,?,?,?,?,'request','active',NULL,'now')")
    .run(agent,node.node,epoch,cid,'PA');
  db.prepare("INSERT INTO pa_policies(binding_id) VALUES('binding')").run();
  const result = await node.frames.send('node.streaming_delta', {
    node_id:node.node,kind:'worker_permission_request',agent_id:agent,session_id:'pa',run_id:'pa',worker:{workerId:'claude-1',runtime:'claude',label:'Claude'},
    expires_at:Date.now()+5000,permission_request:{request_id:'pa-request',call_id:'pa-call',tool_name:'Read',question:'Claude: Read report',tool_input:{file_path:'report'}},
  });
  expect(result.type,result).toBe('ack');
  const receipt = result.payload;
  expect(receipt.conversation_id).toBe(cid);
  db.prepare('UPDATE personal_agent_bindings SET status=? WHERE binding_id=?').run('pending','binding');
  const answer = () => center.http('POST',`/im/v1/conversations/${cid}/permissions/pa-request`,{message_id:receipt.message_id,decision:'deny'},center.tokens.alice);
  expect((await answer()).status).toBe(409);
  db.prepare('UPDATE personal_agent_bindings SET status=? WHERE binding_id=?').run('active','binding');
  db.prepare('UPDATE node_binding_state SET node_epoch=node_epoch+1 WHERE node_id=?').run(node.node);
  expect((await answer()).status).toBe(409);
  db.prepare('UPDATE node_binding_state SET node_epoch=node_epoch-1 WHERE node_id=?').run(node.node);
  const reply = await answer();
  expect(reply.status,reply.body).toBe(200);
  expect(reply.body.decided_by).toBe('alice');
}, 30_000);
