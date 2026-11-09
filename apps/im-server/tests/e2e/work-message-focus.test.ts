import {DatabaseSync} from 'node:sqlite';
import {expect, it} from 'vitest';
import {start, bind} from './helpers.js';

it('reads one exact reply summary across a thousand persisted wakes and a retired main execution', async () => {
  const f = await start();
  const g = await bind(f, 'focus-node');
  let seq = 0;
  const events: Array<{seq: number; event_id: string; root_agent_id: string; session_id: string; type: string; payload: object; turn_id?: string}> = [];
  const add = (type: string, payload: object, turn_id?: string, session_id = 'focus-main') => events.push({
    seq: ++seq, event_id: `focus-${seq}`, root_agent_id: 'global', session_id, type, payload, ...(turn_id ? {turn_id} : {}),
  });
  const append = async () => {
    while (events.length) {
      const batch = events.splice(0, 100);
      expect((await g.frames.send('agent.work.append', {
        node_id: g.node, journal_id: 'focus', from_seq: batch[0]!.seq, events: batch,
      })).payload.through_seq).toBe(batch.at(-1)!.seq);
    }
  };
  add('session_registered', {scope: 'global_main'});
  for (let turn = 1; turn <= 1000; turn++) {
    add('turn_start', {origin: 'inbox'}, String(turn));
    add('message_sent', {call_id: `send-${turn}`, message_id: `reply-${turn}`, conversation_id: 'chat', text: `Reply ${turn}`}, String(turn));
    if (turn < 1000) add('turn_end', {completed: true}, String(turn));
  }
  // A duplicate delivery identity must continue to resolve to the first fact.
  add('message_sent', {call_id: 'later', message_id: 'reply-1', conversation_id: 'chat'}, '1000');
  await append();

  const base = '/im/v1/agents/global/work';
  const read = (path: string, token = f.tokens.alice) => f.http('GET', path, undefined, token);
  const focus = (id: string) => read(`${base}/focus?message_id=${id}`);
  const direct = await focus('reply-1');
  expect(direct.status).toBe(200);
  expect(direct.body).toEqual({focus: {newer_turn_id: '2', turn: expect.objectContaining({
    session_id: 'focus-main', turn_id: '1', seq: expect.any(Number), items: [], items_deferred: true,
  })}});
  expect((await focus('reply-999')).body.focus).toMatchObject({newer_turn_id: '1000', turn: {turn_id: '999'}});
  expect((await focus('reply-1000')).body.focus).toMatchObject({newer_turn_id: null, turn: {turn_id: '1000'}});
  expect((await focus('not-synced')).body).toEqual({focus: null});

  // Exercise the legacy scan over the identical history to count requests and summaries.
  let cursor: string | null = null;
  let pages = 0;
  const allTurns: string[] = [];
  do {
    const response = await read(`${base}?view=summary&message_id=reply-1${cursor ? `&before_turn=${cursor}` : ''}`);
    expect(response.status).toBe(200);
    expect(response.body.focus).toEqual({session_id: 'focus-main', turn_id: '1'});
    expect(response.body.main_execution).toBe('running');
    allTurns.push(...response.body.turns.map((turn: {turn_id: string}) => turn.turn_id));
    cursor = response.body.next_cursor;
    pages++;
  } while (cursor && pages < 51);
  expect(pages).toBe(50);
  expect(allTurns).toEqual(Array.from({length: 1000}, (_, i) => String(1000 - i)));
  expect((await read(`${base}/sessions/focus-main/turns/1/items`)).body.items[0].payload.work_facts[0]).toMatchObject({
    type: 'message_sent', message_id: 'reply-1',
  });

  // Seed the retained identity that an actual session replacement would leave.
  const db = new DatabaseSync(f.dbPath);
  try {
    db.exec("UPDATE agent_work_sessions SET payload=json_set(payload,'$.retired',json('true')) WHERE session_id='focus-main'");
    db.exec("UPDATE users SET membership_status='pending',personal_space_enabled=1 WHERE id='outsider'");
  } finally { db.close(); }
  add('session_registered', {scope: 'global_main'}, undefined, 'new-main');
  add('turn_start', {origin: 'inbox'}, '1', 'new-main');
  await append();
  const ordinary = await read(`${base}?view=summary`);
  expect(ordinary.body).toMatchObject({main_session_id: 'new-main', other_executions: [{session_id: 'focus-main', retired: true}]});
  expect((await focus('reply-1')).body).toEqual(direct.body);
  expect((await read('/im/v1/agents/assistant/work/focus?message_id=reply-1')).status).toBe(404);
  expect((await read(`${base}/focus?message_id=reply-1`, f.tokens.outsider)).status).toBe(404);
  expect((await f.http('GET', `${base}/focus?message_id=reply-1`)).status).toBe(401);
});
