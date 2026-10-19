import { afterEach, expect, it } from 'vitest';
import { mkdtempSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { createServer } from '../src/server.js';
import { openDatabase } from '../src/db.js';
import { TaskGraphService } from '../src/task-graphs.js';
import { EventEmitter } from 'node:events';

const cleanups: Array<() => unknown | Promise<unknown>> = [];
afterEach(async () => { for (const close of cleanups.splice(0).reverse()) await close(); });
async function fixture() {
  const dir = mkdtempSync(join(tmpdir(), 'im-tenancy-'));
  cleanups.push(() => rmSync(dir, { recursive: true, force: true }));
  const app = await createServer({ dbPath: join(dir, 'im.db'), publicUrl: 'http://localhost', jwtSecret: 'tenancy-test-secret' });
  cleanups.push(() => app.close());
  const register = async (name: string) => app.im.identity.register(name, 'password-123', name);
  const request = (token: string, method: any, url: string, payload?: any) => app.inject({ method, url, payload, headers: { authorization: `Bearer ${token}` } });
  return { app, db: app.im.db, register, request };
}
function agent(db: DatabaseSync, id: string, owner: string, space: string) {
  db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES(?,?,?,'online')").run(id, owner, id);
  db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,space_id,work_mode,tool_allowlist_json,created_at,updated_at) VALUES(?,?,?,?,?,'global','[\"task_graph\"]','2026-01-01','2026-01-01')").run(id, owner, id, id, space);
  db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES(?,?,?,?, '2026-01-01')").run(`agent-${id}`, `agent:${id}`, id, owner);
}

it('registers a usable private account, keeps join explicit and never publishes private resources after approval', async () => {
  const { app, db, register, request } = await fixture();
  const a = await register('alice'), b = await register('bob'), admin = await register('admin');
  expect(a.user).toMatchObject({ membership_status: 'none', personal_space_enabled: true, account_status: 'active', is_company_admin: false });
  db.prepare("UPDATE users SET personal_space_enabled=0,membership_status='active',is_company_admin=1 WHERE id=?").run(admin.user.id);
  agent(db, 'private-a', a.user.id, `personal:${a.user.id}`);
  agent(db, 'private-b', b.user.id, `personal:${b.user.id}`);
  agent(db, 'company-agent', admin.user.id, 'company:default');
  const privateChat = (await request(a.access_token, 'POST', '/im/v1/conversations', {title:'Private task chat',type:'direct',participants:[{type:'agent',id:'private-a'}]})).json();
  const companyChat = (await request(admin.access_token, 'POST', '/im/v1/conversations', {title:'Company task chat',type:'group',visibility:'public',participants:[{type:'agent',id:'company-agent'}]})).json();
  expect(privateChat).toMatchObject({visibility:'private',can_write:true});
  expect(companyChat).toMatchObject({visibility:'public',can_write:true});
  expect((await request(a.access_token, 'GET', '/im/v1/conversations?scope=public')).json().items).toEqual([]);
  const tasks = new TaskGraphService(db, app.im.messaging);
  const task = tasks.execute({ kind: 'agent', id: 'private-a', node_id: 'private-a' }, 'create', { title: 'Private plan', mode: 'dag', request_key: 'create-private', conversation_id: privateChat.id });
  const company = tasks.execute({ kind: 'agent', id: 'company-agent', node_id: 'company-agent' }, 'create', { title: 'Company plan', mode: 'dag', request_key: 'create-company', conversation_id: companyChat.id });
  const contacts = (await request(a.access_token, 'GET', '/im/v1/contacts')).json().items;
  expect(contacts.map((x: any) => x.user_id).sort()).toEqual([a.user.id, 'agent-private-a'].sort());
  expect((await request(admin.access_token, 'GET', '/im/v1/company/members')).json().members.map((x: any) => x.id)).not.toContain(a.user.id);
  for (const url of ['/im/v1/contacts/agent-private-b', '/im/v1/agents/private-b/work', `/im/v1/task-graphs/${company.graph_id}`])
    expect((await request(a.access_token, 'GET', url)).statusCode, url).toBe(404);
  expect((await request(a.access_token, 'GET', '/im/v1/task-graphs')).json().items.map((x: any) => x.graph_id)).toEqual([task.graph_id]);
  expect((await request(b.access_token, 'POST', '/im/v1/conversations', { title: 'intrusion', type: 'direct', participants: [{ type: 'agent', id: 'private-a' }] })).statusCode).toBe(404);
  expect(() => tasks.execute({ kind: 'agent', id: 'private-b', node_id: 'private-b' }, 'delete', { graph_id: task.graph_id, base_revision: 1, request_key: 'delete-private' })).toThrow();
  expect((await request(a.access_token, 'POST', '/im/v1/company/join', {})).json().membership_status).toBe('pending');
  expect((await request(admin.access_token, 'POST', `/im/v1/company/members/${a.user.id}/approve`, {})).statusCode).toBe(200);
  expect((await request(a.access_token, 'GET', `/im/v1/task-graphs/${company.graph_id}`)).statusCode).toBe(200);
  expect((await request(admin.access_token, 'GET', `/im/v1/task-graphs/${task.graph_id}`)).statusCode).toBe(404);
  expect(() => tasks.execute({ kind: 'agent', id: 'private-a', node_id: 'private-a' }, 'delete', { graph_id: company.graph_id, base_revision: 1, request_key: 'delete-company' })).toThrow();
  expect((await request(admin.access_token, 'POST', `/im/v1/company/members/${a.user.id}/suspend`, {})).statusCode).toBe(200);
  expect((await request(a.access_token, 'GET', '/im/v1/me')).statusCode).toBe(401);
  const fresh = await app.im.identity.login('alice', 'password-123');
  expect((await request(fresh.access_token, 'GET', '/im/v1/agents/private-a/work')).statusCode).toBe(200);
  expect((await request(fresh.access_token, 'GET', `/im/v1/task-graphs/${company.graph_id}`)).statusCode).toBe(404);
});

it('upgrades old rows once without activating pending or suspended accounts or changing resource identifiers', () => {
  const dir = mkdtempSync(join(tmpdir(), 'im-migration-')), path = join(dir, 'old.db');
  cleanups.push(() => rmSync(dir, { recursive: true, force: true }));
  const old = new DatabaseSync(path);
  const schema = readFileSync(new URL('../src/schema.sql', import.meta.url), 'utf8')
    .replace(/personal_space_enabled INTEGER NOT NULL DEFAULT 0,\s*/g, '')
    .replace(/\s*space_id TEXT NOT NULL DEFAULT 'company:default',/g, '');
  old.exec(schema);
  old.prepare("INSERT INTO users(id,username,display_name,owner_id,membership_status,created_at) VALUES('old','old','Old','old','suspended','then')").run();
  old.prepare("INSERT INTO conversations(id,title,owner_id,created_at) VALUES('old-chat','Old','old','then')").run();
  old.close();
  for (let i = 0; i < 2; i++) {
    const db = openDatabase(path);
    expect(db.prepare('SELECT id,owner_id,membership_status,personal_space_enabled FROM users').get()).toEqual({ id: 'old', owner_id: 'old', membership_status: 'suspended', personal_space_enabled: 0 });
    expect(db.prepare('SELECT id,owner_id,space_id FROM conversations').get()).toEqual({ id: 'old-chat', owner_id: 'old', space_id: 'company:default' });
    db.close();
  }
});

it('filters live events, replay and native trajectory by current space after company revocation', async () => {
  const { app, db, register, request } = await fixture();
  const a = await register('stream-owner'), b = await register('stream-outsider'), admin = await register('stream-admin');
  db.prepare("UPDATE users SET membership_status='active' WHERE id IN (?,?)").run(a.user.id, admin.user.id);
  db.prepare("UPDATE users SET is_company_admin=1 WHERE id=?").run(admin.user.id);
  agent(db, 'stream-private', a.user.id, `personal:${a.user.id}`);
  agent(db, 'stream-company', admin.user.id, 'company:default');
  const create = async (id: string) => (await request(a.access_token, 'POST', '/im/v1/conversations', {title: id, type: 'direct', participants: [{type: 'agent', id}]})).json();
  const personal = await create('stream-private'), company = await create('stream-company');
  expect(personal.id).toBeTruthy();
  expect(company.id).toBeTruthy();
  const p = app.im.messaging.insertMessage(personal.id, a.user.id, 'user', 'private content', [], null);
  const c = app.im.messaging.insertMessage(company.id, a.user.id, 'user', 'company content', [], null);
  app.im.messaging.event(personal.id, p.id, 'message.completed', {content: p.content});
  app.im.messaging.event(company.id, c.id, 'message.completed', {content: c.content});
  app.im.identity.transition(admin.user.id, a.user.id, 'suspend');
  const fresh = await app.im.identity.login('stream-owner', 'password-123');
  const streams = [fresh, b].map(pair => {
    const frames: any[] = [];
    const socket: any = { readyState: 1, bufferedAmount: 0, send: (raw: string) => frames.push(JSON.parse(raw)), close() { this.readyState = 3; } };
    const stream = { socket, userId: pair.user.id, sessionId: app.im.identity.accessSession(pair.access_token).sid, ready: true, cursor: 0 };
    app.im.gateway.browsers.add(stream);
    return {frames, stream};
  });
  app.im.gateway.replay(streams[0]!.stream, 0);
  expect(streams[0]!.frames.map(x => x.data?.content)).toContain('private content');
  expect(streams[0]!.frames.map(x => x.data?.content)).not.toContain('company content');
  streams[0]!.frames.length = 0;
  app.im.gateway.broadcast([a.user.id], {op: 'event', conversation_id: company.id, event_type: 'message.completed', data: {content: 'hidden live'}});
  expect(streams[0]!.frames).toEqual([]);
  app.im.gateway.work.append('stream-private', {journal_id: 'private-journal', from_seq: 1, events: [{seq: 1, event_id: 'private-session', root_agent_id: 'stream-private', session_id: 'private-session', type: 'session_registered', payload: {scope: 'global_main'}}]});
  expect(streams[0]!.frames).toEqual([expect.objectContaining({event_type: 'agent.work.updated'})]);
  expect(streams[1]!.frames).toEqual([]);
  const ticket = app.im.identity.issueTicket(app.im.identity.accessSession(b.access_token).sid);
  const rejected: any[] = [];
  const socket: any = { send: (raw: string) => rejected.push(JSON.parse(raw)), close: (code: number) => rejected.push(code) };
  app.im.gateway.trajectory.browser(socket, ticket, 'stream-private', 'private-session');
  expect(rejected).toContain(1008);
  expect(rejected[0]).toMatchObject({type: 'failed'});
});

it('does not replay old private task mutation receipts after the Agent changes private owner', async () => {
  const { app, db, register, request } = await fixture();
  const before = await register('before-transfer'), after = await register('after-transfer');
  agent(db, 'transferred', before.user.id, `personal:${before.user.id}`);
  const chat = (await request(before.access_token, 'POST', '/im/v1/conversations', {title:'Transfer task chat',type:'direct',participants:[{type:'agent',id:'transferred'}]})).json();
  const tasks = new TaskGraphService(db, app.im.messaging), actor = {kind: 'agent' as const, id: 'transferred', node_id: 'transferred'};
  const created = tasks.execute(actor, 'create', {title: 'Private graph', mode: 'dag', request_key: 'create', conversation_id:chat.id});
  const deletion = {graph_id: created.graph_id, base_revision: 1, request_key: 'delete'};
  const receipt = tasks.execute(actor, 'delete', deletion);
  expect(tasks.execute(actor, 'delete', deletion)).toEqual(receipt);
  db.prepare('UPDATE nodes SET owner_id=? WHERE node_id=?').run(after.user.id, 'transferred');
  db.prepare('UPDATE agent_profiles SET owner_id=?,space_id=? WHERE agent_id=?').run(after.user.id, `personal:${after.user.id}`, 'transferred');
  db.prepare('UPDATE users SET owner_id=? WHERE username=?').run(after.user.id, 'agent:transferred');
  expect(() => tasks.execute(actor, 'delete', deletion)).toThrow('not accessible');
  expect(tasks.execute(actor, 'list', {}).items).toEqual([]);
});

it('acknowledges revoked company work without blocking the shared private journal or replaying dropped content', async () => {
  const { app, db, register } = await fixture();
  const owner = await register('mixed-owner');
  agent(db, 'mixed-private', owner.user.id, `personal:${owner.user.id}`);
  agent(db, 'mixed-company', owner.user.id, 'company:default');
  db.prepare("UPDATE agent_profiles SET node_id='mixed-private' WHERE agent_id='mixed-company'").run();
  db.prepare("UPDATE users SET membership_status='suspended' WHERE id=?").run(owner.user.id);
  const events = ['mixed-company', 'mixed-private'].map((root, i) => ({seq: i + 1, event_id: root, root_agent_id: root, session_id: root, type: 'session_registered', payload: {scope: 'global_main'}}));
  const batch = {journal_id: 'mixed', from_seq: 1, events};
  expect(app.im.gateway.work.append('mixed-private', batch).through_seq).toBe(2);
  expect(db.prepare('SELECT root_agent_id FROM agent_work_events').all()).toEqual([{root_agent_id: 'mixed-private'}]);
  expect(db.prepare("SELECT payload FROM agent_work_sessions WHERE root_agent_id='mixed-company'").get()).toEqual({payload: JSON.stringify({scope: 'global_main', parent_session_id: null})});
  db.prepare("UPDATE users SET membership_status='active' WHERE id=?").run(owner.user.id);
  expect(app.im.gateway.work.append('mixed-private', batch).through_seq).toBe(2);
  expect(db.prepare('SELECT root_agent_id FROM agent_work_events').all()).toEqual([{root_agent_id: 'mixed-private'}]);
  expect(() => app.im.gateway.work.append('mixed-private', {...batch, events: [{...events[0], root_agent_id: 'unknown'}]})).toThrow();
});

it('closes revoked company trajectory reads while the same node remains usable for personal work', async () => {
  const { app, db, register } = await fixture();
  const owner = await register('native-owner'), reader = await register('native-reader');
  db.prepare("UPDATE users SET membership_status='active' WHERE id IN (?,?)").run(owner.user.id, reader.user.id);
  db.prepare('UPDATE users SET is_company_admin=1 WHERE id=?').run(reader.user.id);
  agent(db, 'native-private', owner.user.id, `personal:${owner.user.id}`);
  agent(db, 'native-company', owner.user.id, 'company:default');
  db.prepare("UPDATE agent_profiles SET node_id='native-private' WHERE agent_id='native-company'").run();
  db.prepare("INSERT INTO node_binding_state(node_id,node_epoch,owner_id) VALUES('native-private',0,?)").run(owner.user.id);
  class Socket extends EventEmitter {
    readyState = 1; bufferedAmount = 0; frames: any[] = [];
    send(raw: string) { this.frames.push(JSON.parse(raw)); }
    close(code?: number) { this.readyState = 3; this.frames.push({ closed: code }); }
  }
  const device = { node_id: 'native-private', owner_id: owner.user.id, node_epoch: 0, socket: new Socket() };
  app.im.gateway.nodes.set(device.node_id, device as any);
  app.im.gateway.work.append(device.node_id, { journal_id: 'native-mixed', from_seq: 1, events:
    ['native-company', 'native-private'].map((root, i) => ({ seq: i + 1, event_id: root, root_agent_id: root, session_id: root, type: 'session_registered', payload: { scope: 'global_main' } })) });
  const open = (token: string, root: string) => {
    const browser = new Socket();
    const ticket = app.im.identity.issueTicket(app.im.identity.accessSession(token).sid);
    app.im.gateway.trajectory.browser(browser as any, ticket, root, root);
    return browser;
  };
  const pair = (browser: Socket) => {
    const prepare = device.socket.frames.filter(frame => frame.type === 'trajectory.prepare').at(-1);
    const node = new Socket();
    app.im.gateway.trajectory.node(node as any, prepare.payload.ticket);
    node.emit('message', Buffer.from(JSON.stringify({ type: 'ready', observerId: prepare.payload.scope.observerId })));
    expect(browser.frames.at(-1)).toMatchObject({ type: 'ready' });
    return node;
  };
  const company = open(reader.access_token, 'native-company'), companyNode = pair(company);
  app.im.identity.transition(reader.user.id, owner.user.id, 'suspend');
  app.im.gateway.trajectory.check();
  expect(app.im.gateway.valid(device as any)).toBe(true);
  expect(company.readyState).toBe(3);
  expect(companyNode.readyState).toBe(3);
  const denied = open(reader.access_token, 'native-company');
  expect(denied.frames).toContainEqual(expect.objectContaining({ type: 'failed' }));
  expect(denied.readyState).toBe(3);
  const freshOwner = await app.im.identity.login('native-owner', 'password-123');
  const personal = open(freshOwner.access_token, 'native-private'), personalNode = pair(personal);
  personal.emit('message', Buffer.from(JSON.stringify({ type: 'call', requestId: 'private-read', method: 'session/page', params: {} })));
  expect(personalNode.frames.at(-1)).toMatchObject({ requestId: 'private-read', method: 'session/page' });
  expect(personal.readyState).toBe(1);
});

it('resumes both spaces after a revoked mixed node is handed to an approved owner', async () => {
  const {app, db, register} = await fixture();
  const before = await register('handoff-old'), after = await register('handoff-new');
  agent(db, 'handoff-private', before.user.id, `personal:${before.user.id}`);
  agent(db, 'handoff-company', before.user.id, 'company:default');
  db.prepare("UPDATE agent_profiles SET node_id='handoff-private' WHERE agent_id='handoff-company'").run();
  db.prepare("UPDATE users SET membership_status='suspended' WHERE id=?").run(before.user.id);
  const registrations = ['handoff-company', 'handoff-private'].map((root, i) => ({seq:i+1,event_id:root,root_agent_id:root,session_id:root,type:'session_registered',payload:{scope:'global_main',title:'revoked private content'}}));
  expect(app.im.gateway.work.append('handoff-private', {journal_id:'handoff',from_seq:1,events:registrations}).through_seq).toBe(2);
  db.prepare("UPDATE users SET membership_status='active' WHERE id=?").run(after.user.id);
  db.prepare("UPDATE nodes SET owner_id=? WHERE node_id='handoff-private'").run(after.user.id);
  db.prepare("UPDATE agent_profiles SET owner_id=? WHERE node_id='handoff-private'").run(after.user.id);
  db.prepare("UPDATE agent_profiles SET space_id=? WHERE agent_id='handoff-private'").run(`personal:${after.user.id}`);
  const turns = registrations.map((e, i) => ({...e,seq:i+3,event_id:`turn-${e.event_id}`,turn_id:'new-turn',type:'turn_started',payload:{model:'m'}}));
  expect(app.im.gateway.work.append('handoff-private', {journal_id:'handoff',from_seq:3,events:turns}).through_seq).toBe(4);
  expect(db.prepare('SELECT root_agent_id FROM agent_work_events WHERE seq>=3 ORDER BY seq').all()).toEqual([{root_agent_id:'handoff-company'},{root_agent_id:'handoff-private'}]);
  expect(db.prepare("SELECT payload FROM agent_work_sessions WHERE root_agent_id='handoff-company'").get()?.payload).not.toContain('revoked private content');
});

it('lets both real Agent owners observe existing direct history and events without acquiring membership or write rights', async () => {
  const { app, db, register, request } = await fixture();
  const alice = await register('observer-alice'), bob = await register('observer-bob'), outsider = await register('observer-admin');
  db.prepare("UPDATE users SET membership_status='active',is_company_admin=1").run();
  agent(db, 'left', alice.user.id, 'company:default');
  agent(db, 'right', bob.user.id, 'company:default');
  agent(db, 'same', alice.user.id, 'company:default');
  agent(db, 'private-left', alice.user.id, `personal:${alice.user.id}`);
  agent(db, 'private-right', alice.user.id, `personal:${alice.user.id}`);
  const messaging = app.im.messaging;
  const cross = messaging.resolveTarget('left', 'agent:right');
  const same = messaging.resolveTarget('left', 'agent:same');
  const personal = messaging.resolveTarget('private-left', 'agent:private-right');
  // These histories predate observation and do not require another Agent message.
  db.prepare("UPDATE conversations SET owner_id='legacy-orphan' WHERE id=?").run(cross);
  for (const id of [cross, same, personal]) messaging.insertMessage(id, id === personal ? 'agent-private-left' : 'agent-left', 'agent', 'existing history', [], null);
  db.prepare('INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,?)').run(cross,alice.user.id);
  const upload = await app.inject({method:'POST',url:`/im/v1/uploads?conversation_id=${cross}&file_name=history.txt`,payload:'historical attachment',headers:{authorization:`Bearer ${alice.access_token}`,'content-type':'text/plain'}});
  expect(upload.statusCode).toBe(201);
  const media = upload.json().url;
  db.prepare('DELETE FROM conversation_participants WHERE conversation_id=? AND user_id=?').run(cross,alice.user.id);
  for (const pair of [alice, bob]) {
    expect((await request(pair.access_token, 'GET', media)).body).toBe('historical attachment');
    const detail = await request(pair.access_token, 'GET', `/im/v1/conversations/${cross}`);
    expect(detail.statusCode).toBe(200);
    expect(detail.json()).toMatchObject({is_observer: true, is_member: false, can_write: false, can_join: false, title: 'left ↔ right', participant_ids: ['agent-left', 'agent-right']});
    expect((await request(pair.access_token, 'GET', `/im/v1/conversations/${cross}/messages`)).json().items[0].message.content).toBe('existing history');
    const ids = (await request(pair.access_token, 'GET', '/im/v1/conversations')).json().items.map((c: any) => c.id);
    expect(ids.filter((id: string) => id === cross)).toHaveLength(1);
    expect((await request(pair.access_token, 'GET', '/im/v1/sync')).json().items.map((c: any) => c.id)).toContain(cross);
    for (const [method, path, payload] of [
      ['POST', `/im/v1/conversations/${cross}/messages`, {content: 'intrude', sender: {type: 'agent', id: 'left'}}],
      ['PATCH', `/im/v1/conversations/${cross}`, {title: 'changed', is_pinned: true}],
      ['POST', `/im/v1/conversations/${cross}/participants`, {participants: [{type: 'user', id: pair.user.id}]}],
      ['DELETE', `/im/v1/conversations/${cross}/participants/agent-left`, undefined],
      ['POST', `/im/v1/conversations/${cross}/join`, {}],
      ['DELETE', `/im/v1/conversations/${cross}`, undefined],
    ] as const) expect((await request(pair.access_token, method, path, payload)).statusCode, path).toBe(404);
    expect((await app.inject({method:'POST', url:`/im/v1/uploads?conversation_id=${cross}&file_name=note.txt`, payload:'blocked',headers:{authorization:`Bearer ${pair.access_token}`,'content-type':'text/plain'}})).statusCode).toBe(404);
  }
  expect((await request(outsider.access_token, 'GET', media)).statusCode).toBe(404);
  expect((await request(outsider.access_token, 'GET', `/im/v1/conversations/${cross}`)).statusCode).toBe(404);
  expect((await request(bob.access_token, 'GET', `/im/v1/conversations/${personal}`)).statusCode).toBe(404);
  expect((await request(alice.access_token, 'GET', '/im/v1/conversations')).json().items.map((c: any) => c.id).sort()).toEqual([cross, same, personal].sort());
  expect(db.prepare('SELECT COUNT(*) n FROM messages WHERE conversation_id=?').get(cross)).toEqual({n:1});
  expect(db.prepare('SELECT COUNT(*) n FROM relay_tasks').get()).toEqual({n:0});

  const streams = [alice, bob, outsider].map(pair => {
    const frames: any[] = [];
    const socket: any = {readyState:1, bufferedAmount:0, send: (raw: string) => frames.push(JSON.parse(raw)), close: () => {}};
    const browser = {socket, userId:pair.user.id, sessionId:app.im.identity.accessSession(pair.access_token).sid, ready:true, cursor:0};
    app.im.gateway.browsers.add(browser);
    return {frames, browser};
  });
  const first = messaging.event(cross, null, 'message.created', {content:'live collaboration'});
  expect(streams.map(s => s.frames.some(f => f.event_id === first.event_id))).toEqual([true,true,false]);
  for (const s of streams) { s.frames.length = 0; app.im.gateway.replay(s.browser, 0); }
  expect(streams.map(s => s.frames.some(f => f.event_id === first.event_id))).toEqual([true,true,false]);
  // Runtime availability is not ownership: preserve offline/stale known history.
  db.prepare("UPDATE agent_profiles SET is_stale=1 WHERE agent_id='right'").run();
  expect((await request(alice.access_token, 'GET', `/im/v1/conversations/${cross}`)).statusCode).toBe(200);
  db.prepare("UPDATE agent_profiles SET owner_id=? WHERE agent_id='left'").run(bob.user.id);
  const next = messaging.event(cross, null, 'message.created', {content:'after ownership change'});
  expect(streams[0].frames.some(f => f.event_id === next.event_id)).toBe(false);
  expect(streams[1].frames.some(f => f.event_id === next.event_id)).toBe(true);
  streams[0].frames.length = 0; app.im.gateway.replay(streams[0].browser, 0);
  expect(streams[0].frames.some(f => f.conversation_id === cross)).toBe(false);
  expect((await request(alice.access_token, 'GET', media)).statusCode).toBe(404);
  expect((await request(alice.access_token, 'GET', `/im/v1/conversations/${cross}`)).statusCode).toBe(404);
  db.prepare("UPDATE users SET membership_status='suspended' WHERE id=?").run(bob.user.id);
  expect((await request(bob.access_token, 'GET', `/im/v1/conversations/${cross}`)).statusCode).toBe(404);
  // Profiles must resolve in the conversation's space; a legacy third participant is not a two-Agent direct.
  db.prepare("UPDATE agent_profiles SET space_id=? WHERE agent_id='same'").run(`personal:${alice.user.id}`);
  expect((await request(alice.access_token, 'GET', `/im/v1/conversations/${same}`)).statusCode).toBe(404);
  db.prepare('INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,?)').run(personal, 'agent-right');
  expect((await request(alice.access_token, 'GET', `/im/v1/conversations/${personal}`)).statusCode).toBe(404);
});
