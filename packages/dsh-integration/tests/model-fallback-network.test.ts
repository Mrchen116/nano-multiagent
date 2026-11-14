import { createServer } from 'node:http';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it.each(['provider-timeout', 'watchdog', 'unavailable-host'] as const)('uses the backup after %s and waits when the backup also stalls', async fault => {
  const home = await mkdtemp(join(tmpdir(), 'nano-fallback-network-'));
  let client: RuntimeClient | undefined;
  let recover = false;
  const requests: string[] = [];
  const server = createServer(async (req, res) => {
    let body = '';
    for await (const chunk of req) body += chunk;
    const { model } = JSON.parse(body);
    requests.push(model);
    if (model === 'primary' && fault === 'provider-timeout') {
      res.writeHead(200, { 'content-type': 'text/event-stream' });
      res.end('event: error\ndata: {"type":"error","error":{"type":"api_error","message":"Upstream generation timed out"}}\n\n');
      return;
    }
    if (!recover || (model === 'primary' && fault !== 'unavailable-host')) return;
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    const emit = (type: string, data: object) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`);
    emit('message_start', { message: { id: 'answer', type: 'message', role: 'assistant', model, content: [], stop_reason: null, usage: { input_tokens: 10, output_tokens: 0 } } });
    emit('content_block_start', { index: 0, content_block: { type: 'text', text: '' } });
    emit('content_block_delta', { index: 0, delta: { type: 'text_delta', text: 'Completed original task.' } });
    emit('content_block_stop', { index: 0 });
    emit('message_delta', { delta: { stop_reason: 'end_turn', stop_sequence: null }, usage: { output_tokens: 5 } });
    emit('message_stop', {});
    res.end();
  });
  try {
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    const port = (server.address() as { port: number }).port;
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: {
      api: 'anthropic-messages', baseURL: `http://127.0.0.1:${port}/v1`, apiKeyEnv: 'NANO_TEST_KEY',
      streamIdleTimeoutMs: 500, retryPolicy: { mode: 'normal', maxRetries: 0 },
      models: ['primary', 'backup'].map(id => ({ id, contextWindow: 100000 })),
    } } } }]);
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' } });
    registerNoopTaskHosts(client);
    client.rpc.handle('model.check', () => {
      if (fault === 'unavailable-host') throw new Error('delivery host offline');
      return { published: false };
    });
    const binding = { sessionId: 'root', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
    await client.rpc.request('initialize', { protocol: 1, agents: [{
      agentId: 'a', revision: '1', mode: 'global', workspace: home, provider: 'fixture', model: 'primary',
      modelFallbacks: [{ provider: 'fixture', model: 'backup' }], toolAllowlist: [], features: { dreaming: false },
      approval: { dangerouslySkipPermissions: true },
    }], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);
    const pid = client.process.pid;
    await client.rpc.request('session.submit', { sessionId: 'root', inputId: 'one', mode: 'followup',
      content: [{ type: 'text', text: 'Complete my task.' }],
      source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: 'one' },
    });
    const observe = async () => await client!.rpc.request('session.observe', { sessionId: 'root' }) as any;
    if (fault !== 'unavailable-host') {
      await expect.poll(() => requests.includes('backup'), { timeout: 5000 }).toBe(true);
    }
    await expect.poll(async () => (await observe()).events.filter((event: any) => event.type === 'llm/retry')
      .map((event: any) => event.data.mode), { timeout: 3000 }).toEqual(['always']);
    expect((await observe()).status).toBe('running');
    recover = true;
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'root', inputId: 'one' }) as any)
      .terminal?.kind, { timeout: 8000 }).toBe('completed');
    expect(client.process.pid).toBe(pid);
    expect(requests).toEqual(fault === 'unavailable-host' ? ['primary', 'primary'] : ['primary', 'backup', 'backup']);
    const { modelRuns } = await observe();
    expect(modelRuns).toHaveLength(1);
    expect(modelRuns[0].state).toBe('completed');
    await client.shutdown();
    client = undefined;
  } finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
    await rm(home, { recursive: true, force: true });
  }
}, 20000);
