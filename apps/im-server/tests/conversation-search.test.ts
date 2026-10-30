import { expect, it } from 'vitest';
import { Work } from '../src/work.js';
import { personalFixture } from './personal-fixture.js';

it('finds multiple literal clues, ranks relevance or recency and reads around a match', () => {
  const { ctx, principal, args } = personalFixture();
  const add = (content: string, created_at: string) => ctx.messaging.insertMessage('peer', 'u1', 'user', content, [], null, 'completed', { created_at });
  const prior = add('先讨论', '2026-01-01T00:00:00Z');
  const match = add('方案已经更新，周四准备发布', '2026-01-02T00:00:00Z');
  const next = add('改到周五吧', '2026-01-03T00:00:00Z');
  const recent = add('今天发布了 ERR-42', '2026-02-01T00:00:00Z');
  const work = new Work(ctx);
  const query = (input: Record<string, unknown>) => work.query(principal, { ...args, ...input });

  expect(query({ action: 'search', keywords: ['发布', '周四', '方案'] }).messages.map((m: any) => m.message_id)).toEqual([match.id, recent.id]);
  expect(query({ action: 'search', keywords: ['发布', '周四', '方案'], sort: 'recent' }).messages.map((m: any) => m.message_id)).toEqual([recent.id, match.id]);
  expect(query({ action: 'search', query: 'ERR-42' }).messages.map((m: any) => m.message_id)).toEqual([recent.id]);
  expect(query({ action: 'search', keywords: ['发布'], target: 'peer', participant_id: 'u1', after: '2026-02-01T00:00:00Z' }).messages.map((m: any) => m.message_id)).toEqual([recent.id]);
  expect(() => query({ action: 'search', query: '发布', keywords: ['方案'] })).toThrow();
  expect(query({ action: 'read', target: 'peer', around_message_id: match.id }).messages.map((m: any) => m.message_id)).toEqual([prior.id, match.id, next.id, recent.id]);
});

it('keeps snapshot order and rechecks current permissions on every page', () => {
  const { ctx, db, service, principal, args } = personalFixture();
  const older = ctx.messaging.insertMessage('peer', 'u1', 'user', '发布方案', [], null, 'completed', { created_at: '2026-01-01T00:00:00Z' });
  ctx.messaging.insertMessage('chat', 'u1', 'user', '发布方案', [], null, 'completed', { created_at: '2026-02-01T00:00:00Z' });
  const work = new Work(ctx);
  const query = (input: Record<string, unknown>) => work.query(principal, { ...args, ...input });
  const first = query({ action: 'search', keywords: ['发布'], limit: 1 });
  expect(first.has_more).toBe(true);
  ctx.messaging.insertMessage('chat', 'u1', 'user', '发布方案', [], null, 'completed', { created_at: '2026-03-01T00:00:00Z' });
  expect(query({ action: 'search', keywords: ['发布'], limit: 1, cursor: first.next_cursor }).messages.map((m: any) => m.message_id)).toEqual([older.id]);
  const command = ctx.messaging.insertMessage('chat', 'u1', 'user', 'Do not read peer');
  service.sources(principal, { ...args, action: 'exclude', conversation_id: 'peer', source_message_id: command.id, expected_revision: 1 });
  expect(query({ action: 'search', keywords: ['发布'], limit: 1, cursor: first.next_cursor }).messages).toEqual([]);
  expect(db.prepare('SELECT unread_count FROM conversation_participants WHERE conversation_id=? AND user_id=?').get('peer', 'u1')).toEqual({ unread_count: 0 });
});

it('does not combine fragments from changed messages or unverifiable legacy cursors', () => {
  const { ctx, db, principal, args } = personalFixture();
  const message = ctx.messaging.insertMessage('peer', 'u1', 'user', `长${'x'.repeat(25000)}`, [], null, 'completed');
  const work = new Work(ctx);
  const query = (input: Record<string, unknown>) => work.query(principal, { ...args, ...input });
  const first = query({ action: 'search', query: '长', limit: 1 });
  expect(first.messages[0]).toMatchObject({ message_id: message.id, part_key: '0', total_parts: 2 });
  expect(query({ action: 'search', query: '长', limit: 1, cursor: first.next_cursor }).messages[0]).toMatchObject({ message_id: message.id, part_key: '1', total_parts: 2 });
  const legacy = JSON.parse(Buffer.from(first.next_cursor, 'base64url').toString());
  delete legacy.version; delete legacy.fingerprint;
  const legacyCursor = Buffer.from(JSON.stringify(legacy)).toString('base64url');
  expect(() => query({ action: 'search', query: '长', limit: 1, cursor: legacyCursor })).toThrow('partial_cursor_expired_restart_query');
  db.prepare('UPDATE messages SET content=? WHERE id=?').run(`长${'y'.repeat(25000)}`, message.id);
  expect(() => query({ action: 'search', query: '长', limit: 1, cursor: first.next_cursor })).toThrow('partial_cursor_expired_restart_query');
  expect(() => query({ action: 'search', query: '长', limit: 1, cursor: legacyCursor })).toThrow('partial_cursor_expired_restart_query');
});

it('filters external messages by their actual sender rather than their mirror account', () => {
  const { ctx, db, principal, args } = personalFixture();
  db.prepare("UPDATE conversations SET external_source='feishu' WHERE id='peer'").run();
  const one = ctx.messaging.insertMessage('peer', 'u1', 'user', '发布方案', [], null, 'completed', { sender_source_id: 'ou-one' });
  ctx.messaging.insertMessage('peer', 'u1', 'user', '发布方案', [], null, 'completed', { sender_source_id: 'ou-two' });
  const unknown = ctx.messaging.insertMessage('peer', 'u1', 'user', '发布方案（旧镜像无发言人身份）', [], null, 'completed');
  const work = new Work(ctx);
  const query = (input: Record<string, unknown>) => work.query(principal, { ...args, ...input });
  expect(query({ action: 'search', target: 'peer', query: '发布', sender_source_id: 'ou-one' }).messages.map((m: any) => m.message_id)).toEqual([one.id]);
  expect(query({ action: 'search', target: 'peer', query: '发布', participant_id: 'u1' }).messages).toEqual([]);
  const all = query({ action: 'search', target: 'peer', query: '发布' }).messages;
  expect(all.find((m: any) => m.message_id === one.id).sender).toMatchObject({ kind: 'external', source_id: 'ou-one' });
  expect(all.find((m: any) => m.message_id === one.id).sender).not.toHaveProperty('id');
  expect(all.find((m: any) => m.message_id === unknown.id).sender).not.toHaveProperty('id');
  expect(all.find((m: any) => m.message_id === unknown.id).sender).not.toHaveProperty('is_owner');
  expect(() => query({ action: 'search', query: '发布', sender_source_id: 'ou-one' })).toThrow();
});

it('rejects new filters on a legacy snapshot instead of silently reusing its old order', () => {
  const { ctx, db, principal, args } = personalFixture();
  ctx.messaging.insertMessage('peer', 'u1', 'user', 'first', [], null, 'completed');
  ctx.messaging.insertMessage('peer', 'u1', 'user', 'second', [], null, 'completed');
  const work = new Work(ctx), query = (input: Record<string, unknown>) => work.query(principal, { ...args, ...input });
  const first = query({ action: 'search', limit: 1 });
  const cursor = JSON.parse(Buffer.from(first.next_cursor, 'base64url').toString());
  const row = db.prepare('SELECT data FROM agent_work_query_snapshots WHERE snapshot_id=?').get(cursor.snapshot) as { data: string };
  const snapshot = JSON.parse(row.data);
  for (const key of ['version', 'keywords', 'sort', 'sender_source_id', 'around_message_id']) delete snapshot[key];
  db.prepare('UPDATE agent_work_query_snapshots SET data=? WHERE snapshot_id=?').run(JSON.stringify(snapshot), cursor.snapshot);
  delete cursor.version;
  const legacyCursor = Buffer.from(JSON.stringify(cursor)).toString('base64url');
  expect(query({ action: 'search', limit: 1, cursor: legacyCursor }).messages).toHaveLength(1);
  expect(() => query({ action: 'search', limit: 1, cursor: legacyCursor, sort: 'recent' })).toThrow('invalid_cursor');
  expect(() => query({ action: 'search', limit: 1, cursor: legacyCursor, keywords: ['first'] })).toThrow('invalid_cursor');
});

it('keeps an anchored window fixed while newer messages arrive', () => {
  const { ctx, principal, args } = personalFixture();
  const ids: string[] = [];
  for (let day = 1; day <= 8; day++) ids.push(ctx.messaging.insertMessage('peer', 'u1', 'user', `day ${day}`, [], null, 'completed', { created_at: `2026-01-0${day}T00:00:00Z` }).id);
  const work = new Work(ctx), query = (input: Record<string, unknown>) => work.query(principal, { ...args, ...input });
  const first = query({ action: 'read', target: 'peer', around_message_id: ids[3], limit: 2 });
  ctx.messaging.insertMessage('peer', 'u1', 'user', 'new later message', [], null, 'completed', { created_at: '2026-01-09T00:00:00Z' });
  const seen = first.messages.map((m: any) => m.message_id);
  let cursor = first.next_cursor;
  while (cursor) {
    const page = query({ action: 'read', target: 'peer', around_message_id: ids[3], limit: 2, cursor });
    seen.push(...page.messages.map((m: any) => m.message_id)); cursor = page.next_cursor;
  }
  expect(seen).toEqual(ids);
});
