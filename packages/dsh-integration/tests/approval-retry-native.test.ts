import { createServer } from 'node:http';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

// This seam must remain HTTP + the locked native loop: an in-memory verdict mock
// cannot catch pi-ai dropping status/headers or native retries multiplying policy.
for (const rules of ['nano', 'codex', 'dsh'] as const) {
  it.each([false, true, 'date', 'invalid', 'transport'] as const)(`${rules} executes once after real reviewer HTTP (initial503=%s)`, async initial503 => {
    const home = await mkdtemp(join(tmpdir(), 'nano-review-recovery-'));
    const requests: { session: string; root: string; status: number; time: number }[] = [];
    let retryAfterDeadline = 0;
    const failedStatus = initial503 === 'date' ? 429 : initial503 === 'transport' ? 0 : 503;
    const server = createServer(async (req, res) => {
      let body = ''; for await (const chunk of req) body += chunk;
      const input = JSON.parse(body);
      expect(input.model).toBe('review');
      const status = initial503 && requests.length === 0 ? failedStatus : 200;
      requests.push({ session: String(req.headers['x-agent-session-id']), root: String(req.headers['x-session-id']), status, time: Date.now() });
      if (status === 0) { res.destroy(); return; }
      if (status !== 200) {
        const retryAfter = initial503 === 'date' ? new Date(Date.now() + 2000).toUTCString() : initial503 === 'invalid' ? 'not-a-delay' : '1';
        retryAfterDeadline = initial503 === 'date' ? Date.parse(retryAfter) : initial503 === 'invalid' ? 0 : Date.now() + 1000;
        res.writeHead(status, { 'content-type': 'application/json', 'retry-after': retryAfter, 'request-id': 'review-failure' });
        res.end(JSON.stringify({ type: 'error', error: { type: 'overloaded_error', message: 'Temporary fixture overload' } }));
        return;
      }
      const text = rules === 'nano' ? '<block>no</block>' : rules === 'dsh' ? '{"risk":"low","decision":"allow"}' : '{"outcome":"allow"}';
      res.writeHead(200, { 'content-type': 'text/event-stream', 'request-id': 'review-success' });
      const emit = (type: string, data: object) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`);
      emit('message_start', { message: { id: 'review', type: 'message', role: 'assistant', model: 'review', content: [], stop_reason: null, usage: { input_tokens: 20, output_tokens: 0 } } });
      emit('content_block_start', { index: 0, content_block: { type: 'text', text } });
      emit('content_block_stop', { index: 0 });
      emit('message_delta', { delta: { stop_reason: 'end_turn', stop_sequence: null }, usage: { output_tokens: 5 } });
      emit('message_stop', {}); res.end();
    });
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    let client: RuntimeClient | undefined;
    let logs = '';
    try {
      await writeFile(join(home, 'fixture.mjs'), `
import {appendFile} from 'node:fs/promises';
export const name='review-recovery-fixture'; export const inject=['llm','tools'];
export function apply(ctx) {
 const turns=new Set();
 ctx.tools.register({name:'fixture_effect',description:'Record one mutation',parameters:{type:'object',properties:{}},output:{schema:{},render:(_args,value)=>[{type:'text',text:value}]},async execute(){await appendFile(process.env.DSH_HOME+'/effects.jsonl','once\\n');return 'executed';}});
 ctx.on('llm/stream',async function*(options,next){
  if(options.model!=='main'){yield* next();return;}
  const human=options.messages.findLast(message=>message.role==='user'&&message.source?.kind==='nano-human');
  if(!turns.has(human.id)){turns.add(human.id);yield{type:'block-end',index:0,block:{type:'tool-call',id:'one-action',name:'fixture_effect',arguments:'{}'}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}
  yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};
 });
}`);
      const port = (server.address() as { port: number }).port;
      await prepareProfile(home, [
        { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'anthropic-messages', baseURL: `http://127.0.0.1:${port}`, apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'main', contextWindow: 100000 }, { id: 'review', contextWindow: 100000, reasoningEfforts: { low: 'low' } }], retryPolicy: { mode: 'always', maxRetries: 5 } } } } },
        { insert: [{ id: 'review-recovery-fixture', name: join(home, 'fixture.mjs') }] },
      ]);
      client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => logs += text });
      const config = { agentId: 'a', revision: '1', provider: 'fixture', model: 'main', mode: 'global', approval: { ...approvalDefaults, globalRoot: home, rules, reviewer: { provider: 'fixture', model: 'review' } } };
      let authorizationReads = 0;
      client.rpc.handle('product.call', value => {
        if ((value as { method: string }).method === 'pa.authorization') authorizationReads++;
        throw new Error('Unexpected product query');
      });
      await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [] });
      await client.rpc.request('session.ensure', { sessionId: 'parent', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home });
      await client.rpc.request('session.submit', { sessionId: 'parent', inputId: 'request', mode: 'followup', content: [{ type: 'text', text: 'Perform the isolated fixture action once' }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: 'request' } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'parent', inputId: 'request' }) as { terminal?: unknown }).terminal, { timeout: 15000 }).toBeTruthy();
      const observation = await client.rpc.request('session.observe', { sessionId: 'parent' }) as { approvals: any[] };
      const effects = await readFile(join(home, 'effects.jsonl'), 'utf8').catch(error => {
        if (error.code === 'ENOENT') return ''; throw error;
      });
      expect({ effects, requests: requests.map(row => row.status), audit: observation.approvals.map(row => ({ source: row.source, decision: row.decision })) }).toMatchObject({ effects: 'once\n', requests: initial503 ? [failedStatus, 200] : [200] });
      expect(authorizationReads).toBe(0);
      if (initial503) {
        if (retryAfterDeadline) expect(requests[1]!.time).toBeGreaterThanOrEqual(retryAfterDeadline - 20);
        else expect(requests[1]!.time - requests[0]!.time).toBeGreaterThanOrEqual(440);
        const row = observation.approvals.find(row => row.callId === 'one-action' && row.recovery);
        expect(row?.recovery).toMatchObject({ retriesUsed: 1, formatRetriesUsed: 0 });
        if (rules === 'codex') expect(requests[1]!.session).not.toBe(requests[0]!.session);
      }
    } catch (error) {
      const observation = client ? await client.rpc.request('session.observe', { sessionId: 'parent' }).then((value: any) => ({ approvals: value.approvals, events: value.events.filter((event: any) => ['tool/result', 'turn/end', 'llm/error', 'request/error'].includes(event.type)), lookup: value.status })).catch(() => null) : null;
      throw new Error(`${String(error)}\n${logs}\n${JSON.stringify(requests)}\n${JSON.stringify(observation)}`, { cause: error });
    } finally {
      if (client) await client.shutdown();
      server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve()));
      // The target is the exact mkdtemp directory allocated by this test.
      await rm(home, { recursive: true, force: true });
    }
  }, 25000);
}
