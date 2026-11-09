import { afterEach, expect, test, vi } from 'vitest';
import { createHash } from 'node:crypto';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { backup, DatabaseSync } from 'node:sqlite';
import { workDetailLimits, type WorkJournalEvent } from '@nano/product-contracts';
import { projectWorkDetail, WorkDetailWorker } from '@nano/product-contracts/work-detail-worker';
import { InboxStore } from '../../../packages/personal-assistant/src/inbox.js';
import { WorkSync } from '../../../packages/personal-assistant/src/work-sync.js';
import { createServer } from '../src/server.js';
import { browserSessionCookieName, digest } from '../src/identity.js';

const cleanups: (() => unknown | Promise<unknown>)[] = [];
afterEach(async () => { try { for (const cleanup of cleanups.splice(0).reverse()) await cleanup(); } finally { vi.restoreAllMocks(); } });
const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');
const originalPath = '/im/v1/agents/root/work/sessions/main/originals';
const token = 'isolated-node-key';
const secret = 'isolated-work-detail';
const publicUrl = 'http://127.0.0.1:8011';

async function fixture() {
  const dir = mkdtempSync(join(tmpdir(), 'work-detail-'));
  cleanups.push(() => rmSync(dir, {recursive: true, force: true}));
  const options = {dbPath: join(dir, 'center.db'), publicUrl, jwtSecret: secret};
  const start = async (dbPath = options.dbPath) => {
    const app = await createServer({...options, dbPath});
    const base = await app.listen({port: 0, host: '127.0.0.1'});
    let closed = false;
    const close = async () => { if (!closed) { closed = true; await app.close(); } };
    cleanups.push(close);
    return {app, base, close, db: app.im.db};
  };
  const center = await start(), {db} = center;
  const user = await center.app.im.identity.register('alice', 'password-for-test', 'Alice');
  const owner = user.user.id;
  db.prepare("UPDATE users SET membership_status='active' WHERE id=?").run(owner);
  db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('node',?,'Node','offline')").run(owner);
  db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch,runtime_token_hash) VALUES('node',?,1,?)").run(owner, digest(token));
  const profile = db.prepare(`INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,work_mode,created_at,updated_at,space_id)
    VALUES(?,?,'node',?,'global','2026-01-01','2026-01-01',?)`);
  profile.run('root', owner, 'Root', 'company:default');
  profile.run('private', owner, 'Private', `personal:${owner}`);
  const cookie = `${browserSessionCookieName(publicUrl)}=${center.app.im.identity.refreshBrowser(user.refresh_token).refresh_token}`;
  const inbox = new InboxStore(join(dir, 'inbox.db'));
  cleanups.push(() => inbox.close());
  const journal = `/im/v1/gateway/work-sync/journals/${inbox.journalId}`;
  const send = async (base: string, path: string, method: 'GET' | 'POST' | 'PUT' = 'GET', payload?: unknown) => {
    const response = await fetch(base + journal + path, {method, headers: {authorization: `Bearer ${token}`,
      ...(payload ? {'content-type': 'application/json'} : {})}, body: payload ? JSON.stringify(payload) : undefined});
    const body = await response.json();
    return {status: response.status, body};
  };
  return {center, dir, start, inbox, send, cookie, owner, user: user.access_token};
}

function wire(event: WorkJournalEvent) {
  const raw = Buffer.from(JSON.stringify(event));
  return {raw, manifest: {total_bytes: raw.length, sha256: sha(raw), projection: projectWorkDetail(event), allow_defer: true}};
}

function part(raw: Buffer, offset: number) {
  const bytes = raw.subarray(offset, offset + workDetailLimits.chunkBytes);
  return {data: bytes.toString('base64'), sha256: sha(bytes)};
}

test('a restarted center resumes persisted offsets, preserves two originals, advances later Work, and restores originals with a SQLite backup', async () => {
  const f = await fixture();
  const {inbox, center, send} = f;
  const identity = {root_agent_id: 'root', session_id: 'main'};
  inbox.append({...identity, event_id: 'registered', type: 'session_registered', payload: {scope: 'global_main'}});
  inbox.append({...identity, event_id: 'private-registered', root_agent_id: 'private', session_id: 'private-main', type: 'session_registered', payload: {scope: 'global_main'}});
  inbox.append({...identity, turn_id: 'turn', event_id: 'start', type: 'tool_start',
    payload: {call_id: 'tool', tool_name: 'write', arguments: {text: '示😀\n'.repeat(20 * 1024 * 1024 / 9)}}});
  inbox.append({...identity, turn_id: 'turn', event_id: 'end', type: 'tool_end',
    payload: {call_id: 'tool', presentation: {summary: 'Wrote report', detail: 'z'.repeat(17 * 1024 * 1024)}}});
  inbox.append({...identity, event_id: 'next-root', root_agent_id: 'private', session_id: 'private-main', type: 'recording_degraded', payload: {text: 'small'}});
  const expected = [3, 4].map(seq => {
    const event = inbox.journal(seq - 1, 1)[0]!;
    const {raw, manifest} = wire(event);
    return {seq, digest: manifest.sha256, bytes: raw.length};
  });
  const prepare = await send(center.base, '/events', 'POST', {from_seq: 1, events: inbox.journal(0, 2)});
  expect(prepare.status).toBe(200);
  {
    const {raw, manifest} = wire(inbox.journal(2, 1)[0]!);
    const begun = await send(center.base, '/large/3', 'POST', manifest);
    expect(begun.body).toMatchObject({through_seq: 2, detail: {state: 'uploading', offset: 0}});
    const bytes = part(raw, 0);
    const stored = await send(center.base, '/large/3/0', 'PUT', bytes);
    expect(stored.body).toMatchObject({through_seq: 2, detail: {offset: workDetailLimits.chunkBytes}});
    expect((await send(center.base, '/large/3/0', 'PUT', bytes)).body).toEqual(stored.body);
    expect((await send(center.base, '/large/3', 'POST', manifest)).body).toEqual(stored.body);
    expect((await send(center.base, '/events', 'POST', {from_seq: 3, events: [manifest.projection]})).status).toBe(409);
  }
  await center.close();
  const restarted = await f.start();
  const errors: unknown[] = [];
  const sync = new WorkSync({nodeId: 'node', inbox, url: restarted.base, credentials: () => token, onError: error => errors.push(error)});
  cleanups.push(() => sync.stop());
  sync.start();
  await expect.poll(() => inbox.throughSeq, {timeout: 20_000}).toBe(5);
  expect(errors).toEqual([]);
  expect(restarted.db.prepare('SELECT count(*) AS n FROM agent_work_events').get()).toEqual({n: 5});
  const auth = {authorization: `Bearer ${f.user}`};
  const list = await fetch(restarted.base + originalPath + '?turn_id=turn', {headers: auth});
  expect(list.status).toBe(200);
  const {items} = await list.json() as {items: {revision: number; type: string; state: string; total_bytes: number}[]};
  expect(items.map(item => [item.type, item.state, item.total_bytes])).toEqual(expected.map((item, index) =>
    [index === 0 ? 'tool_start' : 'tool_end', 'complete', item.bytes]));
  const restorePath = join(f.dir, 'restore.db');
  await backup(restarted.db, restorePath);
  const restored = await f.start(restorePath);
  for (const [index, item] of items.entries()) {
    const download = await fetch(restored.base + originalPath + '/' + item.revision, {headers: index === 0 ? {cookie: f.cookie} : auth});
    expect(download.status).toBe(200);
    expect(download.headers.get('content-disposition')).toContain('attachment');
    const digest = createHash('sha256');
    for await (const bytes of download.body!) digest.update(bytes);
    expect(digest.digest('hex')).toBe(expected[index]!.digest);
  }
  expect((await fetch(restored.base + originalPath + '/' + items[0]!.revision)).status).toBe(401);
  restored.db.prepare('UPDATE auth_sessions SET revoked=1 WHERE user_id=?').run(f.owner);
  expect((await fetch(restored.base + originalPath + '/' + items[0]!.revision, {headers: {cookie: f.cookie}})).status).toBe(401);
  expect((await fetch(restored.base + originalPath + '?turn_id=turn', {headers: auth})).status).toBe(401);
}, 30_000);

test('a beyond-limit projection advances without bytes, and an old writer’s deletion state removes current staging', async () => {
  const {center, send, owner} = await fixture();
  const identity = {root_agent_id: 'root', session_id: 'main'};
  const register: WorkJournalEvent = {...identity, seq: 1, event_id: 'register', type: 'session_registered', payload: {scope: 'global_main'}};
  const local: WorkJournalEvent = {...identity, seq: 2, event_id: 'only-local', type: 'recording_degraded', payload: {text: 'Local'}};
  expect((await send(center.base, '/events', 'POST', {from_seq: 1, events: [register]})).status).toBe(200);
  const tooLarge = await send(center.base, '/large/2', 'POST', {
    total_bytes: workDetailLimits.maxBytes + 1, sha256: null, allow_defer: true, projection: projectWorkDetail(local),
  });
  expect(tooLarge.body).toMatchObject({through_seq: 2, detail: {state: 'local', offset: 0}});
  const pending: WorkJournalEvent = {...local, seq: 3, event_id: 'interrupted'};
  const bytes = Buffer.alloc(workDetailLimits.chunkBytes, 0x30);
  expect((await send(center.base, '/large/3', 'POST', {
    total_bytes: 20 * 1024 * 1024, sha256: 'a'.repeat(64), allow_defer: true, projection: projectWorkDetail(pending),
  })).body).toMatchObject({through_seq: 2, detail: {state: 'uploading'}});
  expect((await send(center.base, '/large/3/0', 'PUT', part(bytes, 0))).status).toBe(200);
  const oldWriter = new DatabaseSync(center.app.im.dbPath);
  try {
    oldWriter.exec('PRAGMA foreign_keys=ON');
    oldWriter.prepare(`INSERT INTO agent_deletions(agent_id,operation_id,request_id,owner_id,node_id,node_epoch,revision,profile_version,state)
      VALUES('root','op','request',?,'node',1,1,1,'deleting')`).run(owner);
    oldWriter.exec("UPDATE agent_deletions SET state='deleted' WHERE agent_id='root'");
    expect(oldWriter.prepare('SELECT count(*) n FROM work_detail_uploads').get()).toEqual({n: 0});
    expect(oldWriter.prepare('SELECT count(*) n FROM work_detail_parts').get()).toEqual({n: 0});
  } finally { oldWriter.close(); }
});

test('quota defers one original across Gateway restart and completes the same revision after capacity returns', async () => {
  const f = await fixture();
  const {center, inbox, owner} = f;
  const root = {root_agent_id: 'root', session_id: 'main'};
  inbox.append({...root, event_id: 'registration', type: 'session_registered', payload: {scope: 'global_main'}});
  inbox.append({...root, event_id: 'deferred', type: 'recording_degraded', payload: {text: 'a'.repeat(17 * 1024 * 1024)}});
  inbox.append({...root, event_id: 'after', type: 'recording_degraded', payload: {text: 'later normal record'}});
  center.db.prepare(`INSERT INTO work_detail_uploads
    (owner_id,node_id,node_epoch,journal_id,seq,event_id,root_agent_id,session_id,total_bytes,sha256,projection_json,updated_at,state)
    VALUES(?,'node',1,'older',1,'reservation','root','main',?,'hash','hash',?,'uploading')`).run(owner, workDetailLimits.maxBytes, Date.now());
  const errors: unknown[] = [];
  const start = (source: InboxStore) => {
    const sync = new WorkSync({nodeId: 'node', inbox: source, url: center.base, credentials: () => token, onError: error => errors.push(error)});
    cleanups.push(() => sync.stop());
    sync.start();
    return sync;
  };
  const first = start(inbox);
  await expect.poll(() => inbox.throughSeq, {timeout: 10_000}).toBe(3);
  const manifest = () => center.db.prepare("SELECT revision,state FROM work_detail_uploads WHERE event_id='deferred'").get();
  const before = manifest();
  expect(before).toMatchObject({state: 'pending'});
  expect(inbox.pendingWorkDetail(0, 3)).toMatchObject({seq: 2, event_id: 'deferred'});
  await first.stop();
  center.db.prepare("DELETE FROM work_detail_uploads WHERE event_id='reservation'").run();
  const reopened = new InboxStore(inbox.path);
  cleanups.push(() => reopened.close());
  const workerCalls = vi.spyOn(WorkDetailWorker.prototype, 'run');
  const transport = globalThis.fetch;
  const offsets: number[] = [];
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
    const response = await transport(url, init);
    const offset = /\/large\/2\/(\d+)$/.exec(String(url))?.[1];
    if (offset !== undefined && init?.method === 'PUT') {
      offsets.push(Number(offset));
      if (offsets.length === 1) {
        reopened.append({...root, event_id: 'preempt', type: 'recording_degraded', payload: {text: 'ordinary Work during deferred upload'}});
        resumed.signal();
      }
    }
    return response;
  });
  const resumed = start(reopened);
  await expect.poll(() => reopened.throughSeq, {timeout: 10_000}).toBe(4);
  expect(offsets).toEqual([0]);
  expect(existsSync(`${inbox.path}.work-detail.tmp`)).toBe(true);
  await expect.poll(manifest, {timeout: 15_000}).toEqual({...before, state: 'complete'});
  await expect.poll(() => reopened.pendingWorkDetail(0, 4), {timeout: 15_000}).toBeUndefined();
  expect(offsets.slice(0, 2)).toEqual([0, workDetailLimits.chunkBytes]);
  expect(workerCalls.mock.calls.filter(([job]) => job.kind === 'prepare')).toHaveLength(1);
  expect(existsSync(`${inbox.path}.work-detail.tmp`)).toBe(false);
  expect(center.db.prepare('SELECT count(*) AS n FROM agent_work_events').get()).toEqual({n: 4});
  expect(center.db.prepare('SELECT through_seq FROM agent_work_journals').get()).toEqual({through_seq: 4});
  expect(errors).toEqual([]);
}, 35_000);

test('a valid full hash cannot attach private-root bytes to a company Work event', async () => {
  const {center, send} = await fixture();
  const root = {root_agent_id: 'root', session_id: 'main'};
  const registration = {...root, seq: 1, event_id: 'registered', type: 'session_registered', payload: {scope: 'global_main'}};
  expect((await send(center.base, '/events', 'POST', {from_seq: 1, events: [registration]})).status).toBe(200);
  const privateEvent: WorkJournalEvent = {...root, seq: 2, event_id: 'private-event', root_agent_id: 'private', session_id: 'private-main',
    type: 'recording_degraded', payload: {text: 's'.repeat(17 * 1024 * 1024)}};
  const {raw, manifest} = wire(privateEvent);
  manifest.projection = {...manifest.projection, ...root};
  expect((await send(center.base, '/large/2', 'POST', manifest)).status).toBe(200);
  for (let offset = 0; offset < raw.length; offset += workDetailLimits.chunkBytes) {
    const {status} = await send(center.base, `/large/2/${offset}`, 'PUT', part(raw, offset));
    expect(status).toBe(200);
  }
  await expect.poll(async () => (await send(center.base, '/large/2', 'POST', manifest)).body,
    {timeout: 10_000}).toMatchObject({through_seq: 1, detail: {state: 'rejected'}});
  expect(center.db.prepare('SELECT count(*) AS n FROM work_detail_parts').get()).toEqual({n: 0});
  expect(center.db.prepare('SELECT count(*) AS n FROM agent_work_events').get()).toEqual({n: 1});
}, 20_000);

test('verification from a revoked staging attempt cannot certify different bytes on the same deferred manifest', async () => {
  const {center, send, owner, user} = await fixture();
  const root = {root_agent_id: 'root', session_id: 'main'};
  const registration = {...root, seq: 1, event_id: 'registered', type: 'session_registered', payload: {scope: 'global_main'}};
  expect((await send(center.base, '/events', 'POST', {from_seq: 1, events: [registration]})).status).toBe(200);
  const event: WorkJournalEvent = {...root, seq: 2, event_id: 'replace', type: 'recording_degraded', payload: {text: 'v'.repeat(17 * 1024 * 1024)}};
  const {raw, manifest} = wire(event);
  center.db.prepare(`INSERT INTO work_detail_uploads
    (owner_id,node_id,node_epoch,journal_id,seq,event_id,root_agent_id,session_id,total_bytes,sha256,projection_json,updated_at,state)
    VALUES(?,'node',1,'older',1,'reservation','root','main',?,'hash','{}',?,'uploading')`).run(owner, workDetailLimits.maxBytes, Date.now());
  expect((await send(center.base, '/large/2', 'POST', manifest)).body).toMatchObject({through_seq: 2, detail: {state: 'pending'}});
  center.db.prepare("DELETE FROM work_detail_uploads WHERE event_id='reservation'").run();
  const resume = {resume: true, event_id: event.event_id, sha256: manifest.sha256};
  const state = () => center.db.prepare("SELECT id,revision,generation,state FROM work_detail_uploads WHERE event_id='replace'").get();
  const original = state();
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  cleanups.push(release);
  let verified = false;
  const verify = WorkDetailWorker.prototype.run;
  vi.spyOn(WorkDetailWorker.prototype, 'run').mockImplementation(async function (this: WorkDetailWorker, job) {
    const result = await verify.call(this, job);
    if (!verified && job.kind === 'verify') {
      verified = true;
      await gate;
    }
    return result;
  });
  const upload = async () => {
    expect((await send(center.base, '/large/2', 'POST', resume)).body).toMatchObject({detail: {state: 'uploading', offset: 0}});
    for (let offset = 0; offset < raw.length; offset += workDetailLimits.chunkBytes)
      expect((await send(center.base, `/large/2/${offset}`, 'PUT', part(raw, offset))).status).toBe(200);
  };
  await upload();
  await expect.poll(() => verified).toBe(true);
  const eligibility = center.db.prepare('UPDATE users SET membership_status=? WHERE id=?');
  eligibility.run('pending', owner);
  const reset = await send(center.base, '/large/2/0', 'PUT', part(raw, 0));
  expect(reset.body).toMatchObject({detail: {state: 'pending', offset: 0}});
  eligibility.run('active', owner);
  raw[workDetailLimits.chunkBytes] ^= 1;
  await upload();
  expect(state()).toEqual({...original, generation: 2, state: 'verifying'});
  release();
  await expect.poll(state).toEqual({...original, generation: 2, state: 'rejected'});
  expect(center.db.prepare('SELECT count(*) AS n FROM work_detail_parts').get()).toEqual({n: 0});
  expect(center.db.prepare('SELECT through_seq FROM agent_work_journals').get()).toEqual({through_seq: 2});
  const list = await fetch(center.base + originalPath, {headers: {authorization: `Bearer ${user}`}});
  expect(await list.json()).toMatchObject({items: [{event_id: 'replace', state: 'local'}]});
}, 25_000);

test('records over the JSON structure budget remain local while later Work advances', async () => {
  const {center, inbox, user, send} = await fixture();
  const root = {root_agent_id: 'root', session_id: 'main'};
  inbox.append({...root, event_id: 'registered', type: 'session_registered', payload: {scope: 'global_main'}});
  const argumentsValue = {content: 'x'.repeat(17 * 1024 * 1024), rows: Array(110_000).fill({n: 1})};
  inbox.append({...root, turn_id: 'turn', event_id: 'complex', type: 'tool_start',
    payload: {call_id: 'tool', tool_name: 'writer', arguments: argumentsValue}});
  inbox.append({...root, turn_id: 'turn', event_id: 'normal', type: 'tool_end', payload: {call_id: 'tool'}});
  const errors: unknown[] = [];
  const sync = new WorkSync({nodeId: 'node', inbox, url: center.base, credentials: () => token, onError: error => errors.push(error)});
  cleanups.push(() => sync.stop());
  sync.start();
  await expect.poll(() => inbox.throughSeq, {timeout: 8_000}).toBe(3);
  expect(errors).toEqual([]);
  expect((inbox.journal(1, 1)[0]!.payload.arguments as {rows: unknown[]}).rows).toHaveLength(110_000);
  const auth = {authorization: `Bearer ${user}`};
  const before = await fetch(center.base + originalPath + '?turn_id=turn', {headers: auth});
  expect(await before.json()).toMatchObject({items: [{event_id: 'complex', state: 'local'}]});
  const items = await fetch(center.base + '/im/v1/agents/root/work/sessions/main/turns/turn/items', {headers: auth});
  expect(await items.json()).toMatchObject({items: [{item_id: 'tool:tool', payload: {large_detail_preview: true, status: 'completed'}}]});
  await sync.stop();

  // A sender that still uploads these bytes reaches the same budget at verification.
  const {raw, manifest} = wire({...root, seq: 4, turn_id: 'turn', event_id: 'complex-uploaded', type: 'tool_end',
    payload: {call_id: 'tool', arguments: argumentsValue}});
  expect((await send(center.base, '/large/4', 'POST', manifest)).body).toMatchObject({detail: {state: 'uploading'}});
  for (let offset = 0; offset < raw.length; offset += workDetailLimits.chunkBytes)
    expect((await send(center.base, `/large/4/${offset}`, 'PUT', part(raw, offset))).status).toBe(200);
  await expect.poll(async () => (await send(center.base, '/large/4', 'POST', manifest)).body)
    .toMatchObject({through_seq: 4, detail: {state: 'local', offset: 0}});
  expect(center.db.prepare('SELECT count(*) AS n FROM work_detail_parts').get()).toEqual({n: 0});
}, 25_000);
