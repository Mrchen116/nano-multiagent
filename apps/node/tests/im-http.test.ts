import { createServer } from 'node:http';
import { expect, it } from 'vitest';
import { requestIm } from '../src/im-http.js';

it.each(['record', 'tuples', 'Headers'] as const)('preserves %s request headers on the wire and uses the current gateway token', async shape => {
  const server = createServer(async (req, res) => {
    let body = ''; for await (const chunk of req) body += chunk;
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ headers: req.headers, body, url: req.url }));
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const record = { 'Content-Type': 'application/json', 'Idempotency-Key': 'shadow:message', 'x-agent-lifecycle-revision': '3', authorization: 'Bearer stale' };
  const headers = shape === 'record' ? record : shape === 'tuples' ? Object.entries(record) : new Headers(record);
  try {
    const base = `ws://127.0.0.1:${(server.address() as { port: number }).port}/ws`;
    const options = { method: 'POST', headers, body: JSON.stringify({ content: 'hello' }) };
    for (const token of ['registered', 'refreshed']) {
      expect(await requestIm(base, token, '/im/test?agent_id=a', options)).toMatchObject({
        url: '/im/test?agent_id=a', body: options.body,
        headers: { 'content-type': 'application/json', 'idempotency-key': 'shadow:message', 'x-agent-lifecycle-revision': '3', authorization: `Bearer ${token}` },
      });
    }
    expect(new Headers(headers).get('authorization')).toBe('Bearer stale');
  } finally {
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
  }
});
