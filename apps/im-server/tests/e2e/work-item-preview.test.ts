import {DatabaseSync} from 'node:sqlite';
import {expect, it} from 'vitest';
import {bind, start} from './helpers.js';

it('bounds visible and changed Work item previews while keeping authorized exact bodies available', async () => {
  const f = await start();
  const g = await bind(f, 'work-preview-node');
  const main = 'preview-main';
  const turn = 'first';
  const path = `/im/v1/agents/global/work/sessions/${main}/turns/${turn}/items`;
  const large = '工具结果\n'.repeat(14000);
  const read = (suffix: string, token = f.tokens.bob) => f.http('GET', path + suffix, undefined, token);
  let seq = 0;
  async function append(facts: Array<[type: string, payload: object, turnId?: string]>) {
    const events = facts.map(([type, payload, turn_id]) => {
      const position = ++seq;
      return {seq: position, event_id: `preview-${position}`, root_agent_id: 'global', session_id: main, type, payload, turn_id};
    });
    const response = await g.frames.send('agent.work.append', {
      node_id: g.node, journal_id: 'preview', from_seq: events[0]!.seq, events,
    });
    expect(response.payload.through_seq).toBe(seq);
  }
  await append([
    ['session_registered', {scope: 'global_main'}],
    ['turn_started', {origin: 'inbox'}, turn],
    ['tool_start', {call_id: 'tool/with:separator', name: 'read'}, turn],
    ['tool_end', {call_id: 'tool/with:separator', name: 'read', presentation: {summary: large}}, turn],
    ['tool_start', {call_id: 'running', name: 'bash'}, turn],
    ...Array.from({length: 19}, (_, index): [string, object, string] => ['message', {message_id: `short-${index}`, text: 'small'}, turn]),
    ['session_linked', {parent_session_id: main, child_session_id: 'legacy-child', parent_tool_call_id: 'legacy'}],
  ]);
  const legacyId = 'tool:legacy';
  const db = new DatabaseSync(f.dbPath);
  try {
    db.prepare("UPDATE agent_work_items SET item_id=?,kind='tool',payload=? WHERE session_id=? AND turn_id=? AND item_id='message:short-18'")
      .run(legacyId, JSON.stringify({id: 'legacy', name: 'skill', status: 'completed', duration_ms: 52, output: large}), main, turn);
    db.exec("UPDATE users SET membership_status='pending',personal_space_enabled=1 WHERE id='outsider'");
  } finally { db.close(); }

  const first = (await read('?view=preview&limit=200')).body;
  expect(first.items).toHaveLength(20);
  const item = first.items[0];
  expect(item).toMatchObject({item_id: 'tool:tool/with:separator', detail_deferred: true, payload: {name: 'read', status: 'completed'}});
  expect(item.payload.output.length).toBeLessThan(large.length);
  expect(first.items[1]).toMatchObject({item_id: 'tool:running', payload: {name: 'bash', status: 'running'}});
  expect(first.items[1]).not.toHaveProperty('detail_deferred');
  expect(first.items.every((preview: unknown) => Buffer.byteLength(JSON.stringify(preview)) <= 4096)).toBe(true);

  const next = (await read(`?view=preview&after_seq=${first.next_cursor}`)).body;
  expect(next.items).toEqual([expect.objectContaining({item_id: legacyId, payload: expect.objectContaining({name: "skill", status: "completed", duration_ms: 52}), detail_deferred: true, has_exact_child: true})]);
  expect(next.items[0].payload.output).toBe(large.slice(0, 320));
  const currentDetail = '/' + encodeURIComponent(item.item_id);
  expect((await read(currentDetail)).body).toMatchObject({item_id: item.item_id, payload: {output: large}});
  expect((await read('/' + encodeURIComponent(legacyId))).body).toMatchObject({item_id: legacyId, payload: {output: large}});
  expect((await read('?limit=1')).body.items[0]).toMatchObject({payload: {output: large}});
  expect((await read(currentDetail, f.tokens.outsider)).status).toBe(404);
  expect((await read('?view=preview', f.tokens.outsider)).status).toBe(404);
  expect((await read('/not-in-turn')).status).toBe(404);

  // A replacement revision must preserve the item's original position, even with a large body.
  await append([['tool_end', {call_id: 'running', name: 'bash', presentation: {summary: large}}, turn]]);
  const changes = (await read(`?view=preview&after_revision=${first.revision}`)).body;
  expect(changes.items[0]).toMatchObject({
    item_id: 'tool:running', seq: first.items[1].seq, detail_deferred: true, payload: {status: 'completed'},
  });
  expect(changes.items.every((preview: unknown) => Buffer.byteLength(JSON.stringify(preview)) <= 4096)).toBe(true);
});
