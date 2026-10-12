import { afterEach, expect, test } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import WebSocket from 'ws';
import { WebRelayConnection, type ProtocolFrame, type RelayDiagnostic } from '@nano/channels';
import { createServer } from '../src/server.js';
import { digest } from '../src/identity.js';
import { Frames } from './e2e/helpers.js';

const cleanups: (() => unknown | Promise<unknown>)[] = [];
afterEach(async () => { for (const cleanup of cleanups.splice(0).reverse()) await cleanup(); });
const pause = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

async function fixture() {
  const dir = mkdtempSync(join(tmpdir(), 'node-connection-'));
  cleanups.push(() => rmSync(dir, { recursive: true, force: true }));
  const app = await createServer({ dbPath: join(dir, 'im.db'), publicUrl: 'http://127.0.0.1:8011', jwtSecret: 'isolated-connection-regression' });
  cleanups.push(() => app.close());
  const db = app.im.db;
  for (const id of ['alice', 'admin']) {
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,password_hash,membership_status,is_company_admin,created_at) VALUES(?,?,?,?,?,'active',?,datetime('now'))")
      .run(id, id, id, id, '$2b$12$EF/L52c0/DOIAIzztg.vLeo3btIdIuVbW5/M3UBiyztqi7ZLIfTUW', Number(id === 'admin'));
  }
  db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('node','alice','Node','offline')").run();
  db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch,runtime_token_hash) VALUES('node','alice',1,?)").run(digest('runtime-secret'));
  const url = await app.listen({ port: 0, host: '127.0.0.1' });
  const tokens: Record<string, string> = {};
  for (const id of ['alice', 'admin']) {
    const response = await app.inject({ method: 'POST', url: '/im/v1/auth/login', payload: { username: id, password: 'old-password' } });
    expect(response.statusCode).toBe(200); tokens[id] = response.json().access_token;
  }
  const http = (method: 'GET' | 'POST', path: string, payload?: object, user = 'alice') => app.inject({ method, url: path, payload, headers: { authorization: `Bearer ${tokens[user]}` } });
  async function browser(user: string) {
    const ticket = (await http('POST', '/im/v1/auth/ws-ticket', {}, user)).json().ticket;
    const socket = new WebSocket(`${url.replace('http:', 'ws:')}/im/ws/user?ticket=${ticket}`, { headers: { Origin: 'http://127.0.0.1:8011' } });
    const frames = new Frames(socket);
    cleanups.push(() => socket.terminate());
    await once(socket, 'open');
    socket.send(JSON.stringify({ op: 'resume', after_event_id: 0 }));
    await expect.poll(() => [...app.im.gateway.browsers].some(b => b.userId === user && b.ready)).toBe(true);
    return frames;
  }
  function relay() {
    const received: ProtocolFrame[] = [];
    const diagnostics: RelayDiagnostic[] = [];
    const connection = new WebRelayConnection({ url,
      credentials: () => ({ accessToken: 'runtime-secret', registration: { node_id: 'node', agents: ['assistant'] } }),
      heartbeatIntervalMs: 30000, ackTimeoutMs: 2000, reconnectInitialMs: 500, reconnectMaxMs: 500,
      onFrame: frame => { received.push(frame); },
      onDiagnostic: event => { diagnostics.push(event); },
    });
    cleanups.push(() => connection.stop());
    return { connection, received, diagnostics };
  }
  return { app, db, http, browser, relay };
}
const status = (value: string) => (frame: any) => frame.event_type === 'node.status_changed' && frame.data.status === value;

test('closing the server sends the shutdown reason before the WebSocket plugin closes clients', async () => {
  const f = await fixture(), { connection, diagnostics } = f.relay();
  await connection.start();
  await f.app.close();
  await expect.poll(() => diagnostics.some(event => event.close_code === 1001 && event.close_reason === 'server_shutdown')).toBe(true);
  expect(connection.state).not.toBe('revoked');
});

test('real IM heartbeat guard persists offline, notifies the owner and lets the Relay re-register for new traffic', async () => {
  const f = await fixture();
  const owner = await f.browser('alice'), outsider = await f.browser('admin');
  const { connection, received } = f.relay();
  await connection.start();
  await owner.next(status('online'));
  const old = f.app.im.gateway.nodes.get('node')!;
  const closed = once(old.socket, 'close');
  // Fault injection only: the production guard and all cleanup/transport paths run unchanged.
  old.lastSeen = Date.now() - 91000;
  const [code] = await closed;
  expect(code).toBe(1012);
  expect((await owner.next(status('offline'))).data.last_error).toBe('heartbeat_timeout');
  expect(f.db.prepare('SELECT status,last_error FROM nodes WHERE node_id=?').get('node')).toMatchObject({ status: 'offline', last_error: 'heartbeat_timeout' });
  expect((await f.http('GET', '/im/v1/nodes')).json()[0].status).toBe('offline');
  await owner.next(frame => frame.event_type === 'agent.status_changed' && frame.data.status === 'offline');
  await expect.poll(() => connection.ready && f.app.im.gateway.nodes.get('node') !== old).toBe(true);
  expect((await owner.next(status('online'))).data.last_error).toBeNull();
  expect((await f.http('GET', '/im/v1/nodes')).json()[0]).toMatchObject({ status: 'online', last_error: null });
  expect(f.app.im.identity.authenticateRuntime('runtime-secret')).not.toBeNull();
  const created = await f.http('POST', '/im/v1/conversations', { title: 'Recovery', type: 'direct', participants: [{ type: 'agent', id: 'assistant' }] });
  expect(created.statusCode, created.body).toBe(201);
  const sent = await f.http('POST', `/im/v1/conversations/${created.json().id}/messages`, { sender_user_id: 'alice', content: 'new message after recovery' });
  expect(sent.statusCode).toBe(201);
  await expect.poll(() => received.some(frame => frame.type === 'relay.message' && (frame.payload.message as any).id === sent.json().id)).toBe(true);
  expect(outsider.queue.some(frame => /^(node|agent)\.status_changed$/.test(frame.event_type))).toBe(false);
}, 15000);

test('replacing a connection does not publish offline for the new registered connection', async () => {
  const f = await fixture(), owner = await f.browser('alice');
  const old = f.relay().connection; await old.start(); await owner.next(status('online'));
  const replacement = f.relay().connection; await replacement.start();
  await expect.poll(() => old.state).toBe('revoked');
  await pause(50);
  expect(replacement.ready).toBe(true);
  expect((await f.http('GET', '/im/v1/nodes')).json()[0].status).toBe('online');
  expect(owner.queue.some(status('offline'))).toBe(false);
});

test('account suspension uses real authority revocation, persists offline and stops reconnecting', async () => {
  const f = await fixture(), relay = f.relay().connection;
  await relay.start();
  const response = await f.http('POST', '/im/v1/company/members/alice/suspend', {}, 'admin');
  expect(response.statusCode).toBe(200);
  await expect.poll(() => relay.state).toBe('revoked');
  await pause(600);
  expect(relay.state).toBe('revoked');
  expect(f.app.im.identity.authenticateRuntime('runtime-secret')).toBeNull();
  expect(f.db.prepare('SELECT status FROM nodes WHERE node_id=?').get('node')).toMatchObject({ status: 'offline' });
  expect(f.app.im.gateway.isOnline('node')).toBe(false);
});
