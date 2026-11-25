import { cliWorkerRuntimes } from '@nano/product-contracts';
import { once } from 'node:events';
import { DatabaseSync } from 'node:sqlite';
import { expect, it } from 'vitest';
import { openDatabase } from '../../src/db.js';
import { bind, start } from './helpers.js';

it.each(cliWorkerRuntimes)('%s Work preserves exact focus, live activity, tool records and per-worker usage', async (runtime) => {
  const f = await start();
  const g = await bind(f, 'work-summary-node');
  const base = '/im/v1/agents/global/work';
  const journal = 'summaries';
  const now = Date.now();
  const recent = new Date(now - 1000).toISOString();
  const yesterday = new Date(now - 24 * 3600_000).toISOString();
  const lastWeek = new Date(now - 7 * 24 * 3600_000).toISOString();
  type Fact = [session: string, type: string, payload: object, turn?: string, time?: string | null, eventId?: string];
  let seq = 0;
  const append = async (facts: Fact[]) => {
    const events = facts.map(([session_id, type, payload, turn_id, observed_at = recent, eventId]) => {
      const position = ++seq;
      return {seq: position, event_id: eventId ?? `summary-${position}`, root_agent_id: 'global', session_id, type, payload, turn_id, observed_at: observed_at ?? undefined};
    });
    const response = await g.frames.send('agent.work.append', {node_id: g.node, journal_id: journal, from_seq: events[0]!.seq, events});
    expect(response.payload.through_seq, JSON.stringify(response)).toBe(seq);
  };
  const read = (path: string, token = f.tokens.bob) => f.http('GET', base + path, undefined, token);
  const status = (pending: boolean) => f.http('GET', `/im/v1/gateway/work-sync/journals/${journal}`, undefined, g.runtime, {
    'x-work-produced-seq': String(seq), 'x-work-processing-pending': String(pending),
  });

  await append([
    ['root', 'session_registered', {scope: 'global_main'}],
    ['root', 'turn_started', {origin: 'inbox'}, 'first'],
    ['root', 'turn_end', {usage: {total_tokens: 100}}, 'first'],
    ['root', 'message_sent', {message_id: 'old-reply', call_id: 'send', conversation_id: 'chat'}, 'first'],
    ['root', 'session_linked', {parent_session_id: 'root', child_session_id: 'legacy-dream', title: 'Dreaming · 提取任务摘要'}],
    ['legacy-dream', 'turn_started', {origin: 'dreaming'}, 'same-id'],
    ['legacy-dream', 'turn_end', {status: 'failed'}, 'same-id'],
    ['root', 'turn_started', {origin: 'heartbeat'}, 'same-id'],
    ['root', 'turn_end', {usage: {output: 5}}, 'same-id'],
    ['root', 'session_linked', {parent_session_id: 'root', child_session_id: 'new-dream', maintenance_kind: 'dreaming', maintenance_stage: 'consolidate', title: 'Dreaming · 整合长期记忆'}],
    ['new-dream', 'turn_started', {origin: 'dreaming'}, 'dream-new'],
    ['new-dream', 'turn_end', {model_request_state: 'none', tool_count: 0, usage: {total_tokens: 0}}, 'dream-new'],
    ['root', 'turn_started', {origin: 'inbox'}, 'last'],
    ['root', 'tool_start', {call_id: 'x', name: 'read', presentation: {label: '读取文件'}}, 'last'],
    ['parent', 'session_registered', {scope: 'subagent', parent_session_id: 'root', child_agent_id: 'parent', title: 'Parent'}],
    ['parent', 'turn_started', {}, 'p1', yesterday],
    ['parent', 'turn_end', {usage: {total_tokens: 30}}, 'p1', yesterday],
    ['child', 'session_registered', {scope: 'subagent', parent_session_id: 'parent', child_agent_id: 'child', title: 'Nested'}],
    ['child', 'turn_started', {}, 'c0', lastWeek],
    ['child', 'turn_end', {usage: {total_tokens: 3}}, 'c0', lastWeek],
    ['child', 'turn_started', {}, 'c1'],
    ['child', 'turn_end', {usage: {total_tokens: 7}}, 'c1'],
    ['child', 'turn_started', {}, 'c2'],
    ['child', 'turn_end', {usage: {total_tokens: 8}}, 'c2', null],
    ['child', 'turn_started', {}, 'c3'],
    ['child', 'permission_request', {request_id: 'approval', options: [{id: 'allow'}]}, 'c3'],
    ['running', 'session_registered', {scope: 'subagent', parent_session_id: 'root', child_agent_id: 'running'}],
    ['running', 'turn_started', {}, 'r'],
    ['workflow', 'session_registered', {scope: 'workflow', parent_session_id: 'root', workflow_run_id: 'wf'}],
    ['workflow', 'turn_started', {}, 'w'],
    ['root', 'session_linked', {parent_session_id: 'root', child_session_id: 'unknown-link', title: 'Ambiguous link'}],
  ]);

  const prefix = '?catalog=separate&view=summary&timeline=combined&limit=2';
  const head = await read(prefix);
  expect(head.status, head.body).toBe(200);
  expect(head.body).toMatchObject({timeline: 'combined', turns: [
    {session_id: 'root', turn_id: 'last'},
    {session_id: 'new-dream', turn_id: 'dream-new', maintenance_stage: 'consolidate', tool_count: 0, model_request_state: 'none', usage: {total_tokens: 0}},
  ], next_turn_id: 'same-id', next_turn_seq: 8});
  const more = await read(prefix + '&before_seq=' + head.body.next_cursor);
  expect(more.status, more.body).toBe(200);
  expect(more.body.turns).toMatchObject([{session_id: 'root', turn_id: 'same-id'}, {session_id: 'legacy-dream', turn_id: 'same-id'}]);
  expect(more.body.turns[1]).not.toHaveProperty('tool_count');
  expect((await read(prefix + '&before_seq=' + more.body.next_cursor)).body).toMatchObject({turns: [{session_id: 'root', turn_id: 'first'}], next_cursor: null});
  expect((await read('?catalog=separate&limit=2')).body.turns.map((turn: {session_id: string}) => turn.session_id)).toEqual(['root', 'root']);
  expect((await read('/focus?message_id=old-reply&catalog=separate')).body.focus.turn.turn_id).toBe('first');

  await append([
    ['root', 'control_result', {command: 'compact', status: 'completed'}, 'last'],
    ['root', 'control_result', {command: 'compact', status: 'failed', manual: true, duration_ms: 42, error: 'Compaction was interrupted'}],
  ]);
  const compactPage = (await read(prefix.replace('limit=2', 'limit=1'))).body;
  const compact = compactPage.turns[0];
  expect(compact).toMatchObject({origin: 'context_compaction', status: 'failed', started_at: recent,
    items: [{kind: 'control_result', payload: {manual: true, duration_ms: 42, error: 'Compaction was interrupted'}}]});
  expect((await read(prefix + '&before_seq=' + compactPage.next_cursor)).body.turns[0].turn_id).toBe('last');
  const sessionPage = '/sessions/root/turns?catalog=separate&view=summary&limit=1';
  expect((await read(sessionPage)).body.next_cursor).toBe(compact.turn_id);
  expect((await read(sessionPage + '&before_turn=' + compact.turn_id)).body.turns[0].turn_id).toBe('last');
  expect((await read('/sessions/root/turns/last/items?view=preview')).body.items).toEqual(expect.arrayContaining([
    expect.objectContaining({kind: 'control_result', payload: expect.objectContaining({status: 'completed'})}),
  ]));

  expect((await status(true)).status).toBe(200);
  const syncing = await read('/activity');
  expect(syncing.status, syncing.body).toBe(200);
  expect(syncing.body).toMatchObject({record_sync_state: 'catching_up', main_execution: 'unknown', running_count: null});
  expect((await status(false)).status).toBe(200);
  const incomplete = (await read('/activity')).body;
  expect(incomplete).toMatchObject({revision: syncing.body.revision, record_sync_state: 'current',
    main_execution: 'running', latest_tool: {name: 'read', label: '读取文件', turn_id: 'last', item_id: 'tool:x'}, running_count: null});
  await append([
    ['unknown-link', 'session_registered', {scope: 'subagent', parent_session_id: 'root', child_agent_id: 'unknown-link'}],
    ['root', 'session_linked', {parent_session_id: 'root', child_session_id: 'skills-review', title: '技能复盘'}, undefined, undefined, 'knowledge-run:skills-review'],
    ['old-running', 'session_registered', {scope: 'subagent', parent_session_id: 'root', child_agent_id: 'running'}],
    ['old-running', 'turn_started', {}, 'stale-running', yesterday],
    ['running', 'turn_started', {}, 'current-running'],
  ]);
  await status(false);
  expect((await read('/activity?limit=1')).body).toMatchObject({
    running_count: 1, waiting_permission_count: 1, sessions: [{session_id: 'running', status: 'running'}], next_cursor: null,
  });
  expect((await read('/activity?after_session=child')).body).toMatchObject({sessions: [{session_id: 'running'}], next_cursor: null});

  const graph = await read('/delegation?window=2h&limit=1');
  expect(graph.status, graph.body).toBe(200);
  expect(graph.body).toMatchObject({
    next_cursor: 'child', nodes: [
      {session_id: 'child', parent_session_id: 'parent', ancestor_only: false, usage: {total_tokens: 18, reported_turns: 3, missing_turns: 0}},
      {session_id: 'parent', parent_session_id: 'root', ancestor_only: true, usage: {total_tokens: 30, reported_turns: 1, missing_turns: 0}},
      {session_id: 'root', usage: {total_tokens: 100, reported_turns: 1, missing_turns: 1}},
    ],
  });
  const nextGraph = await read('/delegation?window=2h&after_session=child&until=' + encodeURIComponent(graph.body.until));
  expect(nextGraph.body).toMatchObject({from: graph.body.from, until: graph.body.until, nodes: [
    {session_id: 'old-running'}, {session_id: 'root'}, {session_id: 'running'}, {session_id: 'workflow', scope: 'workflow'},
  ], next_cursor: null});
  const broad = (await read('/delegation?window=3d')).body.nodes;
  expect(broad.find((node: {session_id: string}) => node.session_id === 'parent')).toMatchObject({ancestor_only: false, usage: {total_tokens: 30}});

  expect(broad.find((node: {session_id: string}) => node.session_id === 'child').usage)
    .toEqual(graph.body.nodes[0].usage);
  await append([['child', 'turn_end', {usage: {total_tokens: 9}}, 'c1', null]]);
  const corrected = (await read('/delegation?window=2h')).body.nodes;
  expect(corrected.find((node: {session_id: string}) => node.session_id === 'child').usage)
    .toEqual({total_tokens: 20, reported_turns: 3, missing_turns: 0});

  const db = new DatabaseSync(f.dbPath);
  try {
    db.exec("UPDATE users SET membership_status='pending',personal_space_enabled=1 WHERE id='outsider'");
    db.prepare(`INSERT INTO agent_work_sessions VALUES('retired','global',?,'global_main',NULL,'{"retired":true}')`).run(g.node);
    db.exec(`INSERT INTO agent_work_turns VALUES
      ('retired','retired-turn',1,'{"status":"unknown","run_id":"prior-run","usage":{"total_tokens":50}}');
      DELETE FROM agent_work_lifetime_usage;
      DELETE FROM schema_migrations WHERE version='work-lifetime-usage-v1';`);
    db.prepare(`INSERT INTO agent_work_events(event_id,root_agent_id,session_id,type,observed_at,payload)
      VALUES('retired-end','global','retired','run_completed',?,'{"run_id":"prior-run","usage":{"total_tokens":50}}')`).run(lastWeek);
  } finally { db.close(); }
  openDatabase(f.dbPath).close();
  openDatabase(f.dbPath).close();
  const recovered = (await read('/delegation?window=2h')).body.nodes;
  expect(recovered.find((node: {session_id: string}) => node.session_id === 'root').usage)
    .toEqual({total_tokens: 150, reported_turns: 2, missing_turns: 1});
  expect(recovered.find((node: {session_id: string}) => node.session_id === 'child').usage)
    .toEqual({total_tokens: 20, reported_turns: 3, missing_turns: 0});
  expect(recovered.some((node: {session_id: string}) => node.session_id === 'retired')).toBe(false);
  expect((await read('/activity', f.tokens.outsider)).status).toBe(404);
  expect((await read('/delegation', f.tokens.outsider)).status).toBe(404);

  const worker = {parent_session_id: 'root', title: '审查修改', runtime, call_id: 'dispatch'};
  for (const state of ['starting', 'running', 'completed']) {
    await append([['worker', 'worker_state', {...worker, status: state}]]);
    await status(false);
    const active = state === 'running';
    const page = (await read('/activity?after_session=running')).body;
    expect(page).toMatchObject({
      running_count: active ? 2 : 1, waiting_permission_count: 1,
      sessions: active ? [{session_id: 'worker', scope: 'worker', status: state, title: worker.title}] : [],
      next_cursor: null,
    });
  }

  const reopen = {...worker, status:'running'};
  const rootItems = '/sessions/root/turns/last/items?view=preview';
  const cliTurns = '/sessions/worker/turns';
  const invalidWorkerEvent = async (session_id: string, type: string, payload: object, turn_id?: string) => {
    const position = seq + 1;
    const response = await g.frames.send('agent.work.append', {node_id:g.node,journal_id:journal,from_seq:position,
      events:[{seq:position,event_id:`invalid-${position}`,root_agent_id:'global',session_id,type,payload,turn_id}]});
    expect(response.type).toBe('error');
  };
  await append([
    ['worker','worker_state',{...reopen, has_work_records:true, worker_records_revision:10}],
    ['dsh-worker','worker_state',{...reopen, runtime:'dsh', call_id:'other-dispatch'}],
    ['root','tool_start',{name:'delegate_worker',call_id:'dispatch',arguments:{action:'start'}},'last'],
    ['root','tool_start',{name:'delegate_worker',call_id:'send',arguments:{action:'send',worker_id:'worker',message:'x'.repeat(5000)}},'last'],
    ['root','tool_start',{name:'send_message',call_id:'native-send',arguments:{agent_id:'worker'}},'last'],
    ['root','message',{message_id:'report',source_session_id:'worker',source_kind:'worker-report',text:'报告'},'last'],
  ]);
  expect((await read(cliTurns)).status).toBe(404);
  expect((await read('/sessions?parent_session_id=root&tool_call_id=dispatch')).body.sessions).toEqual([]);
  expect((await read(rootItems)).body.items.find((item:{item_id:string})=>item.item_id==='message:report').payload.source_session_id).toBeUndefined();
  const relationRevision = (await read('?catalog=separate&view=summary')).body.worker_records_revision;
  await invalidWorkerEvent('worker','worker_state',{...reopen,runtime:'dsh'});
  await invalidWorkerEvent('worker','worker_state',{...reopen,call_id:'different'});
  await invalidWorkerEvent('worker','worker_state',{...reopen,title:'不同派工'});
  await invalidWorkerEvent('dsh-worker','message',{text:'不应接收'},'d');
  await invalidWorkerEvent('worker','permission_request',{request_id:'unbound'},'t');
  await append([
    ['worker','turn_started',{model:'test-model'},'cli-turn'],
    ['worker','tool_start',{name:'exec',call_id:'cmd',arguments:{command:'pwd'},presentation:{label:'读取目录'}},'cli-turn'],
  ]);
  await status(false);
  const firstDetailRevision = (await read('?catalog=separate&view=summary')).body.worker_records_revision;
  expect(firstDetailRevision).toBeGreaterThan(relationRevision);
  expect((await read('/sessions/worker')).body).toMatchObject({runtime,has_work_records:true,parent_tool_call_id:'dispatch'});
  expect((await read('/sessions?parent_session_id=root&tool_call_id=dispatch')).body.sessions).toMatchObject([{session_id:'worker'}]);
  const itemRows = (await read(rootItems)).body.items as Array<{item_id:string;payload:Record<string,unknown>}>;
  for (const id of ['tool:dispatch','tool:send','tool:native-send'])
    expect(itemRows.find(item=>item.item_id===id)?.payload.child_session_id).toBe('worker');
  expect(itemRows.find(item=>item.item_id==='message:report')?.payload.source_session_id).toBe('worker');
  expect((await read('/activity')).body.sessions).toContainEqual(expect.objectContaining({session_id:'worker',status:'running',
    has_work_records:true,turn_id:'cli-turn',latest_tool:expect.objectContaining({name:'exec',item_id:'tool:cmd',status:'running'})}));
  expect((await read(cliTurns,f.tokens.outsider)).status).toBe(404);
  expect((await f.http('POST','/im/v1/agents/global/trajectory/prepare',{session_id:'worker'},f.tokens.alice)).status).toBe(404);
  await append([['worker','worker_state',{...reopen,status:'interrupted'}]]);
  expect((await read(cliTurns)).body.turns).toMatchObject([{turn_id:'cli-turn',status:'interrupted',finished_at:recent}]);
  expect((await read('/delegation')).body.nodes.find((row:{session_id:string})=>row.session_id==='worker')).toMatchObject({
    has_work_records:true,status:'interrupted',usage:{total_tokens:null,reported_turns:0,missing_turns:1}});
  await append([['worker','turn_end',{status:'failed',error:'进程失败',usage:{context_used:4200,context_window:100000,output:5,cache_read_tokens:10,cache_total_input_tokens:20,total_tokens:25}},'cli-turn']]);
  expect((await read(cliTurns)).body.turns).toMatchObject([{
    status:'failed',
    error:'进程失败',
    usage:{context_used:4200,context_window:100000,output:5,cache_read_tokens:10,cache_total_input_tokens:20,total_tokens:25},
  }]);
  expect((await read('/delegation')).body.nodes.find((row:{session_id:string})=>row.session_id==='worker').usage)
    .toEqual({total_tokens:25,reported_turns:1,missing_turns:0});
  expect((await read('?catalog=separate&view=summary')).body.worker_records_revision).toBe(firstDetailRevision);

  const closed = once(g.socket, 'close');
  g.socket.terminate();
  await closed;
  await expect.poll(async () => (await read('/activity')).body.node_connection_state).toBe('offline');
  expect((await read('/activity')).body).toMatchObject({record_sync_state: 'unknown', running_count: null, waiting_permission_count: null});
});
