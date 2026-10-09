import { afterEach, expect, test } from 'vitest';
import { WebSocketServer, type WebSocket } from 'ws';
import { WebRelayConnection, RelayDeliveryError, type ProtocolFrame } from '../src/index.js';

const cleanups: (() => Promise<void>)[] = [];
afterEach(async () => { for (const cleanup of cleanups.splice(0).reverse()) await cleanup(); });
const pause = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
async function server(handle: (socket: WebSocket, frame: ProtocolFrame) => void) {
  const headers: string[] = [];
  const connections: WebSocket[] = [];
  const frames: ProtocolFrame[] = [];
  const wss = new WebSocketServer({ port: 0 });
  await new Promise<void>(resolve => wss.once('listening', resolve));
  wss.on('connection', (socket, req) => {
    headers.push(req.headers.authorization ?? ''); connections.push(socket);
    socket.on('message', data => { const frame = JSON.parse(data.toString()); frames.push(frame); handle(socket, frame); });
  });
  cleanups.push(async () => { for (const socket of wss.clients) socket.terminate(); await new Promise<void>(resolve => wss.close(() => resolve())); });
  const address = wss.address();
  if (typeof address === 'string' || !address) throw new Error('No port');
  return { url: `http://127.0.0.1:${address.port}`, headers, connections, frames };
}
function ack(socket: WebSocket, frame: ProtocolFrame, extra = {}) {
  socket.send(JSON.stringify({ type: 'ack', payload: { message_type: frame.type, ...extra } }));
}
function connection(url: string, extras: Partial<ConstructorParameters<typeof WebRelayConnection>[0]> = {}) {
  const relay = new WebRelayConnection({ url, credentials: async () => ({ accessToken: 'secret', registration: { node_id: 'node', agents: [] } }), heartbeatIntervalMs: 10000, ackTimeoutMs: 100, reconnectInitialMs: 10, reconnectMaxMs: 20, onFrame() {}, ...extras });
  cleanups.push(() => relay.stop());
  return relay;
}

test('registration gates business sends and blocked inbound handlers do not block ACKs or control input', async () => {
  let register!: ProtocolFrame;
  const received: string[] = [];
  const s = await server((socket, frame) => {
    if (frame.type === 'node.register') { register = frame; return; }
    socket.send(JSON.stringify({ type: 'relay.message', payload: {} }));
    socket.send(JSON.stringify({ type: 'agent.work.cancel', payload: {} }));
    socket.send(JSON.stringify({ type: 'agent.work.permission', payload: {} }));
    ack(socket, frame);
  });
  const relay = connection(s.url, { onFrame: async frame => { received.push(frame.type); await new Promise(() => {}); } });
  const started = relay.start();
  await expect(relay.request('node.report', {})).rejects.toMatchObject({ delivery: 'not-sent' });
  await pause(20);
  expect(s.frames.map(f => f.type)).toEqual(['node.register']);
  ack(s.connections[0]!, register, { gateway_access_token: 'gateway', node_epoch: 4 });
  expect(await started).toMatchObject({ gateway_access_token: 'gateway', node_epoch: 4 });
  expect(s.headers).toEqual(['Bearer secret']);
  await expect(relay.request('node.report', { node_id: 'node' })).resolves.toMatchObject({ type: 'ack' });
  expect(received).toEqual(['relay.message', 'agent.work.cancel', 'agent.work.permission']);
});

test('typed responses require matching correlation and generic rejection advances FIFO', async () => {
  const s = await server((socket, frame) => {
    if (frame.type === 'conversation.query') {
      socket.send(JSON.stringify({ type: 'conversation.query.result', payload: { request_id: 'wrong' } }));
      setTimeout(() => socket.send(JSON.stringify({ type: 'conversation.query.result', payload: { request_id: frame.payload.request_id } })), 10);
    } else if (frame.type === 'node.report') socket.send(JSON.stringify({ type: 'error', payload: { code: 'rejected', message_type: frame.type } }));
    else ack(socket, frame);
  });
  const relay = connection(s.url); await relay.start();
  expect((await relay.request('conversation.query', { request_id: 'right' })).payload.request_id).toBe('right');
  const rejected = relay.request('node.report', {});
  const next = relay.request('agent.message', {});
  await expect(rejected).rejects.toMatchObject({ delivery: 'rejected', code: 'rejected' });
  await expect(next).resolves.toMatchObject({ payload: { message_type: 'agent.message' } });
});

test('reconnect refreshes auth and registration without replaying uncertain or queued business frames', async () => {
  let tokens = 0;
  const s = await server((socket, frame) => { if (frame.type === 'node.report') socket.close(1012); else ack(socket, frame); });
  const relay = connection(s.url, { credentials: async () => ({ accessToken: `token-${++tokens}`, registration: { node_id: 'node' } }) });
  await relay.start();
  const sent = relay.request('node.report', {});
  const queued = relay.request('agent.message', {});
  await expect(sent).rejects.toMatchObject({ delivery: 'unknown' });
  await expect(queued).rejects.toMatchObject({ delivery: 'not-sent' });
  await pause(60);
  expect(s.headers).toEqual(['Bearer token-1', 'Bearer token-2']);
  expect(s.frames.map(f => f.type)).toEqual(['node.register', 'node.report', 'node.register']);
  expect(relay.ready).toBe(true);
});

test('heartbeat timeout reconnects; revoked identity stops automatic reconnect', async () => {
  const s = await server((socket, frame) => { if (frame.type === 'node.register') ack(socket, frame); });
  const relay = connection(s.url, { heartbeatIntervalMs: 15, ackTimeoutMs: 30 });
  await relay.start(); await pause(70);
  expect(s.connections.length).toBeGreaterThanOrEqual(2);
  s.connections.at(-1)!.close(4003, 'revoked');
  await pause(20);
  expect(relay.state).toBe('revoked');
  const count = s.connections.length;
  await pause(60); expect(s.connections).toHaveLength(count);
  await expect(relay.request('node.report', {})).rejects.toBeInstanceOf(RelayDeliveryError);
});

test('stop rejects waiters and cancels reconnect and heartbeat', async () => {
  const s = await server((socket, frame) => { if (frame.type === 'node.register') ack(socket, frame); });
  const relay = connection(s.url); await relay.start();
  const pending = relay.request('node.report', {});
  const rejected = expect(pending).rejects.toMatchObject({ delivery: 'unknown' });
  await pause(10);
  await relay.stop(); await rejected;
  const count = s.frames.length; await pause(130);
  expect(s.frames).toHaveLength(count); expect(relay.state).toBe('stopped');
});

test('registration timeout never releases business traffic and stop ends pending startup', async () => {
  const s = await server(() => {});
  const relay = connection(s.url, { ackTimeoutMs: 20 });
  const started = relay.start();
  const stopped = expect(started).rejects.toMatchObject({ delivery: 'not-sent' });
  await pause(65);
  expect(s.frames.length).toBeGreaterThanOrEqual(2);
  expect(s.frames.every(frame => frame.type === 'node.register')).toBe(true);
  await relay.stop(); await stopped;
});

test('replacement authority error is terminal and errors never expose credentials', async () => {
  const errors: string[] = [];
  const s = await server((socket, frame) => {
    if (frame.type === 'node.register') ack(socket, frame);
    else socket.send(JSON.stringify({ type: 'error', payload: { code: 'gateway_owner_mismatch', message: 'secret' } }));
  });
  const relay = connection(s.url, { onError: error => errors.push(error.message) });
  await relay.start();
  await expect(relay.request('node.report', {})).rejects.toMatchObject({ delivery: 'unknown' });
  await pause(50);
  expect(relay.state).toBe('revoked'); expect(s.connections).toHaveLength(1);
  expect(errors.join(' ')).not.toContain('secret');
});
