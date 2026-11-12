import { once } from 'node:events';
import { DatabaseSync } from 'node:sqlite';
import { expect, it } from 'vitest';
import { bind, start } from './helpers.js';

it('pages main and Dreaming facts without affecting exact reply focus and reports own usage on the delegation tree', async () => {
  const f = await start();
  const g = await bind(f, 'work-summary-node');
  const base = '/im/v1/agents/global/work';
  const journal = 'summaries';
  const now = Date.now();
  const recent = new Date(now - 1000).toISOString();
  const yesterday = new Date(now - 24 * 3600_000).toISOString();
  type Fact = [session: string, type: string, payload: object, turn?: string, time?: string, eventId?: string];
  let seq = 0;
  const append = async (facts: Fact[]) => {
    const events = facts.map(([session_id, type, payload, turn_id, observed_at = recent, eventId]) => {
      const position = ++seq;
      return {seq: position, event_id: eventId ?? `summary-${position}`, root_agent_id: 'global', session_id, type, payload, turn_id, observed_at};
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
    ['child', 'turn_started', {}, 'c1'],
    ['child', 'turn_end', {usage: {total_tokens: 7}}, 'c1'],
    ['child', 'turn_started', {}, 'c2'],
    ['child', 'turn_end', {usage: {total_tokens: 8}}, 'c2'],
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
    running_count: 1, waiting_permission_count: 1, sessions: [{session_id: 'child', parent_session_id: 'parent', status: 'waiting_permission'}], next_cursor: 'child',
  });
  expect((await read('/activity?after_session=child')).body).toMatchObject({sessions: [{session_id: 'running'}], next_cursor: null});

  const graph = await read('/delegation?window=2h&limit=1');
  expect(graph.status, graph.body).toBe(200);
  expect(graph.body).toMatchObject({
    next_cursor: 'child', nodes: [
      {session_id: 'child', parent_session_id: 'parent', ancestor_only: false, usage: {total_tokens: 15, reported_turns: 2, missing_turns: 0}},
      {session_id: 'parent', parent_session_id: 'root', ancestor_only: true, usage: {total_tokens: null}},
      {session_id: 'root', usage: {total_tokens: 100, reported_turns: 1, missing_turns: 1}},
    ],
  });
  const nextGraph = await read('/delegation?window=2h&after_session=child&until=' + encodeURIComponent(graph.body.until));
  expect(nextGraph.body).toMatchObject({from: graph.body.from, until: graph.body.until, nodes: [
    {session_id: 'old-running'}, {session_id: 'root'}, {session_id: 'running'}, {session_id: 'workflow', scope: 'workflow'},
  ], next_cursor: null});
  const broad = (await read('/delegation?window=3d')).body.nodes;
  expect(broad.find((node: {session_id: string}) => node.session_id === 'parent')).toMatchObject({ancestor_only: false, usage: {total_tokens: 30}});

  const db = new DatabaseSync(f.dbPath);
  try {
    db.exec("UPDATE users SET membership_status='pending',personal_space_enabled=1 WHERE id='outsider'");
  } finally { db.close(); }
  expect((await read('/activity', f.tokens.outsider)).status).toBe(404);
  expect((await read('/delegation', f.tokens.outsider)).status).toBe(404);

  const closed = once(g.socket, 'close');
  g.socket.terminate();
  await closed;
  await expect.poll(async () => (await read('/activity')).body.node_connection_state).toBe('offline');
  expect((await read('/activity')).body).toMatchObject({record_sync_state: 'unknown', running_count: null, waiting_permission_count: null});
});
