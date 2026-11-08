import {expect, it} from 'vitest';
import {start, bind} from './helpers.js';

it('resolves each delivered reply to its exact persisted wake beyond the latest page', async () => {
  const f = await start();
  const g = await bind(f, 'focus-node');
  let seq = 0;
  const events: any[] = [];
  const add = (type: string, payload: object, turn_id?: string) => events.push({seq: ++seq, event_id: `focus-${seq}`, root_agent_id: 'global', session_id: 'focus-main', type, payload, ...(turn_id ? {turn_id} : {})});
  add('session_registered', {scope: 'global_main'});
  for (let turn = 1; turn <= 25; turn++) {
    add('turn_start', {origin: 'inbox'}, String(turn));
    add('message_sent', {call_id: `send-${turn}`, message_id: `reply-${turn}`, conversation_id: 'chat', text: `Reply ${turn}`}, String(turn));
    if (turn < 25) add('turn_end', {completed: true}, String(turn));
  }
  expect((await g.frames.send('agent.work.append', {node_id: g.node, journal_id: 'focus', from_seq: 1, events})).payload.through_seq).toBe(seq);
  const read = (query = '') => f.http('GET', `/im/v1/agents/global/work?view=summary${query}`, undefined, f.tokens.alice);
  expect((await read()).body.turns.map((t: any) => t.turn_id)).not.toContain('1');
  for (const turn of [1, 24, 1]) {
    const focused = await read(`&message_id=reply-${turn}&limit=2`);
    expect(focused.status, focused.body).toBe(200);
    expect(focused.body.focus).toEqual({session_id: 'focus-main', turn_id: String(turn)});
    // A reply is an expansion/scroll anchor, never a filter on the Work list.
    expect(focused.body.turns.map((t: any) => t.turn_id)).toEqual(['25', '24']);
    expect(focused.body.turns[0]).toMatchObject({session_id: 'focus-main', items_deferred: true});
    expect(focused.body.main_execution).toBe('running'); // Historical completion is not current Agent state.
    const allTurns = [...focused.body.turns];
    let cursor = focused.body.next_cursor;
    while (cursor) {
      const earlier = await read(`&message_id=reply-${turn}&before_turn=${cursor}&limit=2`);
      expect(earlier.status).toBe(200);
      allTurns.push(...earlier.body.turns);
      cursor = earlier.body.next_cursor;
    }
    expect(allTurns.map((t: any) => t.turn_id)).toEqual(Array.from({length: 25}, (_, i) => String(25 - i)));
  }
  const items = await f.http('GET', '/im/v1/agents/global/work/sessions/focus-main/turns/1/items', undefined, f.tokens.alice);
  expect(items.body.items[0].payload.work_facts[0]).toMatchObject({type: 'message_sent', message_id: 'reply-1'});
  expect((await read('&message_id=not-synced')).body.focus).toBeNull();
  // A delivery belonging to this Agent never resolves through a different root.
  const other = await f.http('GET', '/im/v1/agents/assistant/work?message_id=reply-1', undefined, f.tokens.alice);
  expect(other.status).toBe(404);
  expect((await f.http('GET', '/im/v1/agents/global/work?message_id=reply-1')).status).toBe(401);
});
