import { createServer, type ServerResponse } from 'node:http';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

function respond(res: ServerResponse, text: string, usage: number, tool = false) {
  res.writeHead(200, { 'content-type': 'text/event-stream', 'request-id': `ok-${usage}` });
  const emit = (type: string, data: object) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`);
  emit('message_start', { message: { id: `response-${usage}`, type: 'message', role: 'assistant', model: 'fixture', content: [], stop_reason: null, usage: { input_tokens: usage, output_tokens: 0 } } });
  emit('content_block_start', { index: 0, content_block: tool ? { type: 'tool_use', id: 'driver', name: 'fixture_driver', input: {} } : { type: 'text', text } });
  if (tool) emit('content_block_delta', { index: 0, delta: { type: 'input_json_delta', partial_json: '{}' } });
  emit('content_block_stop', { index: 0 });
  emit('message_delta', { delta: { stop_reason: tool ? 'tool_use' : 'end_turn', stop_sequence: null }, usage: { output_tokens: usage } });
  emit('message_stop', {}); res.end();
}

it('isolates exact native Guardian streams from idle, fork, CC, disclosure, main and auxiliary requests', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-review-streams-'));
  const requests: { scenario: string; ordinal: number; session: string; time: number }[] = [];
  const counts = new Map<string, number>();
  const barrier = new Map<string, () => void>();
  const usage = { I: 11, A: 21, B: 31, C: 41, D: 51, P: 61, M: 71, X: 81, F: 91, DRIVER: 1 };
  const server = createServer(async (req, res) => {
    let raw = ''; for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw); const text = JSON.stringify(body.messages);
    const scenario = [...text.matchAll(/CONC=([A-Z]+):END/g)].at(-1)?.[1];
    if (!scenario) { res.writeHead(400); res.end('missing marker'); return; }
    const ordinal = (counts.get(scenario) ?? 0) + 1; counts.set(scenario, ordinal);
    requests.push({ scenario, ordinal, session: String(req.headers['x-agent-session-id']), time: Date.now() });
    const reply = () => {
      if (['A', 'B'].includes(scenario) && ordinal === 1) {
        const status = scenario === 'A' ? 429 : 503;
        res.writeHead(status, { 'content-type': 'application/json', 'retry-after': scenario === 'A' ? '2' : '3', 'request-id': `${scenario}-${ordinal}` });
        res.end(JSON.stringify({ type: 'error', error: { type: status === 429 ? 'rate_limit_error' : 'overloaded_error', message: 'controlled concurrent failure' } }));
      } else respond(res, scenario === 'D' ? '<block>no</block>' : scenario === 'P' ? '{"decision":"allow","reason":"host frozen disclosure"}' : ['M', 'X'].includes(scenario) ? 'done' : '{"outcome":"allow"}', usage[scenario as keyof typeof usage], scenario === 'DRIVER' && ordinal === 1);
    };
    if (['A', 'B', 'C', 'D', 'P', 'M'].includes(scenario) && ordinal === 1) {
      barrier.set(scenario, reply);
      if (barrier.size === 6) { for (const release of barrier.values()) release(); }
    } else reply();
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  let client: RuntimeClient | undefined; let logs = '';
  try {
    const port = (server.address() as { port: number }).port;
    const approval = { ...approvalDefaults, globalRoot: home, alwaysAllowTools: ['fixture_driver'], reviewer: { provider: 'fixture', model: 'review' } };
    await writeFile(join(home, 'fixture.mjs'), `
import {appendFile} from 'node:fs/promises';
import {ReviewRecovery} from ${JSON.stringify(new URL('../lib/policy/recovery.js', import.meta.url).href)};
import {classify} from ${JSON.stringify(new URL('../lib/policy/classifier.js', import.meta.url).href)};
export const name='stream-driver';export const inject=['tools','agents','llm','nanoApproval','codexApproval'];
export function apply(ctx){
 const config={agentId:'a',revision:'1',mode:'global',provider:'fixture',model:'main',features:{memory_curation:false,skill_creation:false},approval:${JSON.stringify(approval)}};
 const log=value=>appendFile(process.env.DSH_HOME+'/results.jsonl',JSON.stringify(value)+'\\n');
 ctx.tools.register({name:'fixture_driver',description:'Exercise independent native reviewers',parameters:{type:'object'},output:{schema:{},render:()=>[{type:'text',text:'driver finished'}]},async execute(_args,exec){
  const other=ctx.agents.get('other');const idle=ctx.agents.get('idle');
  const request=(scenario,parent,signal,recovery)=>({exec:{...exec,agent:parent,name:'fixture_effect',callId:scenario,arguments:{scenario:'CONC='+scenario+':END'},signal},config,sources:ctx.nanoApproval.sources,inherited:[],reviewer:{provider:'fixture',model:'review'},recovery});
  const run=async(scenario,parent,controller=new AbortController())=>{
   const recovery=new ReviewRecovery(controller.signal,scenario);
   try{const result=await ctx.codexApproval.review(request(scenario,parent,controller.signal,recovery));await log({scenario,result,trace:recovery.finish('allow','internal')});}
   catch(error){await log({scenario,error:String(error),trace:recovery.finish('cancelled','cancel')});}
  };
  await run('I',idle); // Retained idle registry entry must not intercept any unrelated stream.
  const b=new AbortController();const timer=setTimeout(()=>b.abort(),1200);
  try{
   const hand=async()=>{const recovery=new ReviewRecovery(exec.signal,'D');try{const result=await classify(ctx,{...request('D',exec.agent,exec.signal,recovery),config:{...config,approval:{...config.approval,rules:'nano'}}});await log({scenario:'D',result,trace:recovery.finish('allow','internal')});}finally{recovery.finish('done','internal');}};
   const disclosure=async()=>{const result=await ctx.codexApproval.reviewDisclosure({agent:exec.agent,config,action:{marker:'CONC=P:END'},evidence:async()=>[],signal:exec.signal});await log({scenario:'P',result});};
   await Promise.all([run('A',exec.agent),run('B',exec.agent,b),run('C',other),hand(),disclosure()]);
   const previous=ctx.agents.list().find(agent=>agent.id.startsWith('nano-codex-')&&agent.session.header.parentSession===undefined);
   const chunks=[];for await(const chunk of ctx.llm.stream({provider:'fixture',model:'review',sessionId:previous?.id,purpose:'auxiliary-probe',messages:[{role:'user',content:[{type:'text',text:'CONC=X:END'}]}],signal:exec.signal}))chunks.push(chunk);
   await log({scenario:'X',chunks});
   await run('F',other); // A later action replaces C's currentAttempt without stale finally writes.
  }finally{clearTimeout(timer);}
  return{};
 }});
}`);
    await prepareProfile(home, [
      { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'anthropic-messages', baseURL: `http://127.0.0.1:${port}`, apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'main', contextWindow: 200000 }, { id: 'review', contextWindow: 200000, reasoningEfforts: { high: 'high' }, defaultReasoningEffort: 'high' }] } } } },
      { insert: [{ id: 'stream-driver', name: join(home, 'fixture.mjs') }] },
    ]);
    const config = { agentId: 'a', revision: '1', mode: 'global', provider: 'fixture', model: 'main', features: { memory_curation: false, skill_creation: false }, toolAllowlist: ['fixture_driver'], approval };
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [] });
    for (const sessionId of ['parent', 'other', 'idle', 'main']) await client.rpc.request('session.ensure', { sessionId, agentId: 'a', revision: '1', ownerId: 'owner', cwd: home });
    const submit = (sessionId: string, scenario: string) => client!.rpc.request('session.submit', { sessionId, inputId: scenario, mode: 'followup', content: [{ type: 'text', text: `CONC=${scenario}:END` }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: scenario } });
    await submit('parent', 'DRIVER');
    await expect.poll(() => requests.filter(row => ['A', 'B', 'C', 'D', 'P'].includes(row.scenario)).length, { timeout: 10000 }).toBe(5);
    await submit('main', 'M');
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'parent', inputId: 'DRIVER' }) as any).terminal, { timeout: 15000 }).toBeTruthy();
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'main', inputId: 'M' }) as any).terminal).toBeTruthy();
    const results = (await readFile(join(home, 'results.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    const row = (scenario: string) => results.find(result => result.scenario === scenario);
    expect(results.map(result => result.scenario).sort()).toEqual(['I', 'A', 'B', 'C', 'D', 'P', 'X', 'F'].sort());
    expect(row('B').trace.finalRoute).toBe('cancel');
    expect(requests.filter(request => request.scenario === 'B')).toHaveLength(1);
    expect(row('A').trace).toMatchObject({ retriesUsed: 1, formatRetriesUsed: 0 });
    expect(row('A').trace.attempts[0]).toMatchObject({ status: 429, requests: [{ http: { status: 429, retryAfterMs: 2000, requestId: 'A-1' } }] });
    const aRequests = requests.filter(request => request.scenario === 'A');
    expect(aRequests[1]!.time - aRequests[0]!.time).toBeGreaterThanOrEqual(1950);
    expect(aRequests[1]!.session).not.toBe(aRequests[0]!.session);
    for (const scenario of ['I', 'A', 'C', 'D', 'F']) {
      expect(row(scenario).result.decision.behavior).toBe('allow');
      expect(row(scenario).trace.knownUsage.outputTokens).toBe(usage[scenario as keyof typeof usage]);
      expect(row(scenario).trace.usageComplete).toBe(scenario !== 'A');
      const request = row(scenario).trace.attempts.at(-1).requests[0];
      expect(request.resolvedEffort).toBe('high');
      if (scenario !== 'A') expect(request.http).toBeUndefined();
    }
    expect(row('P').result).toMatchObject({ decision: 'allow', usage: { outputTokens: usage.P } });
    expect(row('X').chunks.find((chunk: any) => chunk.type === 'usage').usage.outputTokens).toBe(usage.X);
    expect(row('C').result.metadata.sessionId).toBe(row('F').result.metadata.sessionId);
    expect(row('F').result.metadata.contextMode).toBe('delta');
    const identities = requests.filter(request => ['I', 'A', 'B', 'C', 'P'].includes(request.scenario) && request.ordinal === 1).map(request => request.session);
    expect(new Set(identities).size).toBe(5);
    await client.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${error}\nHTTP=${JSON.stringify(requests)}\nRESULTS=${await readFile(join(home, 'results.jsonl'), 'utf8').catch(() => '')}\n${logs}`, { cause: error }); }
  finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve()));
    await rm(home, { recursive: true, force: true });
  }
}, 25000);
