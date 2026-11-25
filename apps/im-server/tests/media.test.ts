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

it('uploads and downloads general files with safe headers, MIME normalization, 0-byte rejection, and idempotent gateway routes', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'im-media-generic-'));
  const app = await createServer({ dbPath: join(directory, 'im.db'), publicUrl: 'http://localhost', jwtSecret: 'isolated-media-test-secret' });
  try {
    const owner = await app.im.identity.register('owner', 'password-123', 'Owner');
    const outsider = await app.im.identity.register('outsider', 'password-123', 'Outsider');
    const now = new Date().toISOString();
    app.im.db.prepare("INSERT INTO conversations(id,title,type,space_id,created_at) VALUES('files','Files','direct',?,?)").run(`personal:${owner.user.id}`, now);
    app.im.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('files',?)").run(owner.user.id);
    const auth = { authorization: `Bearer ${owner.access_token}` };
    const outsiderAuth = { authorization: `Bearer ${outsider.access_token}` };

    const empty = await app.inject({ method: 'POST', url: '/im/v1/uploads?conversation_id=files&file_name=empty.csv', payload: Buffer.alloc(0), headers: { ...auth, 'content-type': 'text/csv' } });
    expect(empty.statusCode).toBe(400);

    const cases = [
      { name: 'report.csv', sendMime: '', expectedMime: 'text/csv', body: Buffer.from('a,b\n1,2\n') },
      { name: 'bundle.zip', sendMime: 'application/octet-stream', expectedMime: 'application/zip', body: Buffer.from([0x50, 0x4b, 0x03, 0x04, 0x00, 0x01]) },
      { name: 'config.yaml', sendMime: '', expectedMime: 'text/yaml', body: Buffer.from('env: staging\n') },
      { name: 'diagram.svg', sendMime: 'image/svg+xml', expectedMime: 'image/svg+xml', body: Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>') },
      { name: 'page.html', sendMime: 'text/html', expectedMime: 'text/html', body: Buffer.from('<html><body>hi</body></html>') },
      { name: '报告 2026.mybin', sendMime: '', expectedMime: 'application/octet-stream', body: Buffer.from([0x00, 0xff, 0x7f, 0x42]) },
    ];
    for (const item of cases) {
      const upload = await app.inject({
        method: 'POST',
        url: `/im/v1/uploads?conversation_id=files&file_name=${encodeURIComponent(item.name)}`,
        payload: item.body,
        headers: { ...auth, ...(item.sendMime ? { 'content-type': item.sendMime } : { 'content-type': 'application/octet-stream' }) },
      });
      expect(upload.statusCode, upload.body).toBe(201);
      expect(upload.json()).toMatchObject({ content_type: item.expectedMime, file_name: item.name });
      const download = await app.inject({ method: 'GET', url: upload.json().url, headers: auth });
      expect(download.statusCode).toBe(200);
      expect(download.headers['x-content-type-options']).toBe('nosniff');
      expect(download.headers['content-security-policy']).toBe("default-src 'none'; sandbox");
      expect(String(download.headers['content-disposition'])).toMatch(/^attachment; filename="[^"]+"; filename\*=UTF-8''/);
      expect(download.rawPayload).toEqual(item.body);
      const blocked = await app.inject({ method: 'GET', url: upload.json().url, headers: outsiderAuth });
      expect([403, 404]).toContain(blocked.statusCode);
    }

    // Raster image download keeps nosniff and inline Content-Disposition (preserving original file name) without sandbox CSP.
    const png = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 0]);
    const pngUpload = await app.inject({ method: 'POST', url: '/im/v1/uploads?conversation_id=files&file_name=shot.png', payload: png, headers: { ...auth, 'content-type': 'image/png' } });
    expect(pngUpload.statusCode).toBe(201);
    const pngDownload = await app.inject({ method: 'GET', url: pngUpload.json().url, headers: auth });
    expect(pngDownload.statusCode).toBe(200);
    expect(pngDownload.headers['x-content-type-options']).toBe('nosniff');
    expect(String(pngDownload.headers['content-disposition'])).toMatch(/^inline; filename="shot\.png"; filename\*=UTF-8''shot\.png$/);
    expect(pngDownload.headers['content-security-policy']).toBeUndefined();

    // Gateway idempotent attachment upload & recovery route (gateway credential required)
    const userOnGatewayRoute = await app.inject({ method: 'POST', url: '/im/v1/conversations/files/attachments?file=1&file_name=data.csv', payload: Buffer.from('x,y\n'), headers: { ...auth, 'content-type': 'text/csv', 'idempotency-key': 'op-user:0' } });
    expect([401, 403]).toContain(userOnGatewayRoute.statusCode);

    const ownerId = owner.user.owner_id ?? owner.user.id;
    app.im.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('node-1',?,'Node','online')").run(ownerId);
    app.im.db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch) VALUES('node-1',?,1)").run(ownerId);
    app.im.db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status,personal_space_enabled) VALUES('agent-user-a','agent:agent-a','Agent A',?,?,'active',1)").run(ownerId, now);
    app.im.db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,space_id,display_name,workspace_root,created_at,updated_at) VALUES('agent-a',?,'node-1',?,'Agent A','/ws',?,?)").run(ownerId, `personal:${owner.user.id}`, now, now);
    app.im.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('files','agent-user-a')").run();
    app.im.gateway.nodes.set('node-1', { node_id: 'node-1', owner_id: ownerId, node_epoch: 1, token: 'gateway-token-1',
      socket: { readyState: 1, send() {}, close() {} } } as any);
    const gwAuth = { authorization: 'Bearer gateway-token-1' };

    const badFlag = await app.inject({ method: 'POST', url: '/im/v1/conversations/files/attachments?agent_id=agent-a&lifecycle_revision=1&file_name=data.csv', payload: Buffer.from('x,y\n'), headers: { ...gwAuth, 'content-type': 'text/csv', 'idempotency-key': 'op-1:0' } });
    expect(badFlag.statusCode).toBe(403);

    const reservedPrefixOnImages = await app.inject({ method: 'POST', url: '/im/v1/conversations/files/images?agent_id=agent-a&lifecycle_revision=1&screenshot=1&file_name=shot.png', payload: png, headers: { ...gwAuth, 'content-type': 'image/png', 'idempotency-key': 'file:reserved' } });
    expect(reservedPrefixOnImages.statusCode).toBe(400);

    const first = await app.inject({ method: 'POST', url: '/im/v1/conversations/files/attachments?agent_id=agent-a&lifecycle_revision=1&file=1&file_name=data.csv', payload: Buffer.from('k,v\n1,2\n'), headers: { ...gwAuth, 'content-type': 'text/csv', 'idempotency-key': 'op-1:0' } });
    expect(first.statusCode, first.body).toBe(201);
    const second = await app.inject({ method: 'POST', url: '/im/v1/conversations/files/attachments?agent_id=agent-a&lifecycle_revision=1&file=1&file_name=data.csv', payload: Buffer.from('k,v\n1,2\n'), headers: { ...gwAuth, 'content-type': 'text/csv', 'idempotency-key': 'op-1:0' } });
    expect(second.statusCode).toBe(200);
    expect(second.json()).toEqual(first.json());

    const lookup = await app.inject({ method: 'GET', url: '/im/v1/conversations/files/attachments?agent_id=agent-a&lifecycle_revision=1&upload_key=op-1:0', headers: gwAuth });
    expect(lookup.statusCode).toBe(200);
    expect(lookup.json()).toEqual({ attachment: first.json() });

    const missingLookup = await app.inject({ method: 'GET', url: '/im/v1/conversations/files/attachments?agent_id=agent-a&lifecycle_revision=1&upload_key=missing', headers: gwAuth });
    expect(missingLookup.statusCode).toBe(200);
    expect(missingLookup.json()).toEqual({ attachment: null });

    app.im.db.prepare("INSERT INTO conversations(id,title,type,space_id,created_at) VALUES('private-other','Private','direct',?,?)").run(`personal:${outsider.user.id}`, now);
    app.im.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('private-other',?)").run(outsider.user.id);
    const nonMemberUpload = await app.inject({ method: 'POST', url: '/im/v1/conversations/private-other/attachments?agent_id=agent-a&lifecycle_revision=1&file=1&file_name=data.csv', payload: Buffer.from('k,v\n'), headers: { ...gwAuth, 'content-type': 'text/csv', 'idempotency-key': 'op-outsider:0' } });
    expect([403, 404]).toContain(nonMemberUpload.statusCode);
  } finally {
    await app.close();
    rmSync(directory, { recursive: true, force: true });
  }
});
