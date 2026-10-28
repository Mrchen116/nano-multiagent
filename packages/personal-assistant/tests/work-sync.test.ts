import { afterEach, expect, test } from 'vitest';
import { createServer, type ServerResponse } from 'node:http';
import { createHash } from 'node:crypto';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { InboxStore } from '../src/inbox.js';
import type { WorkDraft } from '@nano/product-contracts';
import { WorkSync } from '../src/work-sync.js';

interface Call { method: string; path: string; body: any; bytes: number; authorization?: string; produced?: string; processing?: string }
const cleanups: (() => unknown | Promise<unknown>)[] = [];
afterEach(async () => { for (const cleanup of cleanups.splice(0).reverse()) await cleanup(); });
const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');
const json = (response: ServerResponse, data: unknown) => { response.setHeader('content-type', 'application/json'); response.end(JSON.stringify(data)); };
const event = (index: number, text = 'small'): WorkDraft => ({ event_id: `event-${index}`, root_agent_id: 'root', session_id: 'session', type: 'recording_degraded', payload: { text } });

async function fixture(handler: (call: Call, response: ServerResponse) => void | Promise<void>, options: { available?: () => boolean } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'work-uploader-')), path = join(dir, 'inbox.db');
  cleanups.push(() => rmSync(dir, { recursive: true, force: true }));
  const inbox = new InboxStore(path); cleanups.push(() => inbox.close());
  const calls: Call[] = [], errors: unknown[] = [];
  const server = createServer(async (request, response) => {
    const chunks: Buffer[] = []; for await (const chunk of request) chunks.push(chunk as Buffer);
    const body = Buffer.concat(chunks), call = { method: request.method!, path: request.url!, body: body.length ? JSON.parse(body.toString()) : undefined,
      bytes: body.length, authorization: request.headers.authorization, produced: request.headers['x-work-produced-seq'] as string | undefined, processing: request.headers['x-work-processing-pending'] as string | undefined };
    calls.push(call);
    await handler(call, response);
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  cleanups.push(() => new Promise<void>((resolve, reject) => { server.closeAllConnections(); server.close(error => error ? reject(error) : resolve()); }));
  const address = server.address() as { port: number };
  const make = () => new WorkSync({ nodeId: 'node', inbox, url: `http://127.0.0.1:${address.port}`, credentials: () => 'persistent-runtime-secret',
    available: options.available, onError: error => errors.push(error) });
  const sync = make(); cleanups.push(() => sync.stop());
  return { inbox, sync, make, calls, errors, path };
}

test('capability-gated lazy batches advance a lagging ACK and replay retained history after center recovery', async () => {
  let remote = 200, available = false;
  const f = await fixture((call, response) => {
    if (call.method === 'POST') {
      expect(call.body.from_seq).toBe(remote + 1);
      remote = call.body.events.at(-1).seq;
    }
    json(response, { through_seq: remote, expected_seq: remote + 1 });
  }, { available: () => available });
  for (let index = 1; index <= 250; index++) f.inbox.append(event(index));
  f.inbox.acknowledge(190);
  f.sync.start(); f.sync.signal();
  await new Promise(resolve => setImmediate(resolve)); expect(f.calls).toEqual([]);
  available = true; f.sync.signal();
  await expect.poll(() => f.inbox.throughSeq).toBe(250);
  expect(f.calls.find(call => call.method === 'POST')!.body.from_seq).toBe(201);
  expect(f.calls.every(call => !call.path.includes('secret') && call.authorization === 'Bearer persistent-runtime-secret')).toBe(true);
  await f.sync.stop();
  remote = 0;
  const recovered = f.make(); cleanups.push(() => recovered.stop()); recovered.start();
  await expect.poll(() => remote).toBe(250);
  expect(f.inbox.throughSeq).toBe(250); expect(f.inbox.journalSeq).toBe(250);
  for (const call of f.calls.filter(call => call.method === 'POST')) {
    expect(call.bytes).toBeLessThanOrEqual(32 * 1024); expect(call.body.events.length).toBeLessThanOrEqual(100);
  }
  expect(f.errors).toEqual([]);
});

test('a 4 MiB event resumes only missing parts after an uncertain HTTP result and preserves the full body', async () => {
  let remote = 0, failedOnce = false, identity: any, restored: any;
  const received = new Map<number, Buffer>();
  const f = await fixture((call, response) => {
    const part = call.method === 'PUT' ? Number(call.path.split('/').at(-1)) : undefined;
    if (part !== undefined) {
      identity ??= call.body;
      expect(call.body.sha256).toBe(identity.sha256);
      const raw = Buffer.from(call.body.data, 'base64');
      expect(raw.length).toBeLessThanOrEqual(16 * 1024); expect(sha(raw)).toBe(call.body.part_sha256);
      received.set(part, raw);
      if (part === 2 && !failedOnce) { failedOnce = true; response.destroy(); return; }
      if (received.size === identity.total_parts) {
        const rawEvent = Buffer.concat([...received].sort(([a], [b]) => a - b).map(([, bytes]) => bytes));
        expect(sha(rawEvent)).toBe(identity.sha256); expect(rawEvent.length).toBe(identity.total_bytes);
        restored = JSON.parse(rawEvent.toString()); remote = 1;
      }
    }
    json(response, { through_seq: remote, expected_seq: remote + 1, ...(received.size && !remote ? { pending_event: {
      seq: 1, event_id: identity.event_id, sha256: identity.sha256, total_parts: identity.total_parts, received_parts: [...received.keys()],
    } } : {}) });
  });
  const original = event(1, '文'.repeat(Math.ceil(4 * 1024 * 1024 / 3)));
  f.inbox.append(original); f.sync.start();
  await expect.poll(() => f.inbox.throughSeq, { timeout: 12000 }).toBe(1);
  expect(restored).toEqual({ ...original, seq: 1 });
  expect(f.calls.filter(call => call.method === 'PUT' && call.path.endsWith('/parts/2'))).toHaveLength(1);
  expect(f.calls.filter(call => call.method === 'GET').length).toBeGreaterThanOrEqual(2);
  expect(f.calls.filter(call => call.method === 'PUT').every(call => call.bytes <= 64 * 1024)).toBe(true);
  expect(f.errors).toHaveLength(1);
});

test('cursor corruption or a missing local interval pauses without skipping source events', async () => {
  let cursor = 4;
  const f = await fixture((_call, response) => json(response, { through_seq: cursor, expected_seq: cursor + 1 }));
  for (let index = 1; index <= 3; index++) f.inbox.append(event(index));
  f.sync.start();
  await expect.poll(() => f.errors.length).toBe(1);
  expect(String(f.errors[0])).toContain('invalid_cursor'); expect(f.inbox.throughSeq).toBe(0);
  await f.sync.stop(); cursor = 1;
  const database = new DatabaseSync(f.path); database.prepare('DELETE FROM journal WHERE seq=2').run(); database.close();
  const recovered = f.make(); cleanups.push(() => recovered.stop()); recovered.start();
  await expect.poll(() => f.errors.length).toBe(2);
  expect(String(f.errors[1])).toContain('local_journal_gap'); expect(f.inbox.throughSeq).toBe(1);
  expect(f.calls.every(call => call.method === 'GET')).toBe(true);
});

test('events beyond 16 MiB remain local and pause Work rather than creating an oversized upload', async () => {
  const f = await fixture((_call, response) => json(response, { through_seq: 0, expected_seq: 1 }));
  f.inbox.append(event(1, 'x'.repeat(16 * 1024 * 1024)));
  f.sync.start();
  await expect.poll(() => f.errors.length).toBe(1);
  f.sync.signal(); await new Promise(resolve => setImmediate(resolve));
  expect(String(f.errors[0])).toContain('event_too_large');
  expect(f.calls.map(call => call.method)).toEqual(['GET']);
  expect(f.inbox.throughSeq).toBe(0); expect(f.inbox.journalSeq).toBe(1);
});

test('stop cancels a pending HTTP response promptly and never acknowledges its unconfirmed event', async () => {
  const f = await fixture(() => {});
  f.inbox.append(event(1)); f.sync.start();
  await expect.poll(() => f.calls.length).toBe(1);
  const started = Date.now(); await f.sync.stop();
  expect(Date.now() - started).toBeLessThan(500);
  expect(f.inbox.throughSeq).toBe(0); expect(f.errors).toEqual([]);
});

test('all parts durable before a center crash still finalize on restart',async()=>{
 let committed=false;
 const f=await fixture((call,response)=>{
  const event=f.inbox.journal(0,1)[0]!,raw=Buffer.from(JSON.stringify(event)),total=Math.ceil(raw.length/16384);
  if(call.method==='PUT') {expect(call.path.endsWith(`/parts/${total-1}`)).toBe(true);committed=true;}
  json(response,{through_seq:committed?1:0,expected_seq:committed?2:1,...(committed?{}:{pending_event:{seq:1,event_id:event.event_id,sha256:sha(raw),total_parts:total,received_parts:Array.from({length:total},(_,i)=>i)}})});
 });
 f.inbox.append(event(1,'x'.repeat(106*1024)));f.sync.start();
 await expect.poll(()=>f.inbox.throughSeq).toBe(1);expect(f.calls.filter(c=>c.method==='PUT')).toHaveLength(1);expect(f.errors).toEqual([]);
});
test('a busy center Retry-After remains a minimum even during the first jittered retry',async()=>{
 const times:number[]=[];
 const f=await fixture((_call,response)=>{
  times.push(Date.now());
  if(times.length===1){response.statusCode=429;response.setHeader('retry-after','2');json(response,{detail:'work_sync_busy'});}
  else json(response,{through_seq:0,expected_seq:1});
 });
 f.sync.start();await expect.poll(()=>f.calls.length,{timeout:5000}).toBe(2);
 expect(times[1]!-times[0]!).toBeGreaterThanOrEqual(2000);expect(f.errors).toHaveLength(1);
});


test('reports processing separately from upload ACK, including completion with no new events', async () => {
  let remote=0;
  const f=await fixture((call,response)=>{if(call.method==='POST')remote=call.body.events.at(-1).seq;json(response,{through_seq:remote,expected_seq:remote+1});});
  f.inbox.workPending('main',true);f.inbox.append(event(1));f.sync.start();
  await expect.poll(()=>f.inbox.throughSeq).toBe(1);
  expect(f.calls.at(-1)).toMatchObject({produced:'1',processing:'true'});
  f.inbox.workPending('main',false);f.sync.signal();
  await expect.poll(()=>f.calls.at(-1)?.processing).toBe('false');
  expect(f.calls.at(-1)).toMatchObject({method:'GET',produced:'1'});
  expect(f.inbox.journalSeq).toBe(1);expect(f.errors).toEqual([]);
});
