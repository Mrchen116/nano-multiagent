import { createServer, type ServerResponse } from 'node:http';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

function respond(res: ServerResponse, block: Record<string, unknown>) {
  const tool = block.type === 'tool_use';
  res.writeHead(200, { 'content-type': 'text/event-stream' });
  const emit = (type: string, data: object) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`);
  emit('message_start', { message: { id: 'fixture', type: 'message', role: 'assistant', model: 'fixture', content: [], stop_reason: null, usage: { input_tokens: 20, output_tokens: 0 } } });
  emit('content_block_start', { index: 0, content_block: tool ? { ...block, input: {} } : block });
  if (tool) emit('content_block_delta', { index: 0, delta: { type: 'input_json_delta', partial_json: JSON.stringify(block.input) } });
  emit('content_block_stop', { index: 0 });
  emit('message_delta', { delta: { stop_reason: tool ? 'tool_use' : 'end_turn', stop_sequence: null }, usage: { output_tokens: 5 } });
  emit('message_stop', {}); res.end();
}

it('recovers real HTTP 503/429/format failures under the native loop without provider retry multiplication or duplicate effects', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-review-retry-'));
  const requests: { scenario: string; model: string; session: string; time: number }[] = [];
  const cases = ['nano', 'codex'].flatMap(policy => ['service', 'rate', 'rate-date', 'format', 'auth', 'persistent', 'mixed', 'invalid', 'long', 'transport'].map(kind => `${policy}-${kind}`));
  const counts = new Map<string, number>();
  const server = createServer(async (req, res) => {
    let raw = ''; for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw);
    const text = body.messages.map((message: any) => typeof message.content === 'string' ? message.content : message.content.filter((block: any) => block.type === 'text').map((block: any) => block.text).join('\n')).join('\n');
    const scenario = cases.findLast(value => text.includes(value));
    if (!scenario) { res.writeHead(400); res.end('missing scenario'); return; }
    const key = `${body.model}:${scenario}`; const count = (counts.get(key) ?? 0) + 1; counts.set(key, count);
    requests.push({ scenario, model: body.model, session: String(req.headers['x-agent-session-id']), time: Date.now() });
    if (body.model === 'main') {
      respond(res, count === 1 ? { type: 'tool_use', id: `call-${scenario}`, name: 'fixture_effect', input: { scenario } } : { type: 'text', text: 'done' }); return;
    }
    if (scenario.endsWith('transport') && count === 1) { req.socket.destroy(); return; }
    if (scenario.endsWith('auth') || scenario.endsWith('persistent') || count === 1 && !['format', 'invalid', 'transport'].some(kind => scenario.endsWith(kind))) {
      const status = scenario.endsWith('auth') ? 401 : scenario.includes('-rate') || scenario.endsWith('long') ? 429 : 503;
      const retryAfter = scenario.endsWith('long') ? '15' : scenario.endsWith('rate-date') ? new Date(Date.now() + 2000).toUTCString() : '1';
      res.writeHead(status, { 'content-type': 'application/json', 'retry-after': retryAfter, 'request-id': `${scenario}-${count}` });
      res.end(JSON.stringify({ type: 'error', error: { type: status === 401 ? 'authentication_error' : status === 429 ? 'rate_limit_error' : 'overloaded_error', message: 'controlled failure' } })); return;
    }
    const malformed = scenario.endsWith('invalid') || scenario.endsWith('format') && count === 1 || scenario.endsWith('mixed') && count === 2;
    respond(res, { type: 'text', text: malformed ? 'malformed verdict' : scenario.startsWith('nano') ? '<block>no</block>' : '{"outcome":"allow"}' });
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  let client: RuntimeClient | undefined; let logs = '';
  try {
    const port = (server.address() as { port: number }).port;
    await writeFile(join(home, 'fixture.mjs'), `import {appendFile} from 'node:fs/promises';
export const name='retry-effects';export const inject=['tools'];
export function apply(ctx){ctx.tools.register({name:'fixture_effect',description:'Record one isolated mutation',parameters:{type:'object',properties:{scenario:{type:'string'}},required:['scenario']},output:{schema:{},render:()=>[{type:'text',text:'effect recorded'}]},async execute(args){await appendFile(process.env.DSH_HOME+'/effects.jsonl',JSON.stringify(args)+'\\n');return{};}});}`);
    await prepareProfile(home, [
      { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'anthropic-messages', baseURL: `http://127.0.0.1:${port}`, apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'main', contextWindow: 200000 }, { id: 'review', contextWindow: 200000, reasoningEfforts: { high: 'high' }, defaultReasoningEffort: 'high' }], retryPolicy: { mode: 'always', maxRetries: 5 } } } } },
      { insert: [{ id: 'retry-effects', name: join(home, 'fixture.mjs') }] },
    ]);
    const agents = cases.map(agentId => ({ agentId, revision: '1', mode: 'global', provider: 'fixture', model: 'main', features: { memory_curation: false, skill_creation: false }, toolAllowlist: ['fixture_effect'], approval: { ...approvalDefaults, rules: agentId.startsWith('nano') ? 'nano' : 'codex', globalRoot: home, reviewer: { provider: 'fixture', model: 'review' } } }));
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    await client.rpc.request('initialize', { protocol: 1, agents, bindings: [] });
    for (const config of agents) {
      const sessionId = config.agentId;
      await client.rpc.request('session.ensure', { sessionId, agentId: config.agentId, revision: '1', ownerId: 'owner', cwd: home });
      await client.rpc.request('session.submit', { sessionId, inputId: sessionId, mode: 'followup', content: [{ type: 'text', text: `Execute the isolated ${sessionId} effect exactly once.` }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: sessionId } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId, inputId: sessionId }) as { terminal?: unknown }).terminal, { timeout: 15000 }).toBeTruthy();
      const observation = await client.rpc.request('session.observe', { sessionId }) as { approvals: any[] };
      const review = observation.approvals.find(row => row.recovery);
      expect(review, `${sessionId}: ${JSON.stringify(observation.approvals)}`).toBeTruthy();
      const nativeRequests = requests.filter(row => row.scenario === sessionId && row.model === 'review');
      const blocked = ['auth', 'persistent', 'invalid', 'long'].some(kind => sessionId.endsWith(kind));
      const expectedRequests = ['auth', 'long'].some(kind => sessionId.endsWith(kind)) ? 1 : ['persistent', 'mixed'].some(kind => sessionId.endsWith(kind)) ? 3 : 2;
      expect(nativeRequests, `${sessionId}: ${JSON.stringify(review)}`).toHaveLength(expectedRequests);
      expect(review.recovery).toMatchObject({ callId: `call-${sessionId}`, retriesUsed: expectedRequests - 1, formatRetriesUsed: ['format', 'invalid', 'mixed'].some(kind => sessionId.endsWith(kind)) ? 1 : 0, finalRoute: blocked ? 'return_to_agent' : 'allow' });
      expect(review.recovery.attempts).toHaveLength(expectedRequests);
      if (expectedRequests > 1) {
        const request = review.recovery.attempts[0].requests[0];
        if (['service', 'persistent', 'mixed', 'rate'].some(kind => sessionId.endsWith(kind))) expect(request.http).toMatchObject({ status: sessionId.endsWith('rate') ? 429 : 503, retryAfterMs: 1000, requestId: `${sessionId}-1` });
        if (sessionId.endsWith('rate') || sessionId.endsWith('service')) expect(nativeRequests[1]!.time - nativeRequests[0]!.time).toBeGreaterThanOrEqual(950);
        if (sessionId.endsWith('rate-date')) {
          expect(request.http.status).toBe(429); expect(request.http.retryAfterMs).toBeGreaterThan(900);
          expect(nativeRequests[1]!.time - nativeRequests[0]!.time).toBeGreaterThanOrEqual(request.http.retryAfterMs - 50);
        }
        if (sessionId.startsWith('codex')) {
          expect(nativeRequests[0]!.session).not.toBe(nativeRequests[1]!.session);
          expect(review.recovery.attempts[1].contextMode).toBe('full-retry');
        }
      }
    }
    const effects = (await readFile(join(home, 'effects.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line).scenario);
    expect(effects).toEqual(cases.filter(value => !['auth', 'persistent', 'invalid', 'long'].some(kind => value.endsWith(kind))));
    await client.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${error}\nHTTP=${JSON.stringify(requests)}\n${logs}`, { cause: error }); }
  finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve()));
    await rm(home, { recursive: true, force: true });
  }
}, 60_000);
