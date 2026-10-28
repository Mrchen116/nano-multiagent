import { expect, it } from 'vitest';
import { DatabaseSync } from 'node:sqlite';
import { start, bind, cleanups } from './helpers.js';

it('rejects malformed stable chat fields before message, event or retry identity is committed', async () => {
  const center = await start(), node = await bind(center);
  const created = await center.http('POST', '/im/v1/conversations', {title: 'Boundary', type: 'direct', participants: [{type: 'agent', id: 'assistant'}]}, center.tokens.alice);
  expect(created.status, created.body).toBe(201);
  const cid = created.body.id;
  const started = await node.frames.send('node.streaming_delta', {node_id: node.node, kind: 'turn_start', agent_id: 'assistant', conversation_id: cid, idempotency_key: 'boundary-turn'});
  const mid = started.payload.message_id;
  expect(typeof mid, started).toBe('string');
  const db = new DatabaseSync(center.dbPath); cleanups.push(() => db.close());
  const before = db.prepare('SELECT count(*) AS n FROM conversation_events').get();
  for (const input of [
    {kind: 'message_delta', delta_text: {text: 'invalid'}, idempotency_key: 'same-key'},
    {kind: 'tool_call_upserted', tool_call: {id: {bad: true}}},
    {kind: 'permission_request', run_id: 'run', permission_request: {request_id: 'request', options: [{id: {bad: true}}]}},
    {kind: 'reply_process', item: {item_id: {bad: true}}},
  ]) {
    const response = await node.frames.send('node.streaming_delta', {node_id: node.node, message_id: mid, ...input});
    expect(response.type, response).toBe('error');
  }
  expect(db.prepare('SELECT count(*) AS n FROM conversation_events').get()).toEqual(before);
  expect(db.prepare('SELECT * FROM message_delta_idempotency WHERE message_id=?').all(mid)).toEqual([]);
  expect(db.prepare('SELECT content,tool_calls_json,permission_request_json,reply_process_json FROM messages WHERE id=?').get(mid))
    .toEqual({content: '', tool_calls_json: null, permission_request_json: null, reply_process_json: null});
  const delta = {node_id: node.node, kind: 'message_delta', message_id: mid, delta_text: '原文😀', idempotency_key: 'same-key'};
  await node.frames.send('node.streaming_delta', delta);
  await node.frames.send('node.streaming_delta', delta);
  await node.frames.send('node.streaming_delta', {node_id: node.node, kind: 'message_completed', message_id: mid});
  await node.frames.send('node.streaming_delta', {...delta, delta_text: 'late', idempotency_key: 'late'});
  expect(db.prepare('SELECT content,delivery_status FROM messages WHERE id=?').get(mid)).toEqual({content: '原文😀', delivery_status: 'completed'});
}, 20000);
