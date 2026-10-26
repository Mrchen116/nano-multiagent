import { createServer, type ServerResponse } from 'node:http';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

function answer(res: ServerResponse, block: Record<string, unknown>) {
  if (res.destroyed) return;
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

it.each(['nano', 'codex'] as const)('keeps %s recovery alive across configuration reservation release but revokes it on cancel/disable', async policy => {
  const home = await mkdtemp(join(tmpdir(), 'nano-review-config-'));
  const phases = ['request', 'backoff'];
  const controls = ['rejected', 'persist-failed', 'metadata', 'cancel', 'disable'];
  const cases = phases.flatMap(phase => controls.map(control => `${phase}-${control}`));
  const counts = new Map<string, number>();
  const held = new Map<string, () => void>();
  const requests: { scenario: string; model: string; session: string }[] = [];
  const server = createServer(async (req, res) => {
    let raw = ''; for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw);
    const text = JSON.stringify(body.messages);
    const scenario = [...cases, 'unaffected'].findLast(value => text.includes(`CASE:${value}:END`));
    if (!scenario) { res.writeHead(400); res.end('missing case'); return; }
    const key = `${body.model}:${scenario}`; const count = (counts.get(key) ?? 0) + 1; counts.set(key, count);
    requests.push({ scenario, model: body.model, session: String(req.headers['x-agent-session-id']) });
    if (body.model === 'main') {
      answer(res, count === 1 ? { type: 'tool_use', id: `effect-${scenario}`, name: 'fixture_effect', input: { scenario } } : { type: 'text', text: 'done' }); return;
    }
    const verdict = () => answer(res, { type: 'text', text: policy === 'nano' ? '<block>no</block>' : '{"outcome":"allow"}' });
    if (count === 1 && scenario.startsWith('request-')) { held.set(scenario, verdict); return; }
    if (count === 1 && scenario.startsWith('backoff-')) {
      res.writeHead(503, { 'content-type': 'application/json', 'retry-after': '1', 'request-id': scenario });
      res.end(JSON.stringify({ type: 'error', error: { type: 'overloaded_error', message: 'controlled backoff' } })); return;
    }
    verdict();
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  let client: RuntimeClient | undefined; let logs = '';
  try {
    const port = (server.address() as { port: number }).port;
    await writeFile(join(home, 'fixture.mjs'), `import {appendFile} from 'node:fs/promises';
export const name='config-effects';export const inject=['tools','agents'];
export function apply(ctx){ctx.on('agent/disposed',({agent})=>{if(agent.id.startsWith('nano-codex-'))return appendFile(process.env.DSH_HOME+'/reviewer-ends.jsonl',JSON.stringify(agent.session.snapshotEvents().filter(e=>e.type==='turn/end'))+'\\n');});ctx.tools.register({name:'fixture_effect',description:'Record an isolated effect',parameters:{type:'object',properties:{scenario:{type:'string'}},required:['scenario']},output:{schema:{},render:()=>[{type:'text',text:'done'}]},async execute(args){await appendFile(process.env.DSH_HOME+'/effects.jsonl',JSON.stringify(args)+'\\n');return{};}});}`);
    await prepareProfile(home, [
      { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'anthropic-messages', baseURL: `http://127.0.0.1:${port}`, apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'main', contextWindow: 200000 }, { id: 'review', contextWindow: 200000 }] } } } },
      { insert: [{ id: 'config-effects', name: join(home, 'fixture.mjs') }] },
    ]);
    const agents = [...cases, 'unaffected'].map(agentId => ({ agentId, revision: '1', mode: 'global', provider: 'fixture', model: 'main', features: { memory_curation: false, skill_creation: false, intelligent_ui: false, task_graph: false }, toolAllowlist: ['fixture_effect'], approval: { ...approvalDefaults, rules: policy, globalRoot: home, reviewer: { provider: 'fixture', model: 'review' } } }));
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    await client.rpc.request('initialize', { protocol: 1, agents, bindings: [] });
    const submit = async (scenario: string) => {
      await client!.rpc.request('session.ensure', { sessionId: scenario, agentId: scenario, revision: '1', ownerId: 'owner', cwd: home });
      await client!.rpc.request('session.submit', { sessionId: scenario, inputId: scenario, mode: 'followup', content: [{ type: 'text', text: `Execute CASE:${scenario}:END once.` }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: scenario } });
    };
    for (const scenario of cases) {
      await submit(scenario);
      await expect.poll(() => requests.filter(row => row.scenario === scenario && row.model === 'review').length).toBe(1);
      const config = agents.find(agent => agent.agentId === scenario)!;
      const operationId = `op-${scenario}`; const fingerprint = `fingerprint-${scenario}`;
      if (scenario.endsWith('rejected')) {
        expect(await client.rpc.request('configuration.prepare', { operationId, fingerprint, config: { ...config, revision: '2', toolAllowlist: [] } })).toMatchObject({ ready: false, error_code: 'capability_in_use' });
        // This is the exact release RPC used by the PA/Node rejected transaction.
        expect(await client.rpc.request('configuration.release', { agentId: scenario, operationId })).toMatchObject({ released: true });
      } else if (scenario.endsWith('persist-failed')) {
        expect(await client.rpc.request('configuration.prepare', { operationId, fingerprint, config: { ...config, revision: '2' } })).toMatchObject({ ready: true });
        // A failed persistence does not apply the candidate, only release its reservation.
        await client.rpc.request('configuration.release', { agentId: scenario, operationId });
      } else if (scenario.endsWith('metadata')) {
        const next = { ...config, revision: '2' };
        expect(await client.rpc.request('configuration.prepare', { operationId, fingerprint, config: next })).toMatchObject({ ready: true });
        expect(await client.rpc.request('configuration.apply', { ...next, operationId, fingerprint })).toMatchObject({ effective: true, revision: '2' });
        await client.rpc.request('configuration.release', { agentId: scenario, operationId });
      } else if (scenario.endsWith('cancel')) {
        await client.rpc.request('session.cancel', { sessionId: scenario });
      } else {
        expect(await client.rpc.request('agent.disable', { agentId: scenario, revision: 1 })).toMatchObject({ confirmed: true });
      }
      held.get(scenario)?.();
      if (scenario.endsWith('disable')) {
        expect(requests.filter(row => row.scenario === scenario && row.model === 'review')).toHaveLength(1);
        continue; // Disabled sessions cannot be restored for observation; effects are checked below.
      }
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: scenario, inputId: scenario }) as any).terminal, { timeout: 10000 }).toBeTruthy();
      const observation = await client.rpc.request('session.observe', { sessionId: scenario }) as any;
      const revoked = scenario.endsWith('cancel') || scenario.endsWith('disable');
      expect(observation.approvals.some((row: any) => row.callId === `effect-${scenario}` && row.decision === 'allow')).toBe(!revoked);
      const seen = requests.filter(row => row.scenario === scenario && row.model === 'review');
      expect(seen).toHaveLength(!revoked && scenario.startsWith('backoff') ? 2 : 1);
      if (!revoked) {
        const audit = observation.approvals.find((row: any) => row.recovery);
        expect(audit.recovery).toMatchObject({ finalRoute: 'allow', retriesUsed: scenario.startsWith('backoff') ? 1 : 0 });
        if (policy === 'codex' && seen.length === 2) expect(seen[0]!.session).not.toBe(seen[1]!.session);
      }
    }
    await submit('unaffected');
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'unaffected', inputId: 'unaffected' }) as any).terminal).toBeTruthy();
    const effects = (await readFile(join(home, 'effects.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line).scenario);
    expect(effects).toEqual([...cases.filter(value => !value.endsWith('cancel') && !value.endsWith('disable')), 'unaffected']);
    await client.shutdown(); client = undefined;
  } catch (error) {
    const observation = client ? await client.rpc.request('session.observe', { sessionId: requests.at(-1)?.scenario }).catch(() => null) : null;
    throw new Error(`${error}\nHTTP=${JSON.stringify(requests)}\nOBS=${JSON.stringify(observation)}\nENDS=${await readFile(join(home, 'reviewer-ends.jsonl'), 'utf8').catch(() => '')}\n${logs}`, { cause: error });
  }
  finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve()));
    // home is the mkdtemp-owned test root, never a caller checkout.
    await rm(home, { recursive: true, force: true });
  }
}, 60_000);
