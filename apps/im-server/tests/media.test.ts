import Fastify from 'fastify';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { expect, it } from 'vitest';
import { openDatabase } from '../src/db.js';
import { registerMediaRoutes } from '../src/media.js';
import type { ImContext } from '../src/context.js';

it('stores retryable file versions, preserves prior bytes, and rejects key/hash or stale-version conflicts', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-media-'));
  const db = openDatabase(join(directory, 'im.db'));
  db.prepare("INSERT INTO conversations(id,title,created_at) VALUES('private','Private','2026-01-01')").run();
  db.prepare("INSERT INTO conversations(id,title,created_at) VALUES('other','Other','2026-01-01')").run();
  const ctx = { db, dbPath: join(directory, 'im.db'), identity: {rateLimit() {}}, messaging: {principal: () => ({kind:'user',id:'owner'}), access() {}} } as unknown as ImContext;
  const start = async () => { const app = Fastify(); await registerMediaRoutes(app, ctx); return app; };
  let app = await start();
  const upload = (key: string, payload: string, extra = '', sha = createHash('sha256').update(payload).digest('hex')) => app.inject({method:'POST',url:`/im/v1/uploads?conversation_id=private&file_name=plan.md${extra}`,payload,headers:{'content-type':'text/markdown','idempotency-key':key,'x-content-sha256':sha}});
  try {
    const first = await upload('create-plan', 'First version');
    expect(first.statusCode, first.body).toBe(201);
    const receipt = first.json();
    expect(receipt).toMatchObject({version:1,sha256:createHash('sha256').update('First version').digest('hex'),byte_size:13,receipt:{status:'stored',resource_id:receipt.resource_id}});
    expect((await upload('create-plan', 'First version')).json()).toEqual(receipt);
    expect((await upload('create-plan', 'Changed bytes')).statusCode).toBe(409);
    expect((await upload('bad-hash', 'First version', '', '0'.repeat(64))).statusCode).toBe(409);
    const update = `&artifact_id=${receipt.artifact_id}&expected_version=1`;
    const revised = await upload('revise-plan', 'Second version', update);
    expect(revised.statusCode, revised.body).toBe(201);
    expect(revised.json()).toMatchObject({artifact_id:receipt.artifact_id,version:2,previous_resource_id:receipt.resource_id});
    expect((await upload('stale', 'Third version', update)).statusCode).toBe(409);
    expect((await upload('missing-version', 'Third version', `&artifact_id=${receipt.artifact_id}`)).statusCode).toBe(400);
    expect((await upload('foreign', 'Third version', '&artifact_id=foreign&expected_version=1')).statusCode).toBe(404);
    await app.close(); app = await start();
    expect((await upload('revise-plan', 'Second version', update)).json()).toEqual(revised.json());
    expect((await app.inject({method:'GET',url:receipt.url})).body).toBe('First version');
    expect((await app.inject({method:'GET',url:revised.json().url})).body).toBe('Second version');
    expect(db.prepare('SELECT count(*) n FROM message_images').get()).toMatchObject({n:2});
    expect(db.prepare("SELECT count(*) n FROM attachment_storage WHERE state='reserved'").get()).toMatchObject({n:0});
  } finally { await app.close(); db.close(); await rm(directory,{recursive:true,force:true}); }
});
