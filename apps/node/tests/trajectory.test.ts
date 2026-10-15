import { once } from 'node:events';
import { expect, it } from 'vitest';
import { WebSocketServer } from 'ws';
import { TRAJECTORY_MAX_BYTES, TrajectoryValueDecoder, type RuntimePort } from '@nano/product-contracts';
import { NodeTrajectory } from '../src/trajectory.js';

it('drains fragmented native read responses over its dedicated observer socket', async () => {
  const server = new WebSocketServer({ port: 0, host: '127.0.0.1' });
  await once(server, 'listening');
  const port = (server.address() as { port: number }).port;
  const page = { records: [{ text: '历史😀"\\'.repeat(300_000) }], hasMore: true };
  const runtime = { request: async (method: string) => method === 'trajectory.prepare'
    ? { version: '0.2.1-alpha.1' } : { ok: true, value: page } } as unknown as RuntimePort;
  const trajectory = new NodeTrajectory({ imUrl: `http://127.0.0.1:${port}`, runtime, valid: () => true });
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
  }
});
