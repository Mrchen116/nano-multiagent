import { afterEach, expect, it } from 'vitest';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { PassThrough, Readable } from 'node:stream';
import { registerMediaRoutes } from '../src/media.js';

const cleanups: (() => void)[] = [];
afterEach(() => { for (const cleanup of cleanups.splice(0).reverse()) cleanup(); });
const ownerLimit = 1024 ** 3, serviceLimit = 10 * ownerLimit;

async function fixture(seed: {owner: string; bytes: number; state?: string}[] = []) {
  const directory = mkdtempSync(join(tmpdir(), 'nano-media-quota-'));
  cleanups.push(() => rmSync(directory, { recursive: true, force: true }));
  const db = new DatabaseSync(':memory:'); cleanups.push(() => db.close());
  db.exec(readFileSync(new URL('../src/schema.sql', import.meta.url), 'utf8'));
  db.prepare("INSERT INTO conversations(id,title,type,created_at) VALUES('chat','Chat','group','2026-01-01')").run();
  for (const [index, row] of seed.entries()) db.prepare('INSERT INTO attachment_storage VALUES(?,?,?,?)').run(`seed-${index}`, row.owner, row.bytes, row.state ?? 'stored');
  const handlers = new Map<string, (req: any, reply: any) => Promise<any>>();
  const app = { get() {}, post(path: string, handler: any) { handlers.set(path, handler); },
    async register(install: (app: any) => Promise<void>) { await install(app); }, removeAllContentTypeParsers() {}, addContentTypeParser() {} };
  let denied = false;
  const ctx = { db, dbPath: join(directory, 'im.db'), identity: { rateLimit() {} },
    messaging: { principal: (req: any) => ({ kind: 'user', id: req.owner }), access() { if (denied) throw new Error('access revoked'); } } };
  // Exercise the registered streaming handler and real storage/files; auth is owned by route tests.
  await registerMediaRoutes(app as any, ctx as any);
  const upload = (body: Readable, owner = 'owner', imageKey?: string) => {
    const url = imageKey ? '/im/v1/conversations/:conversation_id/images' : '/im/v1/uploads';
    return handlers.get(url)!({ body, owner, url, query: { conversation_id: 'chat', file_name: 'fixture' }, params: { conversation_id: 'chat' },
      headers: { 'content-type': imageKey ? 'image/png' : 'text/plain', 'idempotency-key': imageKey } }, { code() { return this; } });
  };
  const reserved = () => Number(db.prepare("SELECT coalesce(sum(byte_size),0) n FROM attachment_storage WHERE state='reserved'").get()!.n);
  const used = () => Number(db.prepare('SELECT coalesce(sum(byte_size),0) n FROM attachment_storage').get()!.n);
  return { upload, reserved, used, db, deny: () => { denied = true; }, allow: () => { denied = false; } };
}

it.each(['owner', 'service'])('counts concurrent %s reservations and releases a failed upload', async limit => {
  const f = await fixture(limit === 'owner' ? [{ owner: 'owner', bytes: ownerLimit - 10 }]
    : [{ owner: 'historical', bytes: serviceLimit - 10 }]);
  const firstBody = new PassThrough();
  const first = f.upload(firstBody).catch(error => error);
  firstBody.write(Buffer.alloc(6));
  await expect.poll(f.reserved).toBe(6);
  await expect(f.upload(Readable.from([Buffer.alloc(5)]), limit === 'owner' ? 'owner' : 'other')).rejects.toMatchObject({ statusCode: 507 });
  expect(f.reserved()).toBe(6);
  firstBody.destroy(new Error('connection aborted'));
  expect(await first).toMatchObject({ message: 'connection aborted' });
  expect(f.reserved()).toBe(0);
  await f.upload(Readable.from([Buffer.alloc(10)]));
  expect(f.used()).toBe(limit === 'owner' ? ownerLimit : serviceLimit);
  await expect(f.upload(Readable.from([Buffer.alloc(1)]))).rejects.toMatchObject({ statusCode: 507 });
});

it('rebuilds quota after restart cleanup and releases only accepted bytes on oversize', async () => {
  const f = await fixture([{ owner: 'owner', bytes: ownerLimit - 10 }, { owner: 'owner', bytes: 100, state: 'reserved' }]);
  expect(f.reserved()).toBe(0);
  const body = Readable.from((async function* () { yield Buffer.alloc(6); yield Buffer.alloc(10 * 1024 * 1024); })());
  await expect(f.upload(body)).rejects.toMatchObject({ statusCode: 413 });
  expect(f.used()).toBe(ownerLimit - 10);
  await f.upload(Readable.from([Buffer.alloc(10)]));
  await expect(f.upload(Readable.from([Buffer.alloc(1)]))).rejects.toMatchObject({ statusCode: 507 });
});

it('releases rejected content and duplicate-image reservations while retaining stored bytes', async () => {
  const f = await fixture([{ owner: 'owner', bytes: ownerLimit - 24 }]);
  await expect(f.upload(Readable.from([Buffer.from('not an image')]), 'owner', 'bad')).rejects.toMatchObject({ statusCode: 415 });
  const png = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const first = await f.upload(Readable.from([png]), 'owner', 'image');
  expect(await f.upload(Readable.from([png]), 'owner', 'image')).toEqual(first);
  expect(f.used()).toBe(ownerLimit - 16);
  const body = new PassThrough(), revoked = f.upload(body).catch(error => error);
  body.write(Buffer.alloc(4)); await expect.poll(f.reserved).toBe(4);
  f.deny(); body.end(); expect(await revoked).toMatchObject({ message: 'access revoked' });
  f.allow(); expect(f.used()).toBe(ownerLimit - 16);
  await f.upload(Readable.from([Buffer.alloc(16)]));
  await expect(f.upload(Readable.from([Buffer.alloc(1)]))).rejects.toMatchObject({ statusCode: 507 });
});
