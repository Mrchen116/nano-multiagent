import { expect, it } from 'vitest';
import { once } from 'node:events';
import { join } from 'node:path';
import { start, bind, cleanups } from './helpers.js';
import { NodeStore } from '../../../../packages/personal-assistant/src/store.js';
import { InboxStore } from '../../../../packages/personal-assistant/src/inbox.js';
import { GlobalAgent } from '../../../../packages/personal-assistant/src/global-agent.js';
import { WorkSync } from '../../../../packages/personal-assistant/src/work-sync.js';
import type { RuntimeEvent, RuntimePort, RuntimeWorkerChange } from '@nano/product-contracts';

// Compose real product owners at the integration boundary; only native execution is a fixture.
it('projects real PA main/child facts through its durable journal and HTTP uploader into refreshable Work', async () => {
  const center = await start(), node = await bind(center);
  const store = new NodeStore(join(center.dir, 'node.db'), 'alice');
  const inbox = new InboxStore(join(center.dir, 'inbox.db'));
  cleanups.push(() => store.close(), () => inbox.close());
  store.bind({agentId: 'global', sessionId: 'main', conversationId: 'global:global', ownerId: 'alice', cwd: center.dir, revision: '1'});
  const content = '中文😀\n"原始参数"'.repeat(6000), output = '完整工具结果\n'.repeat(5000);
  const workerTime = Date.now() - 1000;
  const worker = (seq:number, workerId:string, label:string, runtime:RuntimeWorkerChange['runtime'], state:RuntimeWorkerChange['state']): RuntimeWorkerChange => ({
    id:String(seq), time:workerTime+seq, workerId, rootId:'main', callId:workerId+'-call', label, runtime, state,
  });
  let pendingWorkers = [
    worker(8, 'a-worker', '核对报表', 'codex', 'starting'),
    worker(9, 'b-worker', '核对附件', 'dsh', 'running'),
    worker(10, 'a-worker', '核对报表', 'codex', 'running'),
    worker(11, 'a-worker', '核对报表', 'codex', 'completed'),
  ];
  const source: RuntimeEvent[] = [
    {seq: 0, time: 1000, type: 'request/header', data: {header: {config: {model: 'fixture-model'}}}},
    {seq: 1, time: 1001, type: 'request/context', data: {contextWindow: 8192}},
    {seq: 2, time: 1002, type: 'turn/start', data: {turn: 1}},
    {seq: 3, time: 1003, type: 'user/message', data: {turn: 1, source: {kind: 'human'}, content: []}},
    {seq: 4, time: 1004, type: 'tool/call', data: {turn: 1, callId: 'write', name: 'write', arguments: JSON.stringify({path: 'report.txt', content})}},
    {seq: 5, time: 1008, type: 'tool/result', data: {turn: 1, message: {toolCallId: 'write', content: [{type: 'text', text: output}], isError: false}}},
    {seq: 6, time: 1009, type: 'assistant/message', data: {turn: 1, message: {id: 'answer', content: [{type: 'text', text: '主执行正文'}]}, usage: {inputTokens: 10, outputTokens: 3, cacheReadTokens: 2}}},
    {seq: 7, time: 1010, type: 'turn/end', data: {turn: 1, reason: {kind: 'completed'}}},
    {seq:12, time:workerTime+12, type:'turn/start', data:{turn:2}},
    {seq:13, time:workerTime+13, type:'user/message', data:{turn:2, id:'report', source:{kind:'nano-system', channel:'worker-report'}, content:[{type:'text',text:'报表已确认'}]}},
    {seq:14, time:workerTime+14, type:'user/message', data:{turn:2, id:'dsh-report', source:{kind:'agent-message',senderSessionId:'b-worker'}, content:[{type:'text',text:'正在核对附件'}]}},
    {seq:15, time:workerTime+15, type:'turn/end', data:{turn:2, reason:{kind:'completed'}}},
  ];
  const child: RuntimeEvent[] = [
    {seq: 1, time: 1004, type: 'turn/start', data: {turn: 1}},
    {seq: 2, time: 1005, type: 'user/message', data: {source: {kind: 'subagent'}, content: []}},
    {seq: 3, time: 1006, type: 'assistant/message', data: {turn: 1, message: {id: 'child-answer', content: [{type: 'text', text: '子执行正文'}]}}},
    {seq: 4, time: 1007, type: 'turn/end', data: {turn: 1, reason: {kind: 'completed'}}},
  ];
  const errors: unknown[] = [];
  const runtime: RuntimePort = {
    onNotification: () => () => {},
    request: async (method, input) => {
      const args = input as {afterSeq?: number};
      if (method === 'session.work.workers.confirm') {
        const ids = new Set((input as {changes:{id:string}[]}).changes.map(row=>row.id));
        pendingWorkers=pendingWorkers.filter(row=>!ids.has(row.id));
        return {};
      }
      if (method === 'session.work.check') return {rootSettled:true};
      if (method === 'session.work.children') return {children:[{kind:'child',id:'child',parentId:'main',throughSeq:4,modelVersion:'done'}]};
      const isChild=method==='session.work.child';
      const events=isChild ? child : source;
      const after=args.afterSeq??-1;
      const throughSeq=isChild ? (after<2?2:4) : (after<4?4:after<10?10:15);
      return {workerChanges:isChild ? [] : pendingWorkers,events:events.filter(event=>event.seq>after && event.seq<=throughSeq),durable:true,
        modelRuns:[],modelVersion:'done',throughSeq,more:throughSeq<events.at(-1)!.seq};
    },
  };
  const makeProduct = (online: boolean) => new GlobalAgent({nodeId: node.node, ownerId: 'alice', agents: [{agentId: 'global', workspace: center.dir, revision: '1', provider: 'fixture', model: 'fixture-model', mode: 'global'}],
    store, inbox, runtime, relay: {ready: online, request: (type, payload) => node.frames.send(type, payload)}, image: async () => '', onError: error => errors.push(error)});
  let product = makeProduct(true);
  cleanups.push(() => product.stop());
  await product.recover();
  await expect.poll(()=>inbox.workProcessingPending).toBe(false);
  const produced = inbox.journalSeq;
  expect(inbox.journal(0).some(event => event.type === 'tool_end')).toBe(true);
  expect(inbox.workCheckpoints('main')).toMatchObject({main: {throughSeq: 15}, child: {throughSeq: 4}});
  const makeSync = (url: string) => new WorkSync({nodeId: node.node, inbox, url, credentials: () => node.runtime, onError: error => errors.push(error)});
  let sync = makeSync(center.base); cleanups.push(() => sync.stop()); sync.start();
  await expect.poll(() => inbox.throughSeq, {timeout: 10000}).toBe(produced);
  expect(errors).toEqual([]);
  const read = () => center.http('GET', '/im/v1/agents/global/work', undefined, center.tokens.alice);
  const first = await read(); expect(first.status, first.body).toBe(200);
  expect(first.body).toMatchObject({main_session_id: 'main', main_execution: 'idle', record_sync_state: 'current'});
  expect(first.body.turns[0].items).toEqual(expect.arrayContaining([
    expect.objectContaining({payload:expect.objectContaining({text:'报表已确认',source_kind:'worker-report'})}),
    expect.objectContaining({payload:expect.objectContaining({text:'正在核对附件',source_worker_id:'b-worker'})}),
  ]));
  expect(first.body.turns[0].items.some((item:{payload:{source_session_id?:string}})=>item.payload.source_session_id==='b-worker')).toBe(false);
  const graph = (query:string) => center.http('GET','/im/v1/agents/global/work/delegation?window=2h&limit=1'+query,undefined,center.tokens.alice);
  const page = (await graph('')).body;
  expect(page.next_cursor).toBe('a-worker');
  expect(page.nodes.find((node:{scope:string})=>node.scope==='worker')).toEqual({
    session_id:'a-worker',parent_session_id:'main',scope:'worker',runtime:'codex',title:'核对报表',
    status:'completed',turn_id:null,last_active_at:new Date(workerTime+11).toISOString(),ancestor_only:false,
  });
  const next = (await graph('&after_session=a-worker&until='+encodeURIComponent(page.until))).body;
  expect(next.nodes).toContainEqual(expect.objectContaining({session_id:'b-worker',runtime:'dsh',status:'running'}));
  expect(first.body.other_executions.map((row:{session_id:string})=>row.session_id)).toEqual(['child']);
  expect((await center.http('GET','/im/v1/agents/global/work/sessions/b-worker/turns',undefined,center.tokens.alice)).status).toBe(404);
  expect(first.body.turns[1]).toMatchObject({status: 'completed', usage: {context_used: 12, output: 3, context_window: 8192}, elapsed_ms: 8});
  expect(first.body.turns[1].usage.total_tokens).toBeUndefined();
  const tool = first.body.turns[1].items.find((item: {item_id: string}) => item.item_id === 'tool:write');
  expect(tool.payload).toMatchObject({input: {path: 'report.txt', content}, detail: {content: output}, status: 'completed', duration_ms: 4});
  expect(first.body.other_executions).toContainEqual(expect.objectContaining({session_id: 'child', parent_session_id: 'main', scope: 'subagent'}));
  const childPage = await center.http('GET', '/im/v1/agents/global/work/sessions/child/turns', undefined, center.tokens.alice);
  expect(childPage.body.turns[0]).toMatchObject({status: 'completed', usage: null});
  expect((await read()).body).toEqual(first.body);

  // The retained WS route rejects the same malformed stable fields without committing.
  const invalid = await node.frames.send('agent.work.append', {node_id: node.node, journal_id: inbox.journalId, from_seq: produced + 1,
    events: [{seq: produced + 1, event_id: 'malformed', root_agent_id: 'global', session_id: 'main', turn_id: '1', type: 'tool_end', payload: {presentation: {summary: 7}}}]});
  expect(invalid.type).toBe('error');
  const path = `/im/v1/gateway/work-sync/journals/${inbox.journalId}`;
  expect((await center.http('GET', path, undefined, node.runtime)).body.through_seq).toBe(produced);

  await sync.stop(); await product.stop(); node.socket.terminate();
  center.child.kill('SIGTERM'); await once(center.child, 'exit');
  const restarted = await start(center.dbPath);
  product = makeProduct(false); await product.recover();
  await expect.poll(()=>inbox.workProcessingPending).toBe(false);
  expect(inbox.journalSeq).toBe(produced);
  sync = makeSync(restarted.base); sync.start();
  const small = inbox.journal(0).filter(event => !['tool_start', 'tool_end'].includes(event.type));
  for (const event of small) {
    const duplicate = await restarted.http('POST', `${path}/events`, {from_seq: event.seq, events: [event]}, node.runtime);
    expect(duplicate.status, duplicate.body).toBe(200);
    expect(duplicate.body.through_seq).toBe(produced);
  }
  const restored = await restarted.http('GET', '/im/v1/agents/global/work', undefined, restarted.tokens.alice);
  expect(restored.body.turns).toEqual(first.body.turns);
  expect(restored.body.other_executions).toEqual(first.body.other_executions);
  expect(restored.body.revision).toBe(first.body.revision);
  expect(errors).toEqual([]);
}, 30000);

it('writes one plain-text Global message and attributes the actual relay receipt to its original turn', async () => {
  const center=await start(),node=await bind(center);
  const chat=await center.http('POST','/im/v1/conversations',{
    title:'Publication receipt',type:'direct',participants:[{type:'agent',id:'global'}],
  },center.tokens.alice);
  expect(chat.status,chat.body).toBe(201);
  const store=new NodeStore(join(center.dir,'publication-node.db'),'alice');
  const inboxPath = join(center.dir,'publication-inbox.db');
  let inbox = new InboxStore(inboxPath);
  cleanups.push(()=>store.close(),()=>inbox.close());
  store.bind({agentId:'global',sessionId:'publication-root',conversationId:'global:global',ownerId:'alice',cwd:center.dir,revision:'1'});
  const events: RuntimeEvent[] = [
    {seq:1,time:1,type:'turn/start',data:{turn:1}},
    {seq:2,time:2,type:'turn/end',data:{turn:1,reason:{kind:'completed'}}},
    {seq:4,time:4,type:'turn/start',data:{turn:3}},
    {seq:5,time:5,type:'tool/call',data:{turn:3,callId:'send',name:'send_message',arguments:'{}'}},
    {seq:6,time:6,type:'turn/end',data:{turn:3,reason:{kind:'completed'}}},
  ];
  const makeProduct = () => new GlobalAgent({nodeId:node.node,ownerId:'alice',agents:[{agentId:'global',workspace:center.dir,revision:'1',provider:'fixture',model:'fixture',mode:'global'}],
    store,inbox,image:async()=>'',onError:error=>{throw error;},
    runtime:{onNotification:()=>()=>{},request:async (method, params) => {
      if (method === 'session.publication') {
        expect(params).toMatchObject({sessionId:'publication-root',callId:'send',afterSeq:-1});
        return {durable:true,call:{turn:3,seq:5},reads:[],throughSeq:5,head:5};
      }
      if (method === 'session.work.root') return {durable:true,events,throughSeq:6,more:false,modelRuns:[],modelVersion:'done'};
      if (method === 'session.work.children') return {children:[]};
      return {status:'idle'};
    }},
    relay:{request:(type,payload)=>node.frames.send(type,payload)}});
  let product = makeProduct();
  cleanups.push(()=>product.stop());
  const text='已收到，按原计划执行。';
  const call={method:'send_message',args:{target:chat.body.id,text},operationId:'publication-root:send',callId:'send',
    sessionId:'publication-root',rootSessionId:'publication-root',agentId:'global',ownerId:'alice'};
  const receipt=await product.call(call);
  expect(receipt).toMatchObject({status:'sent',message_id:expect.any(String)});
  expect(inbox.workCut(call.sessionId)).toBeUndefined();
  expect(JSON.parse(inbox.publication(call.operationId)!.result!)).toMatchObject({conversation_id:chat.body.id});
  expect(await product.call(call)).toEqual(receipt);
  const messages=await center.http('GET',`/im/v1/conversations/${chat.body.id}/messages`,undefined,center.tokens.alice);
  expect(messages.status,messages.body).toBe(200);
  expect(messages.body.items).toMatchObject([{type:'message',message:{id:(receipt as {message_id:string}).message_id,content:text}}]);
  expect(inbox.journal(0)).toEqual([]);

  await product.stop(); inbox.close();
  inbox = new InboxStore(inboxPath);
  product = makeProduct();
  await product.recover();
  expect(inbox.journal(0).filter(row=>row.type==='message_sent')).toMatchObject([{turn_id:'3',payload:{text,call_id:'send'}}]);
  const upload = await center.http('POST', `/im/v1/gateway/work-sync/journals/${inbox.journalId}/events`,
    {from_seq:1,events:inbox.journal(0)}, node.runtime);
  expect(upload.status, upload.body).toBe(200);
  const work = await center.http('GET', '/im/v1/agents/global/work', undefined, center.tokens.alice);
  expect(work.status, work.body).toBe(200);
  expect(work.body.turns.map((turn: {turn_id:string}) => turn.turn_id)).toEqual(['3','1']);
},20_000);
