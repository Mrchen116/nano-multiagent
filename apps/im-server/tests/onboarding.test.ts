import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, expect, it, vi } from 'vitest';
import { createServer } from '../src/server.js';

const closers: (() => Promise<void>)[] = [];
afterEach(async () => { for (const close of closers.splice(0)) await close(); });
async function fixture(published = true) {
  const dir = mkdtempSync(join(tmpdir(), 'nano-onboarding-'));
  if (published) {
    writeFileSync(join(dir, 'manifest.json'), JSON.stringify({ sha256: 'a'.repeat(64) }));
    writeFileSync(join(dir, 'nano-node.tgz'), 'runtime');
  }
  const app = await createServer({ dbPath: join(dir, 'im.sqlite3'), publicUrl: 'https://nano.example', nodeReleaseDir: dir });
  closers.push(async () => { await app.close(); rmSync(dir, { recursive: true, force: true }); });
  const pair = await app.im.identity.register('alice', 'password1', 'Alice');
  app.im.identity.initializeCompany(pair.user.id);
  const headers = { authorization: 'Bearer ' + pair.access_token };
  return { app, headers, owner: pair.user.owner_id };
}
it('offers only the current account resources and server-origin installation materials', async () => {
  const { app, headers, owner } = await fixture();
  app.im.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status,last_heartbeat_at,agent_count,version) VALUES('mine',?,'My laptop','online','',0,''),('other','other','Secret computer','online','',0,'')").run(owner);
  const response = await app.inject({ url: '/im/v1/onboarding', headers: { ...headers, host: 'attacker.example' } });
  expect(response.statusCode).toBe(200);
  expect(response.json().nodes.map((n: any) => n.node_id)).toEqual(['mine']);
  expect(response.json().install.command).toContain('https://nano.example/install.sh');
  expect(response.body).not.toContain('attacker');
  expect(response.body).not.toContain('Secret computer');
  const script = await app.inject({ url: '/install.sh', headers: { host: 'attacker.example' } });
  expect(script.statusCode).toBe(200);
  expect(script.body).toContain("NANO_ORIGIN='https://nano.example'");
  expect(script.body).not.toContain('attacker');
});
it('refuses setup on another owner node and rechecks transfer after an in-flight response', async () => {
  const { app, headers, owner } = await fixture();
  app.im.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status,last_heartbeat_at,agent_count,version) VALUES('mine',?,'Laptop','online','',0,''),('other','other','Other','online','',0,'')").run(owner);
  const rpc = vi.spyOn(app.im.gateway, 'request').mockResolvedValue({ models: [], api_key: 'never-return', operation: { state: 'testing', api_key: 'never-return' } });
  expect((await app.inject({ method: 'POST', url: '/im/v1/nodes/other/setup', headers, payload: { action: 'status' } })).statusCode).toBe(404);
  expect(rpc).not.toHaveBeenCalled();
  const response = await app.inject({ method: 'POST', url: '/im/v1/nodes/mine/setup', headers, payload: { action: 'status' } });
  expect(response.statusCode).toBe(200);
  expect(response.body).not.toContain('never-return');
  rpc.mockImplementationOnce(async () => {
    app.im.db.prepare("UPDATE nodes SET owner_id='other' WHERE node_id='mine'").run();
    return { models: [{ provider: 'secret', model: 'secret' }] };
  });
  const moved = await app.inject({ method: 'POST', url: '/im/v1/nodes/mine/setup', headers, payload: { action: 'status' } });
  expect(moved.statusCode).toBe(404);
  expect(moved.body).not.toContain('secret');
});
it('does not present an unpublished installer as downloadable', async () => {
  const { app, headers } = await fixture(false);
  expect((await app.inject({ url: '/im/v1/onboarding', headers })).json().install.available).toBe(false);
  expect((await app.inject('/install.sh')).statusCode).toBe(503);
});
