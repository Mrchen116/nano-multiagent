import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { createServer } from '../src/server.js';

it('uses supported image signatures over clipboard declarations and rejects non-image contents', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'im-media-'));
  const app = await createServer({ dbPath: join(directory, 'im.db'), publicUrl: 'http://localhost', jwtSecret: 'isolated-media-test-secret' });
  try {
    const owner = await app.im.identity.register('owner', 'password-123', 'Owner');
    const now = new Date().toISOString();
    app.im.db.prepare("INSERT INTO conversations(id,title,type,space_id,created_at) VALUES('images','Images','direct',?,?)").run(`personal:${owner.user.id}`, now);
    app.im.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('images',?)").run(owner.user.id);
    const headers = { authorization: `Bearer ${owner.access_token}`, 'content-type': 'image/png' };
    // This seam validates signatures, rather than decoding pixels.
    for (const [payload, type, name] of [
      [Buffer.from([137,80,78,71,13,10,26,10,0,0,0,0]), 'image/png', 'image.png'],
      [Buffer.from([255,216,255,224,0,16,74,70,73,70,0,1]), 'image/jpeg', 'image.jpg']
    ] as const) {
      const upload = await app.inject({ method: 'POST', url: '/im/v1/uploads?conversation_id=images&file_name=image.png', payload, headers });
      expect(upload.statusCode, upload.body).toBe(201);
      expect(upload.json()).toMatchObject({ content_type: type, file_name: name });
      const download = await app.inject({ method: 'GET', url: upload.json().url, headers });
      expect(download.statusCode).toBe(200);
      expect(download.headers['content-type']).toBe(type);
      expect(download.rawPayload).toEqual(payload);
    }
    const rejected = await app.inject({ method: 'POST', url: '/im/v1/uploads?conversation_id=images&file_name=image.png', payload: Buffer.from('not an image'), headers });
    expect(rejected.statusCode).toBe(415);
    expect(rejected.json()).toMatchObject({ detail: 'image content does not match content type' });
  } finally {
    await app.close();
    rmSync(directory, { recursive: true, force: true });
  }
});
