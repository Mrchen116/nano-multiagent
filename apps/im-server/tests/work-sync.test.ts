import { afterEach, expect, test } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { request as httpRequest } from 'node:http';
import { createServer } from '../src/server.js';
import { digest } from '../src/identity.js';

const cleanups: (() => unknown | Promise<unknown>)[] = [];
afterEach(async () => { for (const cleanup of cleanups.splice(0).reverse()) await cleanup(); });
const prefix = '/im/v1/gateway/work-sync/journals/journal';
const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');

async function fixture() {
  const dir = mkdtempSync(join(tmpdir(), 'work-sync-'));
  cleanups.push(() => rmSync(dir, { recursive: true, force: true }));
  const options = { dbPath: join(dir, 'im.db'), publicUrl: 'http://127.0.0.1', jwtSecret: 'isolated-work-sync' };
  const app = await createServer(options);
  cleanups.push(() => app.close());
  const db = app.im.db;
  db.prepare("INSERT INTO users(id,username,display_name,owner_id,membership_status,created_at) VALUES('alice','alice','Alice','alice','active','2026-01-01')").run();
  db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('node','alice','Node','offline')").run();
  db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch,runtime_token_hash) VALUES('node','alice',1,?)").run(digest('runtime-secret'));
  db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,work_mode,created_at,updated_at) VALUES('root','alice','node','Root','global','2026-01-01','2026-01-01')").run();
  const request = (method: 'GET' | 'POST' | 'PUT', url = prefix, payload?: object, token = 'runtime-secret') => app.inject({ method, url, payload, headers: { authorization: `Bearer ${token}` } });
  return { app, db, request, options };
}

const event = (seq: number, payload: object = { scope: 'global_main' }) => ({
  seq, event_id: `event-${seq}`, root_agent_id: 'root', session_id: 'main',
  type: seq === 1 ? 'session_registered' : 'recording_degraded', payload,
});
function parts(value: object) {
  const raw = Buffer.from(JSON.stringify(value));
  return Array.from({ length: Math.ceil(raw.length / 16384) }, (_, part) => {
    const bytes = raw.subarray(part * 16384, (part + 1) * 16384);
    return { event_id: (value as any).event_id, sha256: sha(raw), total_bytes: raw.length,
      total_parts: Math.ceil(raw.length / 16384), part_sha256: sha(bytes), data: bytes.toString('base64') };
  });
}

test('an offline machine reads its durable journal with runtime credentials, without a live WebSocket', async () => {
  const f = await fixture();
  const cursor = await f.request('GET');
  expect(cursor.statusCode, cursor.body).toBe(200);
  expect(cursor.json()).toMatchObject({ through_seq: 0, expected_seq: 1 });
  expect((await f.request('GET', prefix, undefined, 'wrong-token')).statusCode).toBe(401);
  expect((await f.request('GET', '/im/v1/conversations')).statusCode).toBe(401);
});
test('advancing a cursor never rewrites previously committed hash receipts',async()=>{
 const f=await fixture();await f.request('POST',`${prefix}/events`,{from_seq:1,events:[event(1)]});
 const original=f.db.prepare('SELECT * FROM work_sync_uploads LIMIT 1').get() as any;
 const insert=f.db.prepare('INSERT INTO work_sync_uploads VALUES(?,?,?,?,?,?,?,?,?,?,?,1)');
 f.db.exec('BEGIN');for(let i=0;i<1000;i++)insert.run(`retained-${i}`,original.owner_id,original.node_id,original.node_epoch,original.journal_id,1,`retained-${i}`,original.sha256,original.total_bytes,original.total_parts,original.updated_at);f.db.exec('COMMIT');
 const changes=()=>Number((f.db.prepare('SELECT total_changes() n').get() as {n:number}).n),before=changes();
 f.db.prepare('UPDATE agent_work_journals SET through_seq=through_seq WHERE node_id=? AND journal_id=?').run('node','journal');
 expect(changes()-before).toBe(1);
 expect(f.db.prepare('SELECT count(*) n FROM work_sync_uploads WHERE committed=1').get()).toMatchObject({n:1001});
});

test('small batches preserve event identity, sequence, body bounds and authenticated node scope', async () => {
  const f = await fixture();
  const first = event(1);
  const post = (payload: object) => f.request('POST', `${prefix}/events`, payload);
  expect((await post({ from_seq: 2, events: [event(2)] })).json()).toMatchObject({ through_seq: 0, expected_seq: 1 });
  expect((await post({ from_seq: 1, events: [first], node_id: 'outsider' })).statusCode).toBe(400);
  expect((await post({ from_seq: 1, events: [{ ...first, root_agent_id: 'outsider' }] })).statusCode).toBe(403);
  expect((await post({ from_seq: 1, events: [first] })).json()).toMatchObject({ through_seq: 1 });
  expect((await post({ from_seq: 1, events: [first] })).json()).toMatchObject({ through_seq: 1 });
  expect((await post({ from_seq: 1, events: [{ ...first, type: 'changed' }] })).statusCode).toBe(409);
  expect((await post({ from_seq: 1, events: [{ ...first, payload: { scope: 'global_main', changed: true } }] })).statusCode).toBe(409);
  expect((await post({ from_seq: 2, events: Array.from({ length: 101 }, (_, i) => event(i + 2)) })).statusCode).toBe(400);
  expect((await post({ from_seq: 2, events: [event(2, { text: 'x'.repeat(64 * 1024) })] })).statusCode).toBe(413);
  expect((await f.request('GET')).json()).toMatchObject({ through_seq: 1 });
  expect(f.db.prepare('SELECT count(*) count FROM agent_work_events').get()).toMatchObject({ count: 1 });
});
test('a chunked child tool keeps its complete arguments, projection and parent ownership',async()=>{
 const f=await fixture();
 const linked={...event(2),type:'session_linked',payload:{parent_session_id:'main',child_session_id:'child'}};
 expect((await f.request('POST',`${prefix}/events`,{from_seq:1,events:[event(1),linked]})).json().through_seq).toBe(2);
 const full={...event(3),session_id:'child',turn_id:'1',type:'tool_end',payload:{call_id:'child-write',tool_name:'write',arguments:{file_path:'child.txt',content:'x'.repeat(106*1024)},presentation:{summary:'child done',detail:{content:'complete child result'}}}};
 const chunks=parts(full);
 for(let i=0;i<chunks.length;i++)expect((await f.request('PUT',`${prefix}/events/3/parts/${i}`,chunks[i])).statusCode).toBe(200);
 expect((await f.request('GET')).json().through_seq).toBe(3);
 expect(f.db.prepare("SELECT root_agent_id,node_id,scope,parent_session_id FROM agent_work_sessions WHERE session_id='child'").get()).toEqual({root_agent_id:'root',node_id:'node',scope:'subagent',parent_session_id:'main'});
 const stored=f.db.prepare('SELECT payload FROM agent_work_events WHERE seq=3').get() as {payload:string};expect(JSON.parse(stored.payload)).toEqual(full.payload);
 const projected=JSON.parse((f.db.prepare("SELECT payload FROM agent_work_items WHERE session_id='child' AND item_id='tool:child-write'").get() as {payload:string}).payload);
 expect(projected.input).toEqual(full.payload.arguments);expect(projected.detail).toEqual(full.payload.presentation.detail);
});

test('parts survive restart, reject corruption and commit a complete 106 KiB event only once', async () => {
  const f = await fixture();
  await f.request('POST', `${prefix}/events`, { from_seq: 1, events: [event(1)] });
  const full = event(2, { text: '中'.repeat(Math.ceil(106 * 1024 / 3)) }), chunks = parts(full);
  const put = (index: number, payload = chunks[index]!) => f.request('PUT', `${prefix}/events/2/parts/${index}`, payload);
  expect((await put(0)).json()).toMatchObject({ through_seq: 1, pending_event: { received_parts: [0] } });
  expect((await put(0)).json().pending_event.received_parts).toEqual([0]);
  expect((await put(1, { ...chunks[1]!, part_sha256: '0'.repeat(64) })).statusCode).toBe(400);
  expect((await put(1, { ...chunks[1]!, sha256: '0'.repeat(64) })).statusCode).toBe(409);
  expect((await f.request('GET')).json()).toMatchObject({ through_seq: 1, pending_event: { received_parts: [0] } });
  expect(f.db.prepare('SELECT 1 FROM agent_work_events WHERE seq=2').get()).toBeUndefined();
  await f.app.close();
  const reopened = await createServer(f.options); cleanups.push(() => reopened.close());
  const request = (method: 'GET' | 'PUT', url = prefix, payload?: object) => reopened.inject({ method, url, payload, headers: { authorization: 'Bearer runtime-secret' } });
  expect((await request('GET')).json()).toMatchObject({ through_seq: 1, pending_event: { received_parts: [0] } });
  for (let index = chunks.length - 1; index > 0; index--) {
    const response = await request('PUT', `${prefix}/events/2/parts/${index}`, chunks[index]);
    expect(response.statusCode, response.body).toBe(200);
    if (index > 1) expect(response.json().through_seq).toBe(1);
  }
  expect((await request('GET')).json()).toMatchObject({ through_seq: 2 });
  const stored = reopened.im.db.prepare('SELECT payload FROM agent_work_events WHERE seq=2').get() as { payload: string };
  expect(JSON.parse(stored.payload)).toEqual(full.payload);
  expect((await request('PUT', `${prefix}/events/2/parts/0`, chunks[0])).json().through_seq).toBe(2);
  expect((await request('PUT', `${prefix}/events/2/parts/0`, { ...chunks[0]!, sha256: 'f'.repeat(64) })).statusCode).toBe(409);
  expect(reopened.im.db.prepare('SELECT count(*) count FROM agent_work_events WHERE seq=2').get()).toMatchObject({ count: 1 });
});

test('device revocation and expired partials discard unconfirmed bytes without advancing Work', async () => {
  const f = await fixture(), chunks = parts(event(1, { scope: 'global_main', text: 'x'.repeat(50000) }));
  const path = `${prefix}/events/1/parts/0`;
  expect((await f.request('PUT', path, chunks[0])).statusCode).toBe(200);
  f.db.prepare('UPDATE work_sync_uploads SET updated_at=0 WHERE committed=0').run();
  expect((await f.request('GET')).json()).toEqual({ through_seq: 0, expected_seq: 1 });
  expect((await f.request('PUT', path, chunks[0])).statusCode).toBe(200);
  f.db.prepare('UPDATE node_binding_state SET node_epoch=2,runtime_token_hash=? WHERE node_id=?').run(digest('new-secret'), 'node');
  expect((await f.request('PUT', `${prefix}/events/1/parts/1`, chunks[1])).statusCode).toBe(401);
  expect((await f.request('GET', prefix, undefined, 'new-secret')).json()).toEqual({ through_seq: 0, expected_seq: 1 });
  expect(f.db.prepare('SELECT count(*) count FROM agent_work_events').get()).toMatchObject({ count: 0 });
});

test('complete parts still require the full byte hash, envelope identity and current session authority', async () => {
  const f = await fixture(), full = event(1, { scope: 'global_main', text: 'x'.repeat(40000) });
  let chunks = parts(full).map(chunk => ({ ...chunk, sha256: '0'.repeat(64) }));
  for (let index = 0; index < chunks.length; index++) {
    const result = await f.request('PUT', `${prefix}/events/1/parts/${index}`, chunks[index]);
    expect(result.statusCode).toBe(index === chunks.length - 1 ? 400 : 200);
  }
  expect((await f.request('GET')).json().through_seq).toBe(0);
  // An expired rejected upload can be retransmitted from the retained source.
  f.db.prepare('UPDATE work_sync_uploads SET updated_at=0').run(); await f.request('GET');
  chunks = parts({ ...full, root_agent_id: 'another-node-root' });
  for (let index = 0; index < chunks.length; index++) {
    const result = await f.request('PUT', `${prefix}/events/1/parts/${index}`, chunks[index]);
    expect(result.statusCode).toBe(index === chunks.length - 1 ? 403 : 200);
  }
  expect((await f.request('GET')).json().through_seq).toBe(0);
  expect(f.db.prepare('SELECT count(*) count FROM agent_work_sessions').get()).toMatchObject({ count: 0 });
});

test('the event and staging quotas reject excess bytes with no false cursor progress', async () => {
  const f = await fixture(), chunk = parts(event(1, { scope: 'global_main', text: 'x'.repeat(40000) }))[0]!;
  expect((await f.request('PUT', `${prefix}/events/1/parts/0`, { ...chunk, total_bytes: 16 * 1024 * 1024 + 1 })).json()).toMatchObject({ detail: 'event_too_large' });
  for (let index = 0; index < 16; index++) {
    const id = `reserved-${index}`;
    f.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES(?,'alice',?,'offline')").run(id, id);
    f.db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch,runtime_token_hash) VALUES(?,'alice',1,'reserved')").run(id);
    f.db.prepare("INSERT INTO work_sync_uploads VALUES(?,'alice',?,1,'reserved',1,'reserved',?,16777216,1024,?,0)").run(id, id, 'a'.repeat(64), Date.now());
  }
  const response = await f.request('PUT', `${prefix}/events/1/parts/0`, chunk);
  expect(response.statusCode).toBe(429); expect(response.headers['retry-after']).toBe('1');
  expect((await f.request('GET')).json().through_seq).toBe(0);
});

test('intake permits enforce one request per node and eight across the center', async () => {
  const f = await fixture();
  const url = await f.app.listen({ port: 0, host: '127.0.0.1' });
  const held: ReturnType<typeof httpRequest>[] = [];
  const hold = (token: string) => {
    const request = httpRequest(`${url}${prefix}/events/1/parts/0`, { method: 'PUT', headers: {
      authorization: `Bearer ${token}`, 'content-type': 'application/json', 'content-length': '1024',
    } });
    request.on('error', () => {}); request.write('{'); held.push(request);
  };
  cleanups.push(() => { for (const request of held) request.destroy(); });
  hold('runtime-secret');
  try {
    await expect.poll(async () => (await f.request('GET')).statusCode).toBe(429);
    for (let index = 0; index < 8; index++) {
      const id = `permit-${index}`, token = `secret-${index}`;
      f.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES(?,'alice',?,'offline')").run(id, id);
      f.db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch,runtime_token_hash) VALUES(?,'alice',1,?)").run(id, digest(token));
      if (index < 7) {
        hold(token);
        await expect.poll(async () => (await f.request('GET', prefix, undefined, token)).statusCode).toBe(429);
      }
    }
    expect((await f.request('GET', prefix, undefined, 'secret-7')).statusCode).toBe(429);
  } finally { for (const request of held) request.destroy(); }
  await expect.poll(async () => (await f.request('GET')).statusCode).toBe(200);
});


test('record completeness requires a current connection declaration and both processing and upload completion', async () => {
  const f=await fixture();
  const connection={node_id:'node',owner_id:'alice',node_epoch:1,token:'runtime-secret',lastSeen:Date.now(),socket:{readyState:1,send(){},close(){}}} as any;
  f.app.im.gateway.nodes.set('node',connection);
  const view=()=>f.app.im.gateway.work.view('root').record_sync_state;
  const report=(highest:number,pending:boolean)=>f.app.inject({method:'GET',url:prefix,headers:{authorization:'Bearer runtime-secret','x-work-produced-seq':String(highest),'x-work-processing-pending':String(pending)}});
  expect(view()).toBe('unknown');
  expect((await report(1,true)).statusCode).toBe(200);expect(view()).toBe('catching_up');
  await f.request('POST',`${prefix}/events`,{from_seq:1,events:[event(1)]});
  expect(view()).toBe('catching_up');
  await report(1,false);expect(view()).toBe('current');
  await report(2,false);expect(view()).toBe('catching_up');
  await f.request('POST',`${prefix}/events`,{from_seq:2,events:[event(2)]});expect(view()).toBe('current');
  f.app.im.gateway.nodes.set('node',{...connection});expect(view()).toBe('unknown');
  await report(2,false);expect(view()).toBe('current');
  f.app.im.gateway.nodes.delete('node');expect(view()).toBe('unknown');
  await report(2,false);expect(view()).toBe('unknown');
  await f.app.close();
  const reopened=await createServer(f.options);cleanups.push(()=>reopened.close());
  reopened.im.gateway.nodes.set('node',{...connection});
  expect(reopened.im.gateway.work.view('root').record_sync_state).toBe('unknown');
});


test('a declaration received before socket replacement cannot mark the replacement current', async () => {
  const f=await fixture();
  const connection={node_id:'node',owner_id:'alice',node_epoch:1,token:'runtime-secret',lastSeen:Date.now(),socket:{readyState:1,send(){},close(){}}} as any;
  f.app.im.gateway.nodes.set('node',connection);
  const append=f.app.im.gateway.work.append.bind(f.app.im.gateway.work);
  f.app.im.gateway.work.append=(...args)=>{
    const result=append(...args);f.app.im.gateway.nodes.set('node',{...connection});return result;
  };
  const result=await f.app.inject({method:'POST',url:`${prefix}/events`,payload:{from_seq:1,events:[event(1)]},headers:{authorization:'Bearer runtime-secret','x-work-produced-seq':'1','x-work-processing-pending':'false'}});
  expect(result.statusCode).toBe(200);
  expect(f.app.im.gateway.work.view('root').record_sync_state).toBe('unknown');
});

test.each([
  ['tool_end', {call_id: 'tool', presentation: {summary: 42}}],
  ['permission_request', {request_id: 'approval', options: [null]}],
  ['permission_request', {request_id: 'approval', permission_request: {options: 'invalid'}}],
])('malformed %s payloads cannot commit a batch or a completely uploaded part set', async (type, payload) => {
  const f = await fixture();
  const invalid = {...event(2), turn_id: '1', type, payload};
  const rejected = await f.request('POST', `${prefix}/events`, {from_seq: 1, events: [event(1), invalid]});
  expect(rejected.statusCode, rejected.body).toBe(400);
  expect((await f.request('GET')).json().through_seq).toBe(0);
  expect(f.db.prepare('SELECT count(*) n FROM agent_work_sessions').get()).toMatchObject({n: 0});
  await f.request('POST', `${prefix}/events`, {from_seq: 1, events: [event(1)]});
  const chunks = parts(invalid);
  for (let index = 0; index < chunks.length; index++) {
    const result = await f.request('PUT', `${prefix}/events/2/parts/${index}`, chunks[index]);
    expect(result.statusCode, result.body).toBe(index === chunks.length - 1 ? 400 : 200);
  }
  expect((await f.request('GET')).json().through_seq).toBe(1);
  expect(f.db.prepare('SELECT count(*) n FROM agent_work_events').get()).toMatchObject({n: 1});
});

test('legacy aliases, omitted statistics and opaque extension payloads keep original journal bytes', async () => {
  const f = await fixture();
  const extension = {z: '中文😀\n"', nested: [null, {dynamic: true}], arbitrary: {x: [1, 2]}};
  const events = [event(1),
    {...event(2), turn_id: '1', type: 'turn_start', payload: {model: null, started_at: null}},
    {...event(3), turn_id: '1', type: 'plugin.custom', payload: extension},
    {...event(4), turn_id: '1', type: 'run_completed', payload: {usage: null, elapsed_ms: null}},
  ];
  const result = await f.request('POST', `${prefix}/events`, {from_seq: 1, events});
  expect(result.statusCode, result.body).toBe(200);
  expect(result.json().through_seq).toBe(4);
  for (const e of events) expect(f.db.prepare('SELECT payload FROM agent_work_events WHERE seq=?').get(e.seq)).toMatchObject({payload: JSON.stringify(e.payload)});
  const view = f.app.im.gateway.work.turns('root', 'main');
  expect(view.turns[0]).toMatchObject({status: 'completed', usage: null});
  expect(view.turns[0]!.items.find(item => item.kind === 'plugin.custom')!.payload).toMatchObject(extension);
  expect((await f.request('POST', `${prefix}/events`, {from_seq: 1, events})).json().through_seq).toBe(4);
  expect(f.db.prepare('SELECT count(*) n FROM agent_work_events').get()).toMatchObject({n: 4});
});
