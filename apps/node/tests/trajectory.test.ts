import { once } from 'node:events';
import http from 'node:http';
import net from 'node:net';
import { expect, it } from 'vitest';
import { WebSocketServer } from 'ws';
import { TRAJECTORY_MAX_BYTES, TrajectoryValueDecoder, type RuntimePort } from '@nano/product-contracts';
import { NodeTrajectory } from '../src/trajectory.js';

it.each([false,true])('drains native reads through the configured network agent (routed=%s)', async routed => {
  const server = new WebSocketServer({ port: 0, host: '127.0.0.1' });
  await once(server, 'listening');
  const port = (server.address() as { port: number }).port;
  const previousAgent=http.globalAgent;
  const networkAgent=new http.Agent();
  networkAgent.createConnection=()=>net.connect({host:'127.0.0.1',port});
  if(routed)http.globalAgent=networkAgent;
  const page = { records: [{ text: '历史😀"\\'.repeat(300_000) }], hasMore: true };
  const runtime = { request: async (method: string) => method === 'trajectory.prepare'
    ? { version: '0.2.1-alpha.1' } : { ok: true, value: page } } as unknown as RuntimePort;
  const trajectory = new NodeTrajectory({ imUrl: routed ? 'http://unreachable.invalid:1' : `http://127.0.0.1:${port}`, runtime, valid: () => true });
  const scope = { observerId: 'reader', rootAgentId: 'agent', rootSessionId: 'root', sessionId: 'child', ownerId: 'owner', nodeId: 'node', nodeEpoch: 1 };
  const connected = once(server, 'connection');
  try {
    trajectory.prepare(scope, 'ticket');
    const [socket] = await connected;
    const decoder = new TrajectoryValueDecoder(), sizes: number[] = [];
    let ready!: () => void, complete!: (value: unknown) => void;
    const opened = new Promise<void>(resolve => { ready = resolve; });
    const result = new Promise<unknown>(resolve => { complete = resolve; });
    socket.on('message', raw => {
      sizes.push(raw.byteLength);
      const value = decoder.push(JSON.parse(raw.toString()));
      if (value?.type === 'ready') ready();
      if (value?.requestId === 'page') complete(value);
    });
    await opened;
    socket.send(JSON.stringify({ type: 'call', requestId: 'page', method: 'session/page', params: {} }));
    await expect(result).resolves.toEqual({ type: 'result', observerId: 'reader', requestId: 'page', value: { ok: true, value: page } });
    decoder.finish();
    expect(sizes.length).toBeGreaterThan(2);
    expect(Math.max(...sizes)).toBeLessThan(TRAJECTORY_MAX_BYTES);
  } finally {
    trajectory.closeAll();
    for (const socket of server.clients) socket.terminate();
    await new Promise<void>(resolve => server.close(() => resolve()));
    http.globalAgent=previousAgent;
    networkAgent.destroy();
  }
});
