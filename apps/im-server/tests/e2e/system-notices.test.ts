import { expect, it } from 'vitest';
import { once } from 'node:events';
import WebSocket from 'ws';
import { DatabaseSync } from 'node:sqlite';
import { Frames, start, bind, cleanups } from './helpers.js';

it('publishes a complete localized-notice snapshot once and preserves it on retry and history load', async () => {
  const f = await start(), g = await bind(f);
  const created = await f.http('POST', '/im/v1/conversations', {
    title: 'Notice chat', type: 'direct', participants: [{ type: 'agent', id: 'assistant' }],
  }, f.tokens.alice);
  expect(created.status, created.body).toBe(201);
  const conversation = created.body.id;
  const ticket = await f.http('POST', '/im/v1/auth/ws-ticket', {}, f.tokens.alice);
  const browser = new WebSocket(`${f.base.replace('http:', 'ws:')}/im/ws/user?ticket=${ticket.body.ticket}`, {
    headers: { Origin: 'http://127.0.0.1:8011' },
  });
  const events = new Frames(browser);
  await once(browser, 'open');
  cleanups.push(() => browser.terminate());
  browser.send(JSON.stringify({ op: 'resume', after_event_id: 0 }));
  const payload = {
    node_id: g.node, conversation_id: conversation, idempotency_key: 'knowledge:review',
    text: '· background self-evolution review: skills updated',
    system_notice: { kind: 'self_evolution_review', source_agent_id: 'assistant', updated_targets: ['skills'] },
  };
  const sent = await g.frames.send('node.system_message', payload);
  expect(sent.type, sent).toBe('ack');
  const live = await events.next(frame => frame.event_type === 'message.created' && frame.message_id === sent.payload.message_id);
  expect(live.data.system_notice).toMatchObject(payload.system_notice);
  expect(live.data.system_notice.source_agent_display_name).toBeTruthy();
  const retry = await g.frames.send('node.system_message', payload);
  expect(retry.payload.message_id).toBe(sent.payload.message_id);
  const history = await f.http('GET', `/im/v1/conversations/${conversation}/messages`, undefined, f.tokens.alice);
  const messages = history.body.items.filter((item: any) => item.type === 'message');
  expect(messages).toHaveLength(1);
  expect(messages[0].message.system_notice).toEqual(live.data.system_notice);
  const db = new DatabaseSync(f.dbPath, { readOnly: true });
  try {
    const notifications = db.prepare('SELECT event_type,payload_json FROM conversation_events WHERE message_id=?').all(sent.payload.message_id);
    expect(notifications).toHaveLength(1);
    expect(notifications[0]!.event_type).toBe('message.created');
    expect(JSON.parse(String(notifications[0]!.payload_json)).system_notice).toEqual(live.data.system_notice);
  } finally { db.close(); }
}, 20_000);
