import {DatabaseSync} from 'node:sqlite';
import {expect, it} from 'vitest';
import {bind, start} from './helpers.js';

it('serves authorized light summaries, exact and paged execution links, and same-sequence item replacements', async () => {
  const f = await start();
  const g = await bind(f, 'bounded-work-node');
  const base = '/im/v1/agents/global/work';
  const root = 'work-main';
  let seq = 0;
  const append = async (facts: Array<[type: string, payload: object, turn?: string]>) => {
    const events = facts.map(([type, payload, turn_id]) => {
      const position = ++seq;
      return {seq: position, event_id: `bounded-${position}`, root_agent_id: 'global', session_id: root, type, payload, turn_id};
    });
    const response = await g.frames.send('agent.work.append', {node_id: g.node, journal_id: 'bounded', from_seq: events[0]!.seq, events});
    expect(response.payload.through_seq).toBe(seq);
  };
  await append([
    ['session_registered', {scope: 'global_main'}],
    ['turn_start', {origin: 'inbox'}, 'first'],
    ['turn_end', {completed: true, usage: {output: 12}}, 'first'],
    ['turn_start', {origin: 'inbox'}, 'second'],
    ['tool_start', {call_id: 'call-a', name: 'read'}, 'second'],
    ['tool_start', {call_id: 'call-b', name: 'agent'}, 'second'],
    ['message_sent', {message_id: 'reply', call_id: 'send', conversation_id: 'chat'}, 'first'],
    ['control_result', {command: 'compact', text: 'large control body'.repeat(4096)}],
  ]);
  const db = new DatabaseSync(f.dbPath);
  try {
    const session = db.prepare('INSERT INTO agent_work_sessions VALUES(?,?,?,?,?,?)');
    for (let i = 0; i < 1050; i++) session.run(`child-${String(i).padStart(4, '0')}`, 'global', g.node, 'subagent', root,
      JSON.stringify({scope: 'subagent', child_agent_id: 'worker', ...(i === 1049 ? {parent_tool_call_id: 'call-a'} : {})}));
    session.run('other-parent', 'global', g.node, 'subagent', 'child-0000', '{"scope":"subagent","child_agent_id":"worker"}');
    session.run('retired', 'global', g.node, 'global_main', null, '{"scope":"global_main","retired":true}');
    db.exec("UPDATE users SET membership_status='pending',personal_space_enabled=1 WHERE id='outsider'");
  } finally { db.close(); }
  const read = (path: string, token = f.tokens.bob) => f.http('GET', base + path, undefined, token);
  const legacy = (await read('?view=summary')).body;
  const modern = (await read('?view=summary&catalog=separate&limit=1')).body;
  expect(legacy.other_executions).toHaveLength(1052);
  expect(legacy.control_items[0].payload.text).toHaveLength('large control body'.length * 4096);
  expect(modern).toMatchObject({
    catalog: 'separate', main_session_id: root, latest_main_usage: {turn_id: 'first', output: 12},
    other_executions: [], control_items: [], next_turn_id: 'second', next_cursor: 'bounded-8',
    turns: [{turn_id: 'bounded-8', origin: 'context_compaction', items: [{kind: 'control_result', payload: {command: 'compact'}}]}],
  });
  expect(JSON.stringify(modern)).not.toContain('large control body');
  const ordinary = (await read('?view=summary&catalog=separate&limit=1&before_turn=' + modern.next_cursor)).body;
  expect(ordinary).toMatchObject({next_turn_id: 'first', next_cursor: 'second',
    turns: [{turn_id: 'second', items: [], items_deferred: true, usage: null}]});
  expect(ordinary.turns[0]).not.toHaveProperty('tool_count');
  expect((await read(`/sessions/${root}/turns?catalog=separate&before_turn=second`)).body).toMatchObject({
    catalog: 'separate', turns: [{turn_id: 'first', items: [], items_deferred: true}], control_items: [], next_cursor: null,
  });
  expect((await read('/focus?message_id=reply&catalog=separate')).body.focus).toMatchObject({
    turn: {turn_id: 'first', items: [], items_deferred: true}, newer_turn_id: 'second', older_turn_id: null,
  });
  expect((await read('/focus?message_id=reply&catalog=separate')).body.focus.turn).not.toHaveProperty('has_background_returns');
  expect((await read(`/sessions/${root}/controls`)).body.items[0].payload.command).toBe('compact');

  const catalog = (await read('/sessions?limit=2')).body;
  expect(catalog).toMatchObject({sessions: [{session_id: 'child-0000'}, {session_id: 'child-0001'}], next_cursor: 'child-0001'});
  expect((await read('/sessions?limit=2&after_session=child-0001')).body.sessions.map((s: {session_id: string}) => s.session_id))
    .toEqual(['child-0002', 'child-0003']);
  expect((await read('/sessions/child-1049')).body).toMatchObject({session_id: 'child-1049'});
  expect((await read('/sessions/retired')).body).toMatchObject({retired: true});
  expect((await read('/sessions?after_session=retired')).body).toEqual({sessions: [], next_cursor: null});
  expect((await read('/sessions?historical=1')).body).toMatchObject({
    sessions: [{session_id: 'retired'}], next_cursor: null,
  });
  const scoped = `/sessions?parent_session_id=${root}&child_agent_id=worker`;
  expect((await read(scoped + '&tool_call_id=call-a')).body).toMatchObject({sessions: [{session_id: 'child-1049'}], next_cursor: null});
  const weak = (await read(scoped + '&tool_call_id=late&limit=1')).body;
  expect(weak).toMatchObject({sessions: [{session_id: 'child-0000'}], next_cursor: 'weak:child-0000', match_mode: 'weak'});
  await append([['session_linked', {parent_session_id: root, child_session_id: 'child-0000', parent_tool_call_id: 'late', child_agent_id:'worker'}]]);
  expect((await read(scoped + '&tool_call_id=late&limit=1')).body).toMatchObject({sessions: [{session_id: 'child-0000'}], next_cursor:null, match_mode:'exact'});
  expect((await read(scoped + '&tool_call_id=late&limit=1&after_session=' + weak.next_cursor)).body)
    .toMatchObject({sessions: [{session_id:'child-0001'}],match_mode:'weak'});
  expect((await read('/sessions?child_agent_id=worker&after_session=weak:child-1049')).body).toMatchObject({sessions: [{session_id: 'other-parent'}]});
  expect((await read('/sessions?limit=NaN')).status).toBe(400);
  expect((await read('/sessions', f.tokens.outsider)).status).toBe(404);
  expect((await read('/sessions/child-1049', f.tokens.outsider)).status).toBe(404);
  expect((await read(`/sessions/${root}/controls`, f.tokens.outsider)).status).toBe(404);
  expect((await f.http('GET', base + '/sessions')).status).toBe(401);

  const details = `/sessions/${root}/turns/second/items?catalog=separate&limit=1`;
  const initial = (await read(details)).body;
  expect(initial.items[0]).toMatchObject({item_id:'tool:call-a',has_exact_child:true});
  const older = (await read(details + '&after_seq=' + initial.next_cursor)).body;
  expect(older.items[0]).toMatchObject({item_id: 'tool:call-b', payload: {status: 'running'}});
  await append([
    ['tool_end', {call_id: 'call-b', name: 'agent', presentation: {summary: 'Finished'}}, 'second'],
    ['tool_end', {call_id: 'call-a', name: 'agent', presentation: {summary: 'Complete'}}, 'second'],
  ]);
  const change = (await read(details + '&after_revision=' + initial.revision)).body;
  expect(change.items[0]).toMatchObject({item_id: 'tool:call-b', seq: older.items[0].seq, payload: {output: 'Finished', status: 'completed'}});
  expect(change.next_cursor).toBe(String(change.revision));
  const next = (await read(details + '&after_revision=' + change.revision)).body;
  expect(next.items[0]).toMatchObject({item_id: 'tool:call-a', seq: initial.items[0].seq, payload: {output: 'Complete'}});
  expect(next.next_cursor).toBeNull();
  expect((await read(details + '&after_revision=' + next.revision)).body).toEqual({items: [], next_cursor: null, revision: next.revision});
});
