import { createServer } from 'node:http';
import { mkdtemp, mkdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

it('groups concurrent global agents and native Skill forks by product root on the actual HTTP wire', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-attribution-'));
  const requests: { root: string; session: string; body: any; path: string }[] = [];
  const server = createServer(async (req, res) => {
    let body = ''; for await (const chunk of req) body += chunk;
    const root = String(req.headers['x-session-id']); const session = String(req.headers['x-agent-session-id']);
    const first = !requests.some(row => row.session === session);
    requests.push({ root, session, body: JSON.parse(body), path: req.url! });
    const tool = root === session && first;
    const block = tool ? { type: 'tool_use', id: 'list-skills', name: 'skill_manage', input: { action: 'list' } } : { type: 'text', text: 'done' };
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    const emit = (type: string, data: object) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`);
    emit('message_start', { message: { id: 'fixture', type: 'message', role: 'assistant', model: 'fixture', content: [], stop_reason: null, usage: { input_tokens: 20, output_tokens: 0 } } });
    emit('content_block_start', { index: 0, content_block: block });
    emit('content_block_stop', { index: 0 });
    emit('message_delta', { delta: { stop_reason: tool ? 'tool_use' : 'end_turn', stop_sequence: null }, usage: { output_tokens: 5 } });
    emit('message_stop', {}); res.end();
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  let client: RuntimeClient | undefined; let logs = '';
  try {
    const port = (server.address() as { port: number }).port;
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: { api: 'anthropic-messages', baseURL: `http://127.0.0.1:${port}`, apiKeyEnv: 'NANO_TEST_KEY', headers: { 'x-session-id': 'stale-static-id' }, models: [{ id: 'fixture', contextWindow: 100000 }], retryPolicy: { mode: 'normal', maxRetries: 0 } } } } }]);
    const agents = ['a', 'b'].map(agentId => ({ agentId, revision: '1', mode: 'global', provider: 'fixture', model: 'fixture', features: { memory_curation: false, skill_creation: true }, knowledge: { skillInterval: 1 }, toolAllowlist: ['skill_manage', 'skill'] }));
    const bindings = agents.map(agent => ({ sessionId: `global-${agent.agentId}`, agentId: agent.agentId, revision: '1', ownerId: 'owner', cwd: join(home, agent.agentId) }));
    for (const binding of bindings) await mkdir(binding.cwd);
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    await client.rpc.request('initialize', { protocol: 1, agents, bindings });
    for (const binding of bindings) await client.rpc.request('session.ensure', binding);
    await Promise.all(bindings.map(binding => client!.rpc.request('session.submit', { sessionId: binding.sessionId, inputId: binding.sessionId, mode: 'followup', content: [{ type: 'text', text: `Inspect skills for ${binding.sessionId}` }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: binding.sessionId } })));
    const reviews = async () => (await client!.rpc.request('knowledge.facts', {}) as { reviews: { rootSessionId: string; childSessionId: string; status: string }[] }).reviews;
    await expect.poll(async () => (await reviews()).filter(row => row.status === 'completed').length, { timeout: 10000 }).toBe(2);
    for (const review of await reviews()) {
      const child = requests.filter(row => row.session === review.childSessionId);
      expect(child.length).toBeGreaterThan(0);
      expect(child.every(row => row.root === review.rootSessionId)).toBe(true);
      expect(JSON.stringify(child[0]!.body.messages)).toContain(`Inspect skills for ${review.rootSessionId}`);
      expect(JSON.stringify(child[0]!.body.messages)).toContain('Review the conversation');
      expect(requests.filter(row => row.session === review.rootSessionId).length).toBe(2);
    }
    expect(requests.map(row => ({root: row.root, path: row.path}))).toEqual(expect.arrayContaining([
      { root: 'global-a', path: expect.stringMatching(/^\/v1\/messages(?:\?|$)/) },
      { root: 'global-b', path: expect.stringMatching(/^\/v1\/messages(?:\?|$)/) },
    ]));
    expect(requests.every(row => ['global-a', 'global-b'].includes(row.root))).toBe(true);
    await client.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${error}\n${logs}`, { cause: error }); }
  finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve()));
    await rm(home, { recursive: true, force: true });
  }
}, 20000);
