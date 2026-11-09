import { expect, it, vi } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { openDatabase } from '../src/db.js';
import { searchMessages } from '../src/message-search.js';
import Fastify from 'fastify';
import { Work } from '../src/work.js';
import { registerMessagingRoutes } from '../src/messaging.js';
import { personalFixture } from './personal-fixture.js';

it('searches messages using the signed-in user’s current read access and paginates without reading', async () => {
  const { ctx, db } = personalFixture();
  const app = Fastify();
  registerMessagingRoutes(app, ctx);
  try {
    db.prepare("INSERT INTO conversations(id,title,type,visibility,created_at) VALUES('public','Public','group','public',datetime('now')),('private','Private','group','private',datetime('now'))").run();
    const old = ctx.messaging.insertMessage('peer', 'u1', 'user', '发布 older', [], null, 'completed', {created_at:'2025-01-01T00:00:00Z'});
    const recent = ctx.messaging.insertMessage('public', 'u2', 'user', '发布 recent', [], null, 'completed', {created_at:'2026-01-01T00:00:00Z'});
    ctx.messaging.insertMessage('private', 'u2', 'user', '发布 secret');
    const before = db.prepare("SELECT unread_count FROM conversation_participants WHERE conversation_id='peer' AND user_id='u1'").get();
    const first = await app.inject({url:'/im/v1/messages/search?q=%E5%8F%91%E5%B8%83&limit=1', headers:{'x-user':'u1'}});
    expect(first.statusCode).toBe(200);
    expect(first.json().messages.map((m:any)=>m.message_id)).toEqual([recent.id]);
    const next = await app.inject({url:`/im/v1/messages/search?q=%E5%8F%91%E5%B8%83&limit=1&cursor=${encodeURIComponent(first.json().next_cursor)}`, headers:{'x-user':'u1'}});
    expect(next.json().messages.map((m:any)=>m.message_id)).toEqual([old.id]);
    const group = await app.inject({url:'/im/v1/messages/search?q=%E5%8F%91%E5%B8%83&kind=group', headers:{'x-user':'u1'}});
    expect(group.json().messages.map((m:any)=>m.message_id)).toEqual([recent.id]);
    expect(db.prepare("SELECT unread_count FROM conversation_participants WHERE conversation_id='peer' AND user_id='u1'").get()).toEqual(before);
    db.prepare("DELETE FROM conversation_participants WHERE conversation_id='peer' AND user_id='u1'").run();
    const revoked = await app.inject({url:`/im/v1/messages/search?q=%E5%8F%91%E5%B8%83&limit=1&cursor=${encodeURIComponent(first.json().next_cursor)}`, headers:{'x-user':'u1'}});
    expect(revoked.json().messages).toEqual([]);
  } finally { await app.close(); }
});

it('finds visible pure card text in Web and Agent history without matching actions or unrendered statements', async () => {
  const { ctx, principal, args } = personalFixture();
  const app = Fastify(); registerMessagingRoutes(app, ctx);
  try {
    const source = [
      'root = Col([Title($heading), Table(["方案"], [["预算对照", "overflow-secret"]]), Svg([SvgText("分流节点", 20, 20, 12)], "0 0 80 40"), Map([MapMarker("云桥公园", 31, 121)]), Chart("bar", [{region: "华东区域", budget: 18, note: "chart-secret"}], "region", ["budget"]), Button("复制", @CopyToClipboard("action-secret"))])',
      '$heading = "周五安排"',
      'unused = Text("unused-secret")',
    ].join('\n');
    const card = ctx.messaging.insertMessage('chat', 'a1', 'agent', '', [], null, 'completed', {
      interactive: { format:'openui', catalog_version:'nano-iui-1', source },
    });
    const query = (keyword: string) => app.inject({url:`/im/v1/messages/search?q=${encodeURIComponent(keyword)}`, headers:{'x-user':'u1'}});
    for (const keyword of ['周五安排', '预算对照', '分流节点', '云桥公园', '华东区域']) {
      const response = await query(keyword);
      expect(response.statusCode).toBe(200);
      expect(response.json().messages).toEqual([expect.objectContaining({message_id:card.id,snippet:expect.stringContaining(keyword)})]);
    }
    for (const keyword of ['action-secret','unused-secret','overflow-secret','chart-secret','CopyToClipboard']) expect((await query(keyword)).json().messages).toEqual([]);
    const work = new Work(ctx);
    const other = ctx.messaging.insertMessage('chat','u1','user','预算对照');
    const result = work.query(principal, {...args,action:'search',target:'chat',keywords:['周五安排','预算对照']});
    expect(result.messages.map((m: {message_id:string})=>m.message_id)).toEqual([card.id,other.id]);
    expect(result.messages[0]).toMatchObject({interactive:{source},content:[],complete_message:true});
  } finally { await app.close(); }
});

it('backfills existing cards for keyword search when opening an older database', () => {
  const { ctx, db } = personalFixture();
  const source = 'root = Text("Old card content")';
  const card = ctx.messaging.insertMessage('chat','a1','agent','',[],null,'completed',{
    interactive:{format:'openui',catalog_version:'nano-iui-1',source},
  });
  const directory = mkdtempSync(join(tmpdir(),'nano-card-search-'));
  const path = join(directory,'im.sqlite');
  try {
    db.prepare('VACUUM INTO ?').run(path);
    const legacy = new DatabaseSync(path);
    try {
      legacy.exec("ALTER TABLE message_interactive DROP COLUMN search_text; DELETE FROM schema_migrations WHERE version='interactive-search-text-v1'");
    } finally { legacy.close(); }
    const migrated = openDatabase(path);
    try {
      expect(searchMessages(migrated,{targets:['chat'],terms:['Old card content'],action:'search'}).map(row=>row.id)).toEqual([card.id]);
      expect(migrated.prepare('SELECT source FROM message_interactive WHERE message_id=?').get(card.id)).toEqual({source});
    } finally { migrated.close(); }
  } finally { rmSync(directory,{recursive:true,force:true}); }
});

it('shows readable mentions and preserves a Feishu sender when display name is missing', async () => {
  const { ctx, db } = personalFixture();
  const app = Fastify(); registerMessagingRoutes(app, ctx);
  try {
    db.prepare("UPDATE conversations SET external_source='feishu' WHERE id='peer'").run();
    ctx.messaging.insertMessage('peer','u1','user','<mention type="user" target_id="u2"/> please review needle',[],null,'completed',{sender_source_id:'ou-other'});
    const response = await app.inject({url:'/im/v1/messages/search?q=needle',headers:{'x-user':'u1'}});
    expect(response.json().messages[0]).toMatchObject({sender_name:'ou-other',snippet:'@u2 please review needle'});
  } finally { await app.close(); }
});

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

it('reads a UI-only message by ID and as one complete history item', () => {
  const { ctx, principal, args } = personalFixture();
  const older = ctx.messaging.insertMessage('chat', 'u1', 'user', 'Earlier message');
  const source = 'root = Text("Editable proposal")';
  const card = ctx.messaging.insertMessage('chat', 'a1', 'agent', '', [], null, 'completed', {
    interactive: { format: 'openui', catalog_version: 'nano-iui-1', source },
  });
  ctx.messaging.insertMessage('chat', 'a1', 'agent', '', [], null, 'running');
  const work = new Work(ctx);
  const read = (input: Record<string, unknown>) => work.query(principal, { ...args, action: 'read', target: 'chat', ...input });

  const exact = read({ message_id: card.id });
  expect(exact.messages).toEqual([expect.objectContaining({
    message_id: card.id, content: [], part_key: '0', total_parts: 1, complete_message: true,
  })]);
  expect(exact.messages[0].interactive).toEqual({ source });
  expect(exact.next_cursor).toBeNull();

  const first = read({ limit: 1 });
  expect(first.messages).toEqual(exact.messages);
  expect(first.next_cursor).toBeTruthy();
  expect(read({ limit: 1, cursor: first.next_cursor }).messages.map((message: { message_id: string }) => message.message_id)).toEqual([older.id]);
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

it('continues long messages across pages', () => {
  const { ctx, principal, args } = personalFixture();
  const message = ctx.messaging.insertMessage('peer', 'u1', 'user', `长${'x'.repeat(25000)}`, [], null, 'completed');
  const work = new Work(ctx);
  const query = (input: Record<string, unknown>) => work.query(principal, { ...args, ...input });
  const first = query({ action: 'search', query: '长', limit: 1 });
  expect(first.messages[0]).toMatchObject({ message_id: message.id, part_key: '0', total_parts: 2 });
  expect(query({ action: 'search', query: '长', limit: 1, cursor: first.next_cursor }).messages[0]).toMatchObject({ message_id: message.id, part_key: '1', total_parts: 2 });
});

it('distinguishes external senders from internal messages in a shadow conversation', async () => {
  const { ctx, db, principal, args } = personalFixture();
  db.prepare("UPDATE conversations SET external_source='feishu' WHERE id='peer'").run();
  const one = ctx.messaging.insertMessage('peer', 'u1', 'user', '发布方案', [], null, 'completed', { sender_source_id: 'ou-one' });
  ctx.messaging.insertMessage('peer', 'u1', 'user', '发布方案', [], null, 'completed', { sender_source_id: 'ou-two' });
  const internal = await ctx.messaging.sendMessage({ headers: {}, params: { conversation_id: 'peer' }, query: {},
    body: { sender_user_id: 'u1', content: '发布方案（内部 IM 发言）' } } as any);
  const work = new Work(ctx);
  const query = (input: Record<string, unknown>) => work.query(principal, { ...args, ...input });
  expect(query({ action: 'search', target: 'peer', query: '发布', sender_source_id: 'ou-one' }).messages.map((m: any) => m.message_id)).toEqual([one.id]);
  expect(query({ action: 'search', target: 'peer', query: '发布', participant_id: 'u1' }).messages.map((m: any) => m.message_id)).toEqual([internal.id]);
  const all = query({ action: 'search', target: 'peer', query: '发布' }).messages;
  expect(all.find((m: any) => m.message_id === one.id).sender).toMatchObject({ kind: 'external', source_id: 'ou-one' });
  expect(all.find((m: any) => m.message_id === one.id).sender.name).toBe('ou-one');
  expect(all.find((m: any) => m.message_id === one.id).sender).not.toHaveProperty('id');
  expect(all.find((m: any) => m.message_id === internal.id).sender).toMatchObject({ id: 'u1', kind: 'user', is_owner: true });
  expect(() => query({ action: 'search', query: '发布', sender_source_id: 'ou-one' })).toThrow();
});

it.each([1, 2])('preserves main v%s snapshots and rejects changes to their query', version => {
  const { ctx, db, principal, args } = personalFixture();
  ctx.messaging.insertMessage('peer', 'u1', 'user', 'first', [], null, 'completed');
  ctx.messaging.insertMessage('peer', 'u1', 'user', 'second', [], null, 'completed');
  const work = new Work(ctx), query = (input: Record<string, unknown>) => work.query(principal, { ...args, ...input });
  const first = query({ action: 'search', limit: 1 });
  const cursor = JSON.parse(Buffer.from(first.next_cursor, 'base64url').toString());
  const row = db.prepare('SELECT data FROM agent_work_query_snapshots WHERE snapshot_id=?').get(cursor.snapshot) as { data: string };
  const snapshot = JSON.parse(row.data);
  for (const key of ['memory_cutoff', 'memory_after']) delete snapshot[key];
  if (version === 1) for (const key of ['version', 'keywords', 'sort', 'sender_source_id', 'around_message_id']) delete snapshot[key];
  db.prepare('UPDATE agent_work_query_snapshots SET data=? WHERE snapshot_id=?').run(JSON.stringify(snapshot), cursor.snapshot);
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

it('does no extra search queries for unrelated private groups and hydrates no chats on a miss', async () => {
  const { ctx, db } = personalFixture();
  db.exec("DELETE FROM conversations");
  const group = db.prepare("INSERT INTO conversations(id,title,type,visibility,created_at) VALUES(?, 'Search group','group',?,datetime('now'))");
  for (let i = 0; i < 10; ++i) {
    group.run('visible-' + i, 'private');
    db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,'u1')").run('visible-' + i);
  }
  const app = Fastify();
  registerMessagingRoutes(app, ctx);
  const detail = vi.spyOn(ctx.messaging, 'conversation');
  const statements = vi.spyOn(db, 'prepare');
  async function miss() {
    statements.mockClear();
    detail.mockClear();
    const response = await app.inject('/im/v1/messages/search?q=absent&limit=1');
    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ messages: [] });
    return { sql: statements.mock.calls.length, details: detail.mock.calls.length };
  }
  try {
    const before = await miss();
    for (let i = 0; i < 1000; ++i) group.run('hidden-' + i, 'private');
    const after = await miss();
    expect(after.sql).toBe(before.sql);
    expect([before.details, after.details]).toEqual([0, 0]);
  } finally {
    await app.close();
  }
});

it('preserves each chat category, observer titles, scope and revocation on the search route', async () => {
  const { ctx, db } = personalFixture();
  // The two-Agent owner and PA binding grant independent kinds of observation.
  db.exec(`UPDATE agent_profiles SET owner_id='u1' WHERE agent_id='a';
    UPDATE users SET owner_id='u1', personal_space_enabled=1 WHERE id='u1';
    UPDATE personal_agent_bindings SET owner_id='u1';
    INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES('a2','agent:b','Beta','u2',datetime('now'));
    INSERT INTO agent_profiles(agent_id,owner_id,display_name,created_at,updated_at) VALUES('b','u2','Beta',datetime('now'),datetime('now'))`);
  const addChat = (id: string, type: string, members: string[], visibility = 'private', space = 'company:default') => {
    db.prepare('INSERT INTO conversations(id,title,type,visibility,space_id,created_at) VALUES(?,?,?,?,?,?)')
      .run(id, id, type, visibility, space, '2026-01-01');
    for (const user of members) db.prepare('INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,?)').run(id,user);
  };
  addChat('network','direct',['a1','a2']);
  addChat('observed-pa','direct',['u2','a1']);
  addChat('agent-group','group',['a1','a2'],'public');
  addChat('empty-group','group',[],'public');
  addChat('private','group',['u2']);
  addChat('extra-peer','direct',['u2','a1','a2']);
  addChat('personal','group',['u1'],'private','personal:u1');
  addChat('foreign','group',['u1'],'public','personal:u2');
  db.exec("UPDATE conversations SET dissolved_at='2026-01-02' WHERE id='empty-group'");
  for (const {id} of db.prepare('SELECT id FROM conversations').all()) {
    db.prepare(`INSERT INTO messages(id,conversation_id,sender_user_id,content,delivery_status,created_at)
      VALUES(?,?,'u2','needle','completed','2026-01-01T00:00:00Z')`).run(id,id);
  }

  const app = Fastify();
  registerMessagingRoutes(app, ctx);
  const page = async (kind: string, limit = 50, cursor = '') => {
    const response = await app.inject({url:'/im/v1/messages/search', query:{q:'NEEDLE',kind,limit:String(limit),cursor}});
    expect(response.statusCode).toBe(200);
    return response.json();
  };
  try {
    const categories = {
      'direct-user':['peer'], 'direct-agent':['observed-pa','chat'],
      'group':['personal','empty-group'], 'agent-network':['network','agent-group'],
    };
    for (const [kind, ids] of Object.entries(categories)) {
      expect((await page(kind)).messages.map((m: any) => m.message_id)).toEqual(ids);
    }
    const expected = Object.values(categories).flat().sort().reverse();
    let cursor = '';
    for (const id of expected) {
      const result = await page('all',1,cursor);
      expect(result.messages.map((m: any) => m.message_id)).toEqual([id]);
      cursor = result.next_cursor ?? '';
    }
    expect(cursor).toBe('');
    expect((await page('direct-agent')).messages[0]).toMatchObject({
      conversation_name:'u2 ↔ a1', sender_name:'u2', snippet:'needle',
    });
    db.exec("UPDATE agent_profiles SET is_stale=1 WHERE agent_id='a'");
    expect((await page('direct-agent')).messages.map((m: any) => m.message_id)).toEqual(['chat']);
    expect((await page('agent-network')).messages.map((m: any) => m.message_id)).toContain('network');
    db.exec("UPDATE users SET membership_status='suspended' WHERE id='u1'");
    expect((await page('all')).messages.map((m: any) => m.message_id)).toEqual(['personal']);
  } finally {
    await app.close();
  }
});
